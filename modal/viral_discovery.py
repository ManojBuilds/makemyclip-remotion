"""Gemini-powered viral clip discovery, enrichment, and validation.

Three-stage LLM pipeline:
1. discover_viral_clips_with_gemini  — Primary semantic discovery
2. enrich_clips_with_gemini          — Metadata enrichment for heuristic-found clips
3. validate_and_refine_clips_with_gemini — Post-selection quality gate
"""

from __future__ import annotations

import json
import logging
import os

from sentence_utils import (
    build_clip_words,
    calculate_sweet_spot_clip_count,
    clips_overlap_too_much,
    detect_content_mode,
    find_matching_sentence,
    normalize_common_stt_homophones,
    prune_leading_fillers,
    score_sentence_conclusion,
)
from viral_constants import WEAK_ENDING_WORDS

logger = logging.getLogger("makemyclip.viral_discovery")


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` fences from LLM responses."""
    raw = text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    return raw


def _call_gemini_with_retry(
    client,
    model_list: list[str],
    prompt: str,
    schema: dict,
    temperature: float = 0.3,
    max_attempts: int = 2,
) -> str | None:
    """Call Gemini with model fallback and retry logic. Returns response text or None."""
    from google.genai import types

    for model in model_list:
        for attempt in range(max_attempts):
            try:
                logger.info("Calling Gemini %s (attempt %d/%d)...", model, attempt + 1, max_attempts)
                res = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                        temperature=temperature,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    ),
                )
                if res.text:
                    logger.info("Gemini %s returned successfully.", model)
                    return res.text
            except Exception as e:
                err_msg = str(e)
                logger.warning("Gemini %s attempt %d failed: %s", model, attempt + 1, err_msg)
                if "503" in err_msg or "UNAVAILABLE" in err_msg or "429" in err_msg:
                    import time
                    time.sleep(2 * (attempt + 1))
                    continue
                else:
                    break
        # If we got a response from this model, we already returned above
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 1: PRIMARY SEMANTIC DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════════


def discover_viral_clips_with_gemini(
    sentences: list[dict],
    words: list[dict],
    full_text: str = "",
    chapters: list[dict] | None = None,
    highlights: list[dict] | None = None,
    sentiments: list[dict] | None = None,
    total_duration_sec: float = 0.0,
    gemini_key: str = "",
    prompt_context: str | None = None,
    keyterms: list[str] | None = None,
) -> list[dict]:
    """Primary discovery engine: Uses Gemini 2.5 Flash (1M token window) to identify the most viral, complete moments."""
    if not gemini_key or not sentences or len(sentences) < 3:
        return []

    try:
        from google import genai

        client = genai.Client(api_key=gemini_key)
        target_count = calculate_sweet_spot_clip_count(total_duration_sec)

        # Detect content mode for context-aware instructions
        content_mode = detect_content_mode(sentences)
        logger.info("Content mode detected: %s", content_mode)

        # Build formatted transcript with timestamps and speaker labels
        formatted_lines = []
        for s in sentences:
            mins = int(s["start"] // 60)
            secs = int(s["start"] % 60)
            spk = f"Speaker {s['speaker']}" if s.get("speaker") is not None else "Speaker"
            formatted_lines.append(f"[{mins:02d}:{secs:02d}] ({spk}): {s['text']}")
        transcript_text = "\n".join(formatted_lines)

        chapters_context = ""
        if chapters:
            ch_items = [
                f"- [{int(c.get('start', 0)//60):02d}:{int(c.get('start', 0)%60):02d} - {int(c.get('end', 0)//60):02d}:{int(c.get('end', 0)%60):02d}] {c.get('gist', c.get('headline', 'Topic'))}: {c.get('summary', '')[:120]}"
                for c in chapters
            ]
            chapters_context = "VIDEO CHAPTERS & TOPICS:\n" + "\n".join(ch_items)

        hl_context = ""
        if highlights:
            hl_names = [h.get("text", "") for h in highlights[:12] if h.get("text")]
            if hl_names:
                hl_context = f"RECURRING THEMES & HIGHLIGHTS: {', '.join(hl_names)}"

        # Build user context section
        user_context = ""
        if prompt_context:
            user_context += f"\nCONTENT DESCRIPTION (from the creator): {prompt_context}"
        if keyterms:
            user_context += f"\nKEY TOPICS TO PRIORITIZE: {', '.join(keyterms)}"

        # Build content-mode-specific guidance
        if content_mode == "solo":
            mode_guidance = """CONTENT MODE: SOLO CREATOR (single speaker throughout)
This is a single-speaker recording (vlog, monologue, educational content, or solo podcast).
The best viral moments for solo content are:
- Personal confessions, vulnerability, and "I was wrong" admissions
- Hot takes and contrarian opinions stated with conviction
- Emotional intensity shifts — moments where the speaker's energy noticeably rises
- "Aha moment" knowledge drops — when a complex idea clicks into a simple insight
- Story climaxes — the peak moment of a personal anecdote
- Direct-to-camera challenges or calls to action
Since there are no speaker turns or debates, focus on EMOTIONAL ARC and INSIGHT DENSITY."""
        elif content_mode == "dialogue":
            mode_guidance = """CONTENT MODE: CONVERSATION (2 speakers — interview/podcast)
This is a two-speaker conversation. The best viral moments are:
- Heated exchanges or surprising disagreements
- Moments where the guest reveals something unexpected
- Funny reactions and banter that feel authentic
- When an interviewer asks a question that visibly catches the guest off-guard
- Debate pivots — when one person changes the other's mind (or refuses to)
- "Tell me more" moments — when a casual comment reveals a deeper story
Focus on DYNAMIC EXCHANGES and REACTION-WORTHY moments."""
        else:  # panel
            mode_guidance = """CONTENT MODE: PANEL DISCUSSION (3+ speakers)
This is a multi-speaker roundtable or group discussion. The best viral moments are:
- Cross-talk and spontaneous reactions from multiple speakers
- When the group erupts in laughter or visible shock
- Sharp disagreements between panelists with clear opposing views
- When one speaker drops a perspective that silences the room
Focus on GROUP DYNAMICS and ENSEMBLE ENERGY."""

        prompt = f"""You are a master viral short-form content curator and growth strategist for TikTok, YouTube Shorts, and Instagram Reels.
Your objective: Find the {target_count} absolute most viral, captivating, and high-retention short clips from this recording.

{mode_guidance}
{user_context}

{chapters_context}

{hl_context}

FULL TRANSCRIPT WITH TIMESTAMPS:
{transcript_text}

═══════════════════════════════════════════
ANALYSIS APPROACH (follow this step by step):
═══════════════════════════════════════════
1. First, scan the entire transcript to identify the 3-5 major themes or story arcs.
2. For each theme, find the single most compelling moment — the highest emotional peak, sharpest insight, or most engaging exchange.
3. Then look for "hidden gems" between major themes — small moments that are independently viral but easy to overlook (funny asides, unexpected confessions, quotable one-liners).
4. For each candidate clip, verify THREE things before including it:
   a) Does the OPENING hook immediately? (Would a stranger stop scrolling in the first 3 seconds?)
   b) Does the ENDING land satisfyingly? (Punchline, revelation, summary, or natural conclusion?)
   c) Would this make COMPLETE SENSE to someone who has never seen the full video?

═══════════════════════════════════════════
CRITICAL SELECTION RULES:
═══════════════════════════════════════════

1. **THE HOOK (First 3-5 Seconds)** — This is the MOST important factor:
   - Must immediately grab attention and stop thumbs from scrolling.
   - Look for: shocking confessions, controversial claims, intriguing questions, high-stakes revelations, emotional outbursts, or surprising statements.
   - NEVER start on conversational filler ("Um, so yeah, basically...", "Right, so anyway...").
   - NEVER start on admin/logistics ("Before we get into it...", "Let me just say...").
   - The very first sentence should make a viewer think "wait, what?" or "I need to hear this."

2. **SELF-CONTAINED NARRATIVE ARC** — Every clip must tell a complete micro-story:
   - Setup → Tension/Insight → Payoff/Punchline.
   - A random viewer with ZERO context must understand what's happening.
   - NEVER cut into the middle of a story that requires earlier context to understand.

3. **THE ENDING** — Almost as important as the hook:
   - Every clip MUST end on a SATISFYING payoff: a punchline, revelation, summary statement, or natural conclusion.
   - NEVER end on a conjunction ("and", "but", "so", "because"), an unanswered question, or mid-anecdote.
   - NEVER end on a transition ("speaking of which...", "which reminds me...").
   - The viewer should feel a sense of COMPLETION, not "wait, what happened next?"
   - Great endings: "...and that changed everything.", "...that's the real secret.", "...and I never made that mistake again."

4. **CLIP DURATION**:
   - Target 25 to 60 seconds (sweet spot for short-form retention).
   - Up to 75 seconds ONLY for genuinely gripping stories or intense debates.
   - NEVER under 18 seconds — too short feels like a fragment.

5. **DISTRIBUTION & TOPIC DIVERSITY**:
   - Spread the {target_count} clips across different topics and timestamps throughout the ENTIRE recording.
   - Do NOT cluster clips in the same 5-minute window.
   - Each clip should cover a different angle, story, or insight.

6. **EXACT QUOTE ANCHORING**:
   - `startQuote`: Copy-paste the EXACT first 4 to 8 words spoken at the beginning of the clip.
   - `endQuote`: Copy-paste the EXACT last 4 to 8 words spoken at the end of the clip.
   - These MUST be verbatim from the transcript — do NOT paraphrase.

7. **FEATURED GUEST / PRIMARY SPEAKER FOCUS**:
   - In interviews, podcasts, or Q&A videos with a guest, viewers watch to hear the GUEST.
   - Prioritize clips where the primary guest/interviewee speaks at least 65% of the time.
   - NEVER select clips that consist primarily of the host/interviewer giving their own monologue or asking a 30-second question while the guest barely speaks.
   - True dialogue clips where the host and guest actively bounce ideas back and forth are great, but the guest MUST deliver the main payoff/insight.


═══════════════════════════════════════════
SCORE CALIBRATION (be precise and honest):
═══════════════════════════════════════════
- 9.5-9.9: Genuinely makes you stop scrolling and share. Shocking, hilarious, or deeply moving. Only 1-2 clips per video deserve this.
- 9.0-9.4: Very strong. Great hook, clean arc, highly shareable. Top 20% of clips.
- 8.5-8.9: Good clip. Solid content, would perform well but isn't "stop everything" level.
- 8.0-8.4: Decent clip. Fills a topic slot but wouldn't go viral on its own.
- 7.5-7.9: Marginal. Only include if nothing better exists in this topic area.
Do NOT inflate scores — if most clips are 9.5+, the scores are meaningless.

For each clip, return:
- title: Irresistible curiosity-driven headline (max 6-7 words, e.g. "The Rule Every Teen Hates", "Did He Really Say That?").
- hookText: Exactly 1 to 3 BOLD uppercase words for the first 2-second screen overlay (e.g. "WAIT FOR IT", "SHOTS FIRED!", "BIG MISTAKE", "UNREAL", "STOP DOING THIS"). Must NOT end with a question mark.
- startQuote: Exact first 4-8 words of the clip.
- endQuote: Exact last 4-8 words of the clip.
- startTimeSec: Approximate start time (float).
- endTimeSec: Approximate end time (float).
- viralScore: Precise score from 7.5 to 9.9 (e.g. 9.7, 9.4, 8.9) based on hook power, emotional intensity, retention, and shareability.
- viralReason: 1 punchy sentence explaining why this clip will perform.
- description: 2-3 engaging social sentences ending with a question to provoke comments.
- hashtags: 5 trending hashtags (e.g. #shorts #viral #podcast).
- clipType: one of ["hot_take", "funny_exchange", "quotable", "debate", "aha_moment", "storytelling", "mind_blowing_fact"]."""

        schema = {
            "type": "OBJECT",
            "properties": {
                "clips": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING"},
                            "hookText": {"type": "STRING"},
                            "startQuote": {"type": "STRING"},
                            "endQuote": {"type": "STRING"},
                            "startTimeSec": {"type": "NUMBER"},
                            "endTimeSec": {"type": "NUMBER"},
                            "viralScore": {"type": "NUMBER"},
                            "viralReason": {"type": "STRING"},
                            "description": {"type": "STRING"},
                            "hashtags": {"type": "STRING"},
                            "clipType": {"type": "STRING"},
                        },
                        "required": [
                            "title", "hookText", "startQuote", "endQuote",
                            "startTimeSec", "endTimeSec", "viralScore", "viralReason"
                        ],
                    },
                }
            },
            "required": ["clips"],
        }

        response_text = _call_gemini_with_retry(
            client, ["gemini-2.5-flash", "gemini-2.5-pro"], prompt, schema, temperature=0.3
        )
        if not response_text:
            return []

        parsed = json.loads(_strip_markdown_fences(response_text))
        suggestions = parsed.get("clips", [])
        if not isinstance(suggestions, list) or not suggestions:
            return []

        candidates_out = []
        for raw in suggestions:
            approx_s = float(raw.get("startTimeSec", 0.0))
            approx_e = float(raw.get("endTimeSec", approx_s + 35.0))
            start_q = raw.get("startQuote", "")
            end_q = raw.get("endQuote", "")

            start_idx = find_matching_sentence(start_q, approx_s, sentences, is_start=True, search_window_sec=40.0)
            end_idx = find_matching_sentence(end_q, approx_e, sentences, is_start=False, search_window_sec=40.0)

            if end_idx <= start_idx:
                # Ensure at least 15-20s duration
                cur_dur = 0.0
                end_idx = start_idx
                while end_idx < len(sentences) - 1 and cur_dur < 25.0:
                    end_idx += 1
                    cur_dur = sentences[end_idx]["end"] - sentences[start_idx]["start"]

            # Anchor to sentence boundaries
            start_sent = sentences[start_idx]
            end_sent = sentences[end_idx]

            # Prune filler words from the opening sentence
            clip_words_slice = [
                w for w in words
                if w["start"] >= start_sent["start"] - 0.05 and w["end"] <= end_sent["end"] + 0.05
            ]
            pruned_start_sec, pruned_words = prune_leading_fillers(clip_words_slice)
            actual_start_sec = pruned_start_sec
            actual_end_sec = end_sent["end"]
            duration = actual_end_sec - actual_start_sec

            if duration < 15.0:
                # Extend to next sentence if too short
                if end_idx < len(sentences) - 1:
                    end_idx += 1
                    actual_end_sec = sentences[end_idx]["end"]
                    duration = actual_end_sec - actual_start_sec
            elif duration > 80.0:
                # Pull back if excessively long
                while end_idx > start_idx + 1 and (sentences[end_idx]["end"] - actual_start_sec) > 60.0:
                    end_idx -= 1
                actual_end_sec = sentences[end_idx]["end"]
                duration = actual_end_sec - actual_start_sec

            # Weak-ending protection: extend by 1 sentence if ending on a trailing conjunction/preposition
            end_text = sentences[end_idx]["text"]
            end_conclusion = score_sentence_conclusion(end_text)
            if end_conclusion == 0.0 and end_idx < len(sentences) - 1:
                last_word = end_text.split()[-1].strip().lower().rstrip(".,!?;:") if end_text.split() else ""
                if last_word in WEAK_ENDING_WORDS:
                    # Try extending to next sentence if it stays within bounds
                    next_end = sentences[end_idx + 1]["end"]
                    if (next_end - actual_start_sec) <= 80.0:
                        end_idx += 1
                        actual_end_sec = next_end
                        duration = actual_end_sec - actual_start_sec

            # Trailing interruption protection: snap back by 1 sentence if clip ends on a short question/interjection after a pause
            if end_idx > start_idx + 1:
                cur_last_sent = sentences[end_idx]
                cur_prev_sent = sentences[end_idx - 1]
                gap_before_last = cur_last_sent["start"] - cur_prev_sent["end"]
                last_sent_dur = cur_last_sent["end"] - cur_last_sent["start"]
                is_speaker_switch = (
                    cur_last_sent.get("speaker") is not None
                    and cur_prev_sent.get("speaker") is not None
                    and cur_last_sent.get("speaker") != cur_prev_sent.get("speaker")
                )
                is_trailing_q = cur_last_sent["text"].strip().endswith("?")

                if (is_speaker_switch and gap_before_last >= 1.2 and last_sent_dur <= 4.5) or (is_trailing_q and gap_before_last >= 1.5):
                    potential_dur = cur_prev_sent["end"] - actual_start_sec
                    if potential_dur >= 18.0:
                        logger.info(
                            "Snapping end boundary back: trimmed trailing %.1fs interjection (%s) after %.1fs pause",
                            last_sent_dur, cur_last_sent["text"][:30], gap_before_last
                        )
                        end_idx -= 1
                        actual_end_sec = cur_prev_sent["end"]
                        duration = actual_end_sec - actual_start_sec

            if not (15.0 <= duration <= 85.0):
                continue

            # Check overlap against already chosen clips
            if any(clips_overlap_too_much(actual_start_sec, actual_end_sec, c["start_sec"], c["end_sec"]) for c in candidates_out):
                continue

            raw_score = float(raw.get("viralScore", 8.5))
            if raw_score > 10.0:
                raw_score = raw_score / 10.0
            viral_score = round(max(1.0, min(9.9, raw_score)), 1)

            start_ms = int(actual_start_sec * 1000)
            end_ms = int(actual_end_sec * 1000)

            title = normalize_common_stt_homophones(raw.get("title", "Viral Highlight"))
            hook_text = normalize_common_stt_homophones(raw.get("hookText", "WATCH THIS")).upper().rstrip("?")
            if not hook_text:
                hook_text = "WATCH THIS"

            description = normalize_common_stt_homophones(raw.get("description", ""))
            viral_reason = normalize_common_stt_homophones(raw.get("viralReason", "High engagement viral short format."))

            candidates_out.append({
                "id": f"short_clip_{len(candidates_out) + 1}",
                "type": "short",
                "headline": title,
                "title": title,
                "gist": title,
                "summary": description,
                "description": description,
                "hook_quote": hook_text,
                "hookText": hook_text,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "start_sec": actual_start_sec,
                "end_sec": actual_end_sec,
                "startTime": actual_start_sec,
                "endTime": actual_end_sec,
                "duration_seconds": round(duration, 2),
                "viral_score": viral_score,
                "viralScore": viral_score,
                "viralReason": viral_reason,
                "hashtags": raw.get("hashtags", "#shorts #viral #podcast"),
                "clipType": raw.get("clipType", "hot_take"),
                "is_shorts_ready": True,
                "words": build_clip_words(words, start_ms, end_ms),

                "signals": {
                    "source": "gemini_semantic_discovery",
                    "pacing_note": "Curated by Gemini 2.5 Flash for maximum viral retention",
                },
            })

        candidates_out.sort(key=lambda x: x["viral_score"], reverse=True)
        for i, c in enumerate(candidates_out):
            c["id"] = f"short_clip_{i + 1}"

        logger.info(
            "Gemini discovered %d high-potential viral clips (top score: %s)",
            len(candidates_out),
            candidates_out[0]["viral_score"] if candidates_out else "N/A",
        )
        return candidates_out

    except Exception as err:
        logger.warning("Gemini primary discovery failed: %s", err)
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 2: METADATA ENRICHMENT (for heuristic-found clips)
# ═══════════════════════════════════════════════════════════════════════════════


def enrich_clips_with_gemini(
    viral_clips: list[dict],
    words: list[dict],
    full_text: str = "",
    chapters: list[dict] | None = None,
    prompt_context: str | None = None,
    keyterms: list[str] | None = None,
) -> list[dict]:
    """Enrich candidate short clips with Gemini-generated viral scores and social metadata."""
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key or not viral_clips:
        return viral_clips

    try:
        from google import genai

        client = genai.Client(api_key=gemini_key)

        candidate_summaries = []
        for i, c in enumerate(viral_clips):
            s = c.get("start_ms", 0) / 1000.0
            e = c.get("end_ms", 0) / 1000.0
            c_words = " ".join([w["word"] for w in words if w["start"] >= s and w["end"] <= e])
            candidate_summaries.append(
                f"Clip {i + 1} ({s:.1f}s - {e:.1f}s):\nHeadline: {c.get('headline', '')}\nTranscript: {c_words[:1000]}"
            )

        context_snippet = "N/A"
        if chapters:
            ch_lines = [
                f"- {c.get('gist', c.get('headline', ''))} ({c.get('start', 0)/60:.0f}m - {c.get('end', 0)/60:.0f}m): {c.get('summary', '')[:100]}"
                for c in chapters[:12]
            ]
            context_snippet = "Video Chapters Breakdown:\n" + "\n".join(ch_lines)
        elif full_text:
            context_snippet = full_text[:1500]

        # Build user context for enrichment
        user_context_section = ""
        if prompt_context:
            user_context_section += f"\nCONTENT DESCRIPTION: {prompt_context}"
        if keyterms:
            user_context_section += f"\nKEY TOPICS: {', '.join(keyterms)}"

        prompt = f"""You are an expert viral short-form content curator and algorithm specialist for TikTok, IG Reels, and YouTube Shorts.
Analyze these pre-extracted video clips and return a structured JSON object matching the schema.
{user_context_section}

CRITICAL VIRAL GUIDELINES:
- Context: {context_snippet}
- TITLE: Must be an irresistible, scroll-stopping curiosity hook (max 6-7 words). Avoid generic labels. Use psychological hooks, strong emotional statements, contrasts, or surprising quotes.
- HOOKTEXT: Exactly 1 to 3 words in ALL CAPS (e.g. "WAIT FOR IT", "SHOTS FIRED!", "BIG MISTAKE", "UNREAL"). Must NOT end with a question mark.
- VIRALSCORE: Precise viral potential score from 7.0 to 9.9. Be honest — differentiate good from great. Not every clip is a 9.0+.
- VIRALREASON: 1 punchy sentence explaining the algorithmic/psychological trigger.
- DESCRIPTION: 2-3 engaging sentences ending with a question to drive comments.
- HASHTAGS: 5 high-traffic hashtags (e.g. #shorts #viral #podcast).
- CLIPTYPE: one of ["hot_take", "funny_exchange", "quotable", "debate", "aha_moment", "storytelling", "mind_blowing_fact"].

Candidates:
{"\n\n".join(candidate_summaries)}"""

        schema = {
            "type": "OBJECT",
            "properties": {
                "clips": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING"},
                            "hookText": {"type": "STRING"},
                            "viralScore": {"type": "NUMBER"},
                            "viralReason": {"type": "STRING"},
                            "description": {"type": "STRING"},
                            "hashtags": {"type": "STRING"},
                            "clipType": {"type": "STRING"},
                        },
                    },
                }
            },
        }

        response_text = _call_gemini_with_retry(
            client, ["gemini-2.5-flash", "gemini-3.6-flash"], prompt, schema, temperature=0.3
        )

        if response_text:
            parsed = json.loads(_strip_markdown_fences(response_text))
            suggestions = parsed.get("clips", [])
            if isinstance(suggestions, list) and suggestions:
                for i, c in enumerate(viral_clips):
                    gem = suggestions[i] if i < len(suggestions) else {}
                    if gem.get("title"):
                        c["headline"] = gem["title"]
                        c["title"] = gem["title"]
                    if gem.get("hookText"):
                        h_val = gem["hookText"].upper().rstrip("?")
                        c["hook_quote"] = h_val
                        c["hookText"] = h_val
                    if gem.get("viralScore") is not None:
                        try:
                            score_val = float(gem["viralScore"])
                            if score_val > 10.0:
                                score_val = score_val / 10.0
                            score_val = round(max(1.0, min(9.9, score_val)), 1)
                            c["viral_score"] = score_val
                            c["viralScore"] = score_val
                        except (ValueError, TypeError):
                            pass
                    if gem.get("viralReason"):
                        c["viralReason"] = gem["viralReason"]
                    if gem.get("description"):
                        c["summary"] = gem["description"]
                        c["description"] = gem["description"]
                    if gem.get("hashtags"):
                        c["hashtags"] = gem["hashtags"]
                    if gem.get("clipType"):
                        c["clipType"] = gem["clipType"]

                viral_clips.sort(key=lambda x: x.get("viral_score", 0.0), reverse=True)
                for i, c in enumerate(viral_clips):
                    c["id"] = f"short_clip_{i + 1}"

    except Exception as err:
        logger.warning("Gemini enrichment failed: %s", err)

    return viral_clips


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 3: POST-SELECTION VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════


def validate_and_refine_clips_with_gemini(
    clips: list[dict],
    sentences: list[dict],
    words: list[dict],
    full_text: str = "",
    chapters: list[dict] | None = None,
    gemini_key: str = "",
) -> list[dict]:
    """Post-selection validation: Review the final clip set for quality, diversity, and ending strength.

    Returns refined clip list with potentially adjusted scores and flagged weak clips removed.
    This is a lightweight pass (~2-3s with Flash) that catches mistakes the discovery pass missed.
    """
    if not gemini_key or not clips or len(clips) < 2:
        return clips

    try:
        from google import genai

        client = genai.Client(api_key=gemini_key)

        # Build clip summaries for validation
        clip_reviews = []
        for i, c in enumerate(clips):
            s_sec = c.get("start_sec", c.get("start_ms", 0) / 1000.0)
            e_sec = c.get("end_sec", c.get("end_ms", 0) / 1000.0)
            clip_words = [w["word"] for w in words if w["start"] >= s_sec - 0.05 and w["end"] <= e_sec + 0.05]
            opening_words = " ".join(clip_words[:15]) if clip_words else "N/A"
            closing_words = " ".join(clip_words[-15:]) if clip_words else "N/A"
            clip_reviews.append(
                f"Clip {i + 1}: \"{c.get('title', 'Untitled')}\" ({s_sec:.1f}s - {e_sec:.1f}s, {c.get('duration_seconds', e_sec - s_sec):.0f}s)\n"
                f"  Score: {c.get('viral_score', 'N/A')} | Type: {c.get('clipType', 'N/A')}\n"
                f"  Opens with: \"{opening_words}\"\n"
                f"  Ends with: \"{closing_words}\""
            )

        chapters_summary = ""
        if chapters:
            ch_names = [c.get("gist", c.get("headline", "Topic")) for c in chapters[:10]]
            chapters_summary = f"\nVideo topics: {', '.join(ch_names)}"

        prompt = f"""You are a quality assurance editor reviewing a set of {len(clips)} short-form viral clips extracted from a video.
{chapters_summary}

CLIPS TO REVIEW:
{chr(10).join(clip_reviews)}

For each clip, evaluate:
1. HOOK QUALITY: Does it start with something attention-grabbing, or with filler/admin?
2. ENDING QUALITY: Does it end on a satisfying conclusion, or trail off mid-thought?
3. STANDALONE: Would a random viewer understand this without context?
4. TOPIC OVERLAP: Does it cover the same ground as another clip in the set?
5. GUEST FOCUS: In an interview or podcast with a guest, does the clip consist mostly of the host talking? Flag "interviewer_dominated" and set keep=false.
6. TRAILING DRIFT / INTERRUPTIONS: If a clip has great content but trails off into a rambling tangent, question, or interruption at the very end, specify trimEndSeconds (number, e.g. 3.5) to cleanly prune that trailing tail. 0 if no trim needed.

Then return a JSON object with:
- validatedClips: array of objects, one per input clip (same order), each with:
  - clipIndex (int): 0-based index of the clip
  - keep (bool): true if the clip should be kept, false if it should be dropped
  - adjustedScore (number): your honest re-assessment of viral potential (7.0-9.9). Lower scores for clips with weak hooks/endings.
  - trimEndSeconds (number): seconds to trim off the end (0 if no trim needed).
  - issueFlags (array of strings): any issues found, e.g. ["weak_hook", "mid_thought_ending", "interviewer_dominated", "topic_overlap_with_clip_3", "needs_context"]
  - notes (string): brief explanation of your assessment"""

        schema = {
            "type": "OBJECT",
            "properties": {
                "validatedClips": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "clipIndex": {"type": "INTEGER"},
                            "keep": {"type": "BOOLEAN"},
                            "adjustedScore": {"type": "NUMBER"},
                            "trimEndSeconds": {"type": "NUMBER"},
                            "issueFlags": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "notes": {"type": "STRING"},
                        },
                        "required": ["clipIndex", "keep", "adjustedScore"],
                    },
                }
            },
            "required": ["validatedClips"],
        }

        response_text = _call_gemini_with_retry(
            client, ["gemini-2.5-flash"], prompt, schema, temperature=0.2
        )

        if not response_text:
            logger.info("Validation pass skipped (no Gemini response). Returning clips as-is.")
            return clips

        parsed = json.loads(_strip_markdown_fences(response_text))
        validated = parsed.get("validatedClips", [])
        if not isinstance(validated, list) or not validated:
            return clips

        # Apply validation results
        kept_clips = []
        dropped_count = 0
        for v in validated:
            idx = v.get("clipIndex", -1)
            if idx < 0 or idx >= len(clips):
                continue

            clip = clips[idx]
            keep = v.get("keep", True)
            flags = v.get("issueFlags", [])
            adjusted = v.get("adjustedScore")
            notes = v.get("notes", "")

            # If flagged as interviewer_dominated, drop the clip
            if "interviewer_dominated" in flags and len(clips) > 2:
                keep = False

            if not keep:
                dropped_count += 1
                logger.info("Validation dropped clip %d (%s): %s (flags: %s)", idx + 1, clip.get("title", ""), notes, flags)
                continue

            # Apply active trim if validator recommended trimming trailing seconds
            trim_sec = float(v.get("trimEndSeconds") or 0.0)
            if 1.0 <= trim_sec <= 10.0:
                new_end_sec = clip["end_sec"] - trim_sec
                if new_end_sec - clip["start_sec"] >= 18.0:
                    logger.info("Validation actively trimming %.1fs from end of clip %d based on validator assessment", trim_sec, idx + 1)
                    clip["end_sec"] = round(new_end_sec, 2)
                    clip["endTime"] = clip["end_sec"]
                    clip["end_ms"] = int(round(clip["end_sec"] * 1000))
                    clip["duration_seconds"] = round(clip["end_sec"] - clip["start_sec"], 2)
                    clip["words"] = build_clip_words(words, clip["start_ms"], clip["end_ms"])


            # Apply adjusted score if provided and reasonable
            if adjusted is not None:
                try:
                    adj_score = float(adjusted)
                    if adj_score > 10.0:
                        adj_score = adj_score / 10.0
                    adj_score = round(max(1.0, min(9.9, adj_score)), 1)
                    clip["viral_score"] = adj_score
                    clip["viralScore"] = adj_score
                except (ValueError, TypeError):
                    pass

            # Store validation metadata
            if flags:
                clip.setdefault("signals", {})["validation_flags"] = flags
            if notes:
                clip.setdefault("signals", {})["validation_notes"] = notes

            kept_clips.append(clip)

        if not kept_clips:
            # Don't return empty — fall back to original clips if validation was too aggressive
            logger.warning("Validation dropped ALL clips. Returning originals.")
            return clips

        # Re-sort and re-index
        kept_clips.sort(key=lambda x: x.get("viral_score", 0.0), reverse=True)
        for i, c in enumerate(kept_clips):
            c["id"] = f"short_clip_{i + 1}"

        logger.info(
            "Validation complete: %d clips kept, %d dropped, top score: %s",
            len(kept_clips), dropped_count,
            kept_clips[0]["viral_score"] if kept_clips else "N/A",
        )
        return kept_clips

    except Exception as err:
        logger.warning("Gemini validation failed: %s. Returning clips as-is.", err)
        return clips

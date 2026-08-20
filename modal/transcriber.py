"""Audio transcriber Modal service.

Downloads audio from a URL (YouTube via yt-dlp, anything else via HTTP),
extracts a 16 kHz mono WAV with FFmpeg, and submits it to AssemblyAI for
speaker-diarized transcription.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile

import modal

from config import ai_secret, app, image, youtube_cookies_secret
from errors import DownloadError, InvalidInputError, RenderError, TranscriptionError
from models import TranscribeRequest
from utils import StageTimer, is_youtube_url, validate_url
from ytdlp_helper import download_youtube_audio, remove_bgutil_pot_provider

logger = logging.getLogger("makemyclip.transcriber")


@app.cls(
    image=image,
    timeout=3600,
    secrets=[ai_secret, youtube_cookies_secret],
)
class AudioTranscriber:
    @modal.enter()
    def setup(self):
        # Each Modal @app.cls runs in its own container, so removing the bgutil
        # PO Token plugin here does not affect AIReframe (which may need it).
        remove_bgutil_pot_provider()

    @modal.fastapi_endpoint(method="POST")
    def transcribe(self, req: TranscribeRequest):
        """Transcribe audio from a video URL with speaker diarization."""
        import assemblyai as aai
        import requests

        logger.info("=== TRANSCRIBE REQUEST ===")
        logger.info("video_url: %s...", req.video_url[:100])

        # --- Validate inputs ---
        vurl = validate_url(req.video_url, label="video_url")

        # Configure AssemblyAI key
        aai.settings.api_key = os.environ.get("ASSEMBLYAI_API_KEY")
        if not aai.settings.api_key:
            raise InvalidInputError(
                "ASSEMBLYAI_API_KEY environment variable is missing in Modal secret"
            )

        with tempfile.TemporaryDirectory() as tmpdir:

            # 1. Download source media
            with StageTimer("download_media"):
                if is_youtube_url(vurl):
                    logger.info(
                        "YouTube URL detected. Downloading audio only via yt-dlp..."
                    )
                    local_media = download_youtube_audio(vurl, tmpdir)
                    logger.info("YouTube audio downloaded to: %s", local_media)
                else:
                    logger.info("Remote URL detected. Downloading directly...")
                    local_media = os.path.join(tmpdir, "input_media")
                    try:
                        with requests.get(vurl, stream=True, timeout=120) as r:
                            r.raise_for_status()
                            with open(local_media, "wb") as f:
                                for chunk in r.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                    except requests.RequestException as e:
                        raise DownloadError(
                            f"Failed to download media: {e}"
                        ) from e
                    logger.info("Remote file downloaded successfully.")

            # 2. Extract a clean 16 kHz mono WAV
            with StageTimer("extract_audio"):
                local_wav = os.path.join(tmpdir, "transcription_audio.wav")
                logger.info("Extracting/converting audio with FFmpeg...")
                cmd = [
                    "ffmpeg", "-y",
                    "-i", local_media,
                    "-ac", "1",
                    "-ar", "16000",
                    "-vn",
                    local_wav,
                ]
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=300
                )
                if result.returncode != 0:
                    raise RenderError(
                        f"FFmpeg audio extraction failed: {result.stderr[-500:]}"
                    )
                logger.info(
                    "Audio extraction successful: %s bytes",
                    f"{os.path.getsize(local_wav):,}",
                )

            # 3. Transcribe via AssemblyAI
            with StageTimer("transcribe_assemblyai"):
                logger.info(
                    "Submitting to AssemblyAI (transcribe_lang=%s, translate_lang=%s)...",
                    req.transcribe_language,
                    req.translate_language,
                )
                
                config_kwargs = {
                    "speech_models": ["universal-3-5-pro", "universal-2"],
                    "speaker_labels": True,
                    "disfluencies": True,
                    "auto_chapters": True,
                    "auto_highlights": True,
                    "sentiment_analysis": True,
                    "filter_profanity": True,
                }
                
                if req.transcribe_language and req.transcribe_language != "auto":
                    config_kwargs["language_code"] = req.transcribe_language
                else:
                    config_kwargs["language_detection"] = True
                    
                if req.translate_language and req.translate_language != "none":
                    config_kwargs["speech_understanding"] = aai.SpeechUnderstandingRequest(
                        request=aai.SpeechUnderstandingFeatureRequests(
                            translation=aai.TranslationRequest(
                                target_languages=[req.translate_language],
                                match_original_utterance=True
                            )
                        )
                    )

                default_prompt = (
                    "Video or podcast recording with spoken dialogue, key topics, and discussions."
                )
                config_kwargs["prompt"] = req.prompt if getattr(req, "prompt", None) else default_prompt
                if getattr(req, "keyterms", None):
                    config_kwargs["keyterms_prompt"] = req.keyterms

                config = aai.TranscriptionConfig(**config_kwargs)

                transcriber = aai.Transcriber(config=config)
                transcript = transcriber.transcribe(local_wav)

                if transcript.status == aai.TranscriptStatus.error:
                    logger.error("AssemblyAI error: %s", transcript.error)
                    raise TranscriptionError(
                        f"AssemblyAI transcription failed: {transcript.error}"
                    )

                logger.info(
                    "Transcription successful. Length: %d chars",
                    len(transcript.text),
                )

            # 4. Map words to sequential speaker IDs and convert ms → seconds
            words = []
            speaker_map = {}
            next_speaker_id = 0
            paragraphs = []
            full_text = transcript.text

            target_lang = req.translate_language
            has_translation = False
            if target_lang and target_lang != "none":
                translated_texts = getattr(transcript, "translated_texts", None)
                if translated_texts and target_lang in translated_texts:
                    has_translation = True

            if has_translation:
                full_text = transcript.translated_texts[target_lang]
                utterances = getattr(transcript, "utterances", None)
                if utterances:
                    for utt in utterances:
                        speaker_id = None
                        if utt.speaker:
                            if utt.speaker not in speaker_map:
                                speaker_map[utt.speaker] = next_speaker_id
                                next_speaker_id += 1
                            speaker_id = speaker_map[utt.speaker]

                        utt_translation = utt.translated_texts.get(target_lang, "") if utt.translated_texts else ""
                        if not utt_translation:
                            continue

                        utt_words = utt_translation.split()
                        num_words = len(utt_words)
                        if num_words == 0:
                            continue

                        start_sec = utt.start / 1000.0
                        end_sec = utt.end / 1000.0
                        duration = end_sec - start_sec
                        word_duration = duration / num_words

                        for idx, word_text in enumerate(utt_words):
                            w_start = start_sec + (idx * word_duration)
                            w_end = w_start + word_duration
                            words.append({
                                "word": word_text,
                                "start": w_start,
                                "end": w_end,
                                "confidence": 0.99,
                                "speaker": speaker_id,
                            })

                    paragraphs = [
                        utt.translated_texts.get(target_lang, "")
                        for utt in utterances
                        if utt.translated_texts and utt.translated_texts.get(target_lang, "")
                    ]

                if not words:
                    all_words = full_text.split()
                    num_words = len(all_words)
                    if num_words > 0:
                        total_duration = 0.0
                        if transcript.words:
                            total_duration = transcript.words[-1].end / 1000.0
                        else:
                            total_duration = 30.0
                        word_duration = total_duration / num_words
                        for idx, word_text in enumerate(all_words):
                            words.append({
                                "word": word_text,
                                "start": idx * word_duration,
                                "end": (idx + 1) * word_duration,
                                "confidence": 0.99,
                                "speaker": 0,
                            })

                if not paragraphs:
                    paragraphs = [full_text]
            else:
                for w in transcript.words:
                    speaker_id = None
                    if w.speaker:
                        if w.speaker not in speaker_map:
                            speaker_map[w.speaker] = next_speaker_id
                            next_speaker_id += 1
                        speaker_id = speaker_map[w.speaker]

                    words.append(
                        {
                            "word": w.text,
                            "start": w.start / 1000.0,
                            "end": w.end / 1000.0,
                            "confidence": w.confidence,
                            "speaker": speaker_id,
                        }
                    )
                paragraphs = [p.text for p in transcript.get_paragraphs()]

            # Extract audio intelligence metrics (sentiments, chapters, highlights)
            sentiments_out = []
            if getattr(transcript, "sentiment_analysis", None):
                for s in transcript.sentiment_analysis:
                    sentiments_out.append({
                        "text": s.text,
                        "start": s.start / 1000.0,
                        "end": s.end / 1000.0,
                        "sentiment": s.sentiment,
                        "confidence": round(s.confidence, 4),
                    })

            chapters_out = []
            if getattr(transcript, "chapters", None):
                for c in transcript.chapters:
                    chapters_out.append({
                        "headline": c.headline,
                        "summary": c.summary,
                        "gist": c.gist,
                        "start": c.start / 1000.0,
                        "end": c.end / 1000.0,
                    })

            highlights_out = []
            raw_hl = getattr(transcript.auto_highlights, "results", []) if getattr(transcript, "auto_highlights", None) else []
            for h in raw_hl:
                highlights_out.append({
                    "text": h.text,
                    "count": h.count,
                    "rank": h.rank,
                    "timestamps": [{"start": t.start / 1000.0, "end": t.end / 1000.0} for t in getattr(h, "timestamps", [])],
                })

            # Multi-signal viral short clip scoring engine (AssemblyAI Audio Intelligence + Chapters)
            total_duration = words[-1]["end"] - words[0]["start"] if words else 0.0
            velocity_timeline = calculate_speech_velocity(words)
            acoustic_events = extract_acoustic_events(words, full_text)
            viral_clips_out = score_and_rank_short_clips(
                sentiments=sentiments_out,
                acoustic_events=acoustic_events,
                highlights=highlights_out,
                velocity_timeline=velocity_timeline,
                words=words,
                total_duration_sec=total_duration,
                chapters=chapters_out,
            )

            # Enrich with Gemini social metadata only if clips weren't AI-discovered
            # (AI-discovered clips already include title, hookText, hashtags, etc.)
            if not any(c.get("_ai_discovered") for c in viral_clips_out):
                viral_clips_out = enrich_clips_with_gemini(
                    viral_clips_out, words, full_text=full_text, chapters=chapters_out
                )
            else:
                for c in viral_clips_out:
                    c.pop("_ai_discovered", None)

            logger.info(
                "Returning %d words, %d paragraphs, %d speakers, %d sentiments, %d chapters, %d short viral clips",
                len(words),
                len(paragraphs),
                len(speaker_map),
                len(sentiments_out),
                len(chapters_out),
                len(viral_clips_out),
            )

            return {
                "success": True,
                "fullText": full_text,
                "words": words,
                "paragraphs": paragraphs,
                "sentiments": sentiments_out,
                "chapters": chapters_out,
                "highlights": highlights_out,
                "viralClips": viral_clips_out,
            }


def enrich_clips_with_gemini(
    viral_clips: list[dict],
    words: list[dict],
    full_text: str = "",
    chapters: list[dict] | None = None,
) -> list[dict]:
    """Enrich candidate short clips with Gemini-generated social metadata (title, hook, hashtags, etc.)."""
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key or not viral_clips:
        logger.info("GEMINI_API_KEY missing or no viral clips to enrich. Skipping Gemini enrichment.")
        return viral_clips

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=gemini_key)

        candidate_summaries = []
        for i, c in enumerate(viral_clips):
            s = c.get("start_ms", 0) / 1000.0
            e = c.get("end_ms", 0) / 1000.0
            c_words = " ".join([w["word"] for w in words if w["start"] >= s and w["end"] <= e])
            candidate_summaries.append(
                f"Clip {i + 1} ({s:.1f}s - {e:.1f}s):\nHeadline: {c.get('headline', '')}\nTranscript: {c_words[:600]}"
            )

        if chapters and len(chapters) > 0:
            ch_lines = [
                f"- {c.get('gist', c.get('headline', ''))} ({c.get('start', 0)/60:.0f}m - {c.get('end', 0)/60:.0f}m): {c.get('summary', '')[:100]}"
                for c in chapters[:12]
            ]
            context_snippet = "Video Chapters Breakdown:\n" + "\n".join(ch_lines)
        elif full_text:
            context_snippet = full_text[:1500]
        else:
            context_snippet = "N/A"

        prompt = f"""You are an expert social media editor for TikTok, IG Reels, and YouTube Shorts.
Analyze these pre-extracted viral video clip candidates and return a JSON object matching the schema.

CRITICAL ACCURACY & CONTEXT RULES:
- Overall Video Context Snippet: {context_snippet}
- Rely ONLY on the actual transcript context to determine who is speaking or being discussed.
- DO NOT hallucinate famous podcasters or celebrity names (such as Joe Rogan, Andrew Huberman, Lex Fridman, etc.) UNLESS they are explicitly mentioned by name in the transcript.
- Match titles, descriptions, and hashtags strictly to the actual speakers and content of the video.

For each candidate clip, generate:
- title: Short, curiosity-inducing clickbait title (max 7 words)
- hookText: Bold 1-3 word scroll-stopping caption for the first 3 seconds
- viralReason: 1 sentence explaining why this clip will go viral
- description: Engaging social media post description
- hashtags: Top 5 space-separated hashtags (e.g. #shorts #viral)
- clipType: one of ["hot_take", "funny_exchange", "quotable", "debate", "aha_moment"]

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
                            "viralReason": {"type": "STRING"},
                            "description": {"type": "STRING"},
                            "hashtags": {"type": "STRING"},
                            "clipType": {"type": "STRING"},
                        },
                    },
                }
            },
        }

        models_to_try = ["gemini-2.5-flash", "gemini-2.5-pro"]
        response_text = None

        for model in models_to_try:
            try:
                res = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                        temperature=0.3,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(
                            disable=True
                        ),
                    ),
                )
                if res.text:
                    response_text = res.text
                    break
            except Exception as e:
                logger.warning("Gemini model %s failed: %s", model, e)
                continue

        if response_text:
            import json
            parsed = json.loads(response_text)
            suggestions = parsed.get("clips", [])
            if isinstance(suggestions, list) and suggestions:
                for i, c in enumerate(viral_clips):
                    gem = suggestions[i] if i < len(suggestions) else {}
                    if gem.get("title"):
                        c["headline"] = gem["title"]
                        c["title"] = gem["title"]
                    if gem.get("hookText"):
                        c["hook_quote"] = gem["hookText"]
                        c["hookText"] = gem["hookText"]
                    if gem.get("viralReason"):
                        c["viralReason"] = gem["viralReason"]
                    if gem.get("description"):
                        c["summary"] = gem["description"]
                        c["description"] = gem["description"]
                    if gem.get("hashtags"):
                        c["hashtags"] = gem["hashtags"]
                    if gem.get("clipType"):
                        c["clipType"] = gem["clipType"]
                logger.info("Successfully enriched %d clips with Gemini metadata directly in Modal transcriber.", len(viral_clips))
    except Exception as err:
        logger.warning("Gemini enrichment in Modal transcriber failed, proceeding with AssemblyAI defaults: %s", err)

    return viral_clips


def calculate_speech_velocity(words: list, window_seconds: float = 5.0) -> list[dict]:
    if not words:
        return []
    min_time = words[0]["start"]
    max_time = words[-1]["end"]
    timeline = []
    current_time = min_time
    step = 2.5
    while current_time < max_time:
        win_start = current_time
        win_end = current_time + window_seconds
        win_words = [w for w in words if w["start"] >= win_start and w["end"] <= win_end]
        count = len(win_words)
        wpm = (count / window_seconds) * 60.0
        timeline.append({
            "window_start_ms": int(win_start * 1000),
            "window_end_ms": int(win_end * 1000),
            "word_count": count,
            "wpm": round(wpm, 1),
        })
        current_time += step
    return timeline


def extract_acoustic_events(words: list, full_text: str) -> list[dict]:
    import re
    pattern = re.compile(r"\[(laughter|cheering|gasp|applause|sigh)\]", re.IGNORECASE)
    events = []
    for w in words:
        match = pattern.search(w["word"])
        if match:
            events.append({
                "event": match.group(1).lower(),
                "text": w["word"],
                "start_ms": int(w["start"] * 1000),
                "end_ms": int(w["end"] * 1000),
                "speaker": w.get("speaker"),
            })
    return events


# ═══════════════════════════════════════════════════════════════════════════════
# OPUSCLIP-GRADE INTELLIGENT VIRAL CLIP EXTRACTION ENGINE
#
# Pipeline:
#   1. PRIMARY:  Gemini AI discovers self-contained viral moments from the
#                full transcript (understands narrative, hooks, payoffs).
#   2. FALLBACK: Enhanced multi-signal heuristics with boundary snapping,
#                speaker exchange detection, and velocity spike analysis.
#   3. ALWAYS:   Natural boundary snapping (never cut mid-sentence) and
#                temporal diversity via penalty-based greedy selection.
# ═══════════════════════════════════════════════════════════════════════════════


def _fmt_ts(seconds: float) -> str:
    """Format seconds as MM:SS for AI-readable transcript."""
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def _format_transcript_for_ai(
    words: list, chapters: list | None = None, max_chars: int = 50000
) -> str:
    """Build a timestamped, speaker-labeled transcript for Gemini analysis.

    Produces lines like:  [MM:SS] Speaker N: Sentence text here.
    """
    if not words:
        return ""

    lines: list[str] = []
    cur_speaker = None
    cur_tokens: list[str] = []
    line_start = 0.0

    def _flush():
        nonlocal cur_tokens, cur_speaker, line_start
        if cur_tokens:
            spk = f"Speaker {cur_speaker}" if cur_speaker is not None else "Speaker"
            lines.append(f"[{_fmt_ts(line_start)}] {spk}: {' '.join(cur_tokens)}")
            cur_tokens = []

    for w in words:
        speaker = w.get("speaker")
        if speaker != cur_speaker and cur_tokens:
            _flush()
            line_start = w["start"]
            cur_speaker = speaker
        elif not cur_tokens:
            line_start = w["start"]
            cur_speaker = speaker

        cur_tokens.append(w["word"])

        # Flush on sentence boundary when line has enough words
        if w["word"].rstrip().endswith((".", "?", "!")) and len(cur_tokens) >= 4:
            _flush()

    _flush()

    # Prepend chapter context if available
    header = ""
    if chapters:
        ch_lines = [
            f"  [{_fmt_ts(c.get('start', 0))}-{_fmt_ts(c.get('end', 0))}] "
            f"{c.get('headline', '')} — {c.get('summary', '')[:120]}"
            for c in chapters[:15]
        ]
        header = "VIDEO CHAPTERS:\n" + "\n".join(ch_lines) + "\n\nFULL TRANSCRIPT:\n"

    result = header + "\n".join(lines)

    # Proportional truncation preserving start, middle, and end
    if len(result) > max_chars:
        third = max_chars // 3
        mid = len(result) // 2 - third // 2
        result = (
            result[:third]
            + "\n\n... [TRANSCRIPT CONTINUES] ...\n\n"
            + result[mid : mid + third]
            + "\n\n... [TRANSCRIPT CONTINUES] ...\n\n"
            + result[-third:]
        )

    return result


def _find_natural_boundaries(words: list) -> list[dict]:
    """Detect natural cut points: sentence ends, pauses, speaker turns.

    Returns sorted list of ``{time, type, strength}`` dicts (strength 0-1).
    """
    if not words:
        return []

    boundaries: list[dict] = []
    for i, w in enumerate(words):
        t = w["end"]
        text = w["word"].rstrip()

        # Strong boundary: sentence end
        if text.endswith((".", "?", "!")):
            boundaries.append({"time": t, "type": "sentence_end", "strength": 1.0})
        # Weak boundary: clause end
        elif text.endswith((",", ";", ":")):
            boundaries.append({"time": t, "type": "clause_end", "strength": 0.5})

        if i < len(words) - 1:
            gap = words[i + 1]["start"] - w["end"]
            # Natural pause (> 400 ms)
            if gap > 0.4:
                boundaries.append(
                    {"time": t, "type": "pause", "strength": min(1.0, gap / 2.0)}
                )
            # Speaker turn
            if (
                w.get("speaker") is not None
                and w.get("speaker") != words[i + 1].get("speaker")
            ):
                boundaries.append({"time": t, "type": "speaker_turn", "strength": 0.9})

    boundaries.sort(key=lambda b: b["time"])
    return boundaries


def _snap_to_boundary(
    target: float,
    boundaries: list[dict],
    direction: str = "nearest",
    max_shift: float = 3.0,
) -> float:
    """Snap *target* to the highest-quality nearby boundary.

    *direction*: ``"nearest"``, ``"before"``, or ``"after"``.
    """
    best_time = target
    best_score = -1.0

    for b in boundaries:
        dist = abs(b["time"] - target)
        if dist > max_shift:
            continue
        if direction == "before" and b["time"] > target + 0.1:
            continue
        if direction == "after" and b["time"] < target - 0.1:
            continue

        score = b["strength"] * 0.6 + (1.0 - dist / max_shift) * 0.4
        if score > best_score:
            best_score = score
            best_time = b["time"]

    return best_time


def _build_clip_words(words: list, start_ms: int, end_ms: int) -> list[dict]:
    """Extract words within a clip range and rebase timestamps to clip-relative."""
    start_sec = start_ms / 1000.0
    return [
        {
            "word": w["word"].strip().lower(),
            "punctuated_word": w["word"].strip(),
            "start": round(max(0.0, w["start"] - start_sec), 3),
            "end": round(max(0.05, w["end"] - start_sec), 3),
            "confidence": round(w.get("confidence", 0.99), 3),
            "speaker": str(w.get("speaker", 0)),
        }
        for w in words
        if start_ms <= int(w["start"] * 1000) <= end_ms
    ]


# ---------------------------------------------------------------------------
# PRIMARY PATH: Gemini-powered clip discovery
# ---------------------------------------------------------------------------

def _discover_clips_with_ai(
    words: list,
    chapters: list | None,
    sentiments: list,
    highlights: list,
    total_duration_sec: float,
    target_clip_count: int,
    boundaries: list[dict],
) -> list[dict] | None:
    """Use Gemini to intelligently discover self-contained viral moments.

    Returns ``None`` when Gemini is unavailable so the caller falls back to
    heuristics.
    """
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key or not words:
        logger.info("GEMINI_API_KEY missing or no words — skipping AI clip discovery.")
        return None

    try:
        from google import genai
        from google.genai import types
        import json

        client = genai.Client(api_key=gemini_key)

        transcript_text = _format_transcript_for_ai(words, chapters)
        duration_min = total_duration_sec / 60.0

        # ── Build signal summary ──
        signal_ctx = ""
        if sentiments:
            pos = sum(1 for s in sentiments if s.get("sentiment") == "POSITIVE")
            neg = sum(1 for s in sentiments if s.get("sentiment") == "NEGATIVE")
            signal_ctx += f"\nSENTIMENT OVERVIEW: {pos} positive, {neg} negative segments."

            peaks = sorted(
                [s for s in sentiments if s.get("sentiment") != "NEUTRAL"],
                key=lambda s: s.get("confidence", 0),
                reverse=True,
            )[:10]
            if peaks:
                peak_lines = [
                    f"  [{_fmt_ts(p['start'])}] {p['sentiment']} (conf={p['confidence']:.2f}): "
                    f"\"{p['text'][:60]}\""
                    for p in peaks
                ]
                signal_ctx += "\nTOP EMOTIONAL PEAKS:\n" + "\n".join(peak_lines)

        if highlights:
            top_hl = sorted(highlights, key=lambda h: h.get("rank", 0), reverse=True)[:8]
            hl_lines = [f"  \"{h['text']}\" (×{h.get('count', 0)})" for h in top_hl]
            signal_ctx += "\nKEY PHRASES:\n" + "\n".join(hl_lines)

        request_count = min(target_clip_count + 4, 20)

        prompt = f"""You are an expert viral video clip curator at the level of OpusClip. Find the {request_count} most engaging, self-contained moments from this {duration_min:.0f}-minute video transcript that will perform exceptionally on TikTok, Instagram Reels, and YouTube Shorts.

CRITICAL SELECTION RULES:

1. SELF-CONTAINED: Each clip MUST make complete sense on its own. A viewer who has never seen the full video must fully understand it. Never include clips that say "as I was saying" or reference unseen context.

2. STRONG HOOK (first 3 seconds): A bold statement, surprising fact, provocative question, emotional outburst, or funny setup. If the opening line is boring, find a better start point.

3. COMPLETE ARC: Setup → Development → Payoff/Punchline. Never end mid-thought.

4. TEMPORAL DIVERSITY: Spread clips across the ENTIRE video.
   - At least 25% from the first third
   - At least 25% from the middle third
   - At least 25% from the final third

5. CONTENT VARIETY: Mix clip types — funny, educational, emotional, surprising, controversial.

6. NATURAL BOUNDARIES: Start at sentence beginnings or speaker turns. End at complete thoughts. NEVER cut mid-sentence.

7. DURATION: 20-55 seconds each.
   - 20-30s: punchlines, hot takes, quotable moments
   - 30-45s: stories, explanations, debates
   - 45-55s: only for exceptional multi-part narratives

VIRAL CLIP PATTERNS:
- Bold/controversial opinions ("hot takes")
- Genuinely funny moments or unexpected humor
- "Aha!" moments that change how you think
- Raw emotion — passion, anger, joy, vulnerability
- Counter-intuitive or contrarian advice
- Relatable experiences told compellingly
- Back-and-forth dialogue (Q&A, debates, banter)
- Memorable one-liners or quotable phrases
- Mini-stories with setup and payoff
- Reaction moments (laughter, surprise, disbelief)

AVOID:
- References to earlier unseen context
- Monotone monologues without energy shifts
- Clips ending mid-sentence or mid-thought
- Generic intros, outros, or housekeeping ("subscribe", "check the link")
- Content requiring visual context
- Multiple clips covering the same moment
{signal_ctx}

VIDEO DURATION: {duration_min:.1f} minutes ({total_duration_sec:.0f} seconds)

{transcript_text}

For EACH clip provide exact start/end timestamps in seconds matching the transcript, a virality score (0-100), and social media metadata."""

        schema = {
            "type": "OBJECT",
            "properties": {
                "clips": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "start_seconds": {"type": "NUMBER"},
                            "end_seconds": {"type": "NUMBER"},
                            "virality_score": {"type": "INTEGER"},
                            "clip_type": {"type": "STRING"},
                            "title": {"type": "STRING"},
                            "hookText": {"type": "STRING"},
                            "viralReason": {"type": "STRING"},
                            "description": {"type": "STRING"},
                            "hashtags": {"type": "STRING"},
                            "self_contained_check": {"type": "STRING"},
                        },
                    },
                }
            },
        }

        models_to_try = ["gemini-2.5-flash", "gemini-2.5-pro"]
        response_text = None

        for model in models_to_try:
            try:
                res = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                        temperature=0.4,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(
                            disable=True
                        ),
                    ),
                )
                if res.text:
                    response_text = res.text
                    logger.info("AI clip discovery succeeded with model: %s", model)
                    break
            except Exception as e:
                logger.warning("Gemini model %s failed for clip discovery: %s", model, e)
                continue

        if not response_text:
            logger.warning("All Gemini models failed — falling back to heuristics.")
            return None

        raw_clips = json.loads(response_text).get("clips", [])
        if not raw_clips:
            logger.warning("Gemini returned no clips — falling back to heuristics.")
            return None

        # ── Post-process & validate ──
        final: list[dict] = []
        for rc in raw_clips:
            raw_s = float(rc.get("start_seconds", 0))
            raw_e = float(rc.get("end_seconds", 0))

            if raw_s < 0 or raw_e <= raw_s or raw_s >= total_duration_sec:
                continue
            raw_e = min(raw_e, total_duration_sec)
            if not (12.0 <= raw_e - raw_s <= 70.0):
                continue

            # Snap to natural speech boundaries
            snapped_s = _snap_to_boundary(raw_s, boundaries, "before", 3.0)
            snapped_e = _snap_to_boundary(raw_e, boundaries, "after", 3.0)

            dur = snapped_e - snapped_s
            if dur < 15.0:
                snapped_e = snapped_s + max(20.0, raw_e - raw_s)
            elif dur > 60.0:
                snapped_e = snapped_s + min(55.0, raw_e - raw_s)

            s_ms = int(snapped_s * 1000)
            e_ms = int(snapped_e * 1000)
            dur_sec = (e_ms - s_ms) / 1000.0

            # Overlap guard
            if any(abs(c["start_ms"] - s_ms) < 10000 for c in final):
                continue

            clip_words = _build_clip_words(words, s_ms, e_ms)
            if not clip_words:
                continue

            h_text = " ".join(w["punctuated_word"] for w in clip_words[:6])
            virality = min(100, max(60, int(rc.get("virality_score", 80))))
            title = rc.get("title", f"Viral Moment {len(final) + 1}")
            hook = rc.get("hookText", h_text)

            final.append({
                "id": f"short_clip_{len(final) + 1}",
                "type": "short",
                "headline": title,
                "title": title,
                "summary": rc.get("description", ""),
                "description": rc.get("description", ""),
                "gist": rc.get("clip_type", "viral_moment"),
                "hook_quote": hook,
                "hookText": hook,
                "start_ms": s_ms,
                "end_ms": e_ms,
                "duration_seconds": round(dur_sec, 2),
                "viral_score": float(virality),
                "is_shorts_ready": True,
                "words": clip_words,
                "viralReason": rc.get("viralReason", ""),
                "hashtags": rc.get("hashtags", ""),
                "clipType": rc.get("clip_type", "quotable"),
                "_ai_discovered": True,
                "signals": {
                    "source": "ai_discovery",
                    "self_contained_check": rc.get("self_contained_check", ""),
                    "speakers_count": len(
                        set(w.get("speaker") for w in clip_words if w.get("speaker"))
                    ),
                    "pacing_note": "AI-powered OpusClip-grade selection",
                },
            })

        if not final:
            logger.warning("No valid clips after post-processing — falling back.")
            return None

        final = _select_with_diversity(final, total_duration_sec, target_clip_count)
        logger.info(
            "AI clip discovery produced %d clips (target %d).",
            len(final),
            target_clip_count,
        )
        return final

    except Exception as e:
        logger.warning("Gemini clip discovery failed — falling back: %s", e)
        return None


# ---------------------------------------------------------------------------
# FALLBACK PATH: Enhanced multi-signal heuristics
# ---------------------------------------------------------------------------

def _generate_heuristic_candidates(
    sentiments: list,
    acoustic_events: list,
    highlights: list,
    velocity_timeline: list,
    words: list,
    chapters: list | None,
    boundaries: list[dict],
) -> list[dict]:
    """Generate candidate anchors from multiple signal sources.

    Improvements over the original:
      - Boundary-snapped timestamps (never cut mid-sentence)
      - Speaker-exchange detection for dialogue-heavy content
      - Velocity-spike detection for high-energy moments
      - Boundary-aware zone windows instead of sequential slicing
    """
    candidates: list[dict] = []

    # ── Source A: Chapters ──
    if chapters:
        for ch in chapters:
            ch_s = ch.get("start", 0)
            ch_e = ch.get("end", 0)
            ch_dur = ch_e - ch_s

            if ch_dur >= 15.0:
                # Trim long chapters to a ~35s window
                if ch_dur > 55.0:
                    trim_end = ch_s + 35.0
                    ch_e = min(
                        _snap_to_boundary(trim_end, boundaries, "after", 5.0),
                        ch_s + 55.0,
                    )

                snapped_s = _snap_to_boundary(ch_s, boundaries, "after", 3.0)
                snapped_e = _snap_to_boundary(ch_e, boundaries, "before", 3.0)

                if snapped_e - snapped_s >= 15.0:
                    candidates.append({
                        "start_sec": snapped_s,
                        "end_sec": snapped_e,
                        "source": "chapter",
                        "headline": ch.get("headline", "Topic Highlight"),
                        "gist": ch.get("gist", "Key Topic"),
                        "summary": ch.get("summary", ""),
                        "base_score": 80.0,
                    })

    # ── Source B: Sentiment peaks ──
    intense = [
        s for s in sentiments
        if s.get("confidence", 0) > 0.80 and s.get("sentiment") != "NEUTRAL"
    ]
    for peak in intense:
        raw_s = max(0, peak["start"] - 5.0)
        raw_e = peak["end"] + 25.0

        snapped_s = _snap_to_boundary(raw_s, boundaries, "before", 4.0)
        snapped_e = _snap_to_boundary(raw_e, boundaries, "after", 4.0)

        dur = snapped_e - snapped_s
        if dur < 15.0:
            snapped_e = snapped_s + 30.0
        elif dur > 55.0:
            snapped_e = snapped_s + 40.0

        candidates.append({
            "start_sec": snapped_s,
            "end_sec": snapped_e,
            "source": "sentiment",
            "headline": f"Peak: {peak['text'][:40]}...",
            "gist": f"Viral Peak ({peak['sentiment']})",
            "summary": peak["text"],
            "base_score": 75.0,
        })

    # ── Source C: Highlights ──
    for h in (highlights or [])[:10]:
        for t in h.get("timestamps", []):
            raw_s = max(0, t["start"] - 3.0)
            raw_e = t["end"] + 20.0

            snapped_s = _snap_to_boundary(raw_s, boundaries, "before", 3.0)
            snapped_e = _snap_to_boundary(raw_e, boundaries, "after", 3.0)

            dur = snapped_e - snapped_s
            if dur < 15.0:
                snapped_e = snapped_s + 30.0
            elif dur > 55.0:
                snapped_e = snapped_s + 40.0

            candidates.append({
                "start_sec": snapped_s,
                "end_sec": snapped_e,
                "source": "highlight",
                "headline": f"Highlight: {h.get('text', '')[:40]}",
                "gist": h.get("text", "Key Highlight"),
                "summary": h.get("text", ""),
                "base_score": 72.0,
            })

    # ── Source D: Speaker-exchange zones ──
    if words and len(words) > 10:
        window, step = 30.0, 15.0
        t0, t1 = words[0]["start"], words[-1]["end"]
        cur = t0
        while cur < t1 - 15.0:
            w_end = min(cur + window, t1)
            win_w = [w for w in words if cur <= w["start"] <= w_end]

            turns = sum(
                1 for i in range(1, len(win_w))
                if win_w[i].get("speaker") is not None
                and win_w[i - 1].get("speaker") is not None
                and win_w[i].get("speaker") != win_w[i - 1].get("speaker")
            )

            if turns >= 2:
                sn_s = _snap_to_boundary(cur, boundaries, "before", 3.0)
                sn_e = _snap_to_boundary(w_end, boundaries, "after", 3.0)
                dur = sn_e - sn_s
                if 15.0 <= dur <= 55.0:
                    candidates.append({
                        "start_sec": sn_s,
                        "end_sec": sn_e,
                        "source": "speaker_exchange",
                        "headline": f"Discussion ({turns} exchanges)",
                        "gist": "Multi-Speaker Exchange",
                        "summary": "",
                        "base_score": 76.0 + min(8.0, turns * 2.0),
                    })
            cur += step

    # ── Source E: Velocity spikes ──
    if velocity_timeline:
        avg_wpm = sum(v["wpm"] for v in velocity_timeline) / len(velocity_timeline)
        for v in velocity_timeline:
            if v["wpm"] > avg_wpm * 1.4:
                spike_s = v["window_start_ms"] / 1000.0
                sn_s = _snap_to_boundary(spike_s, boundaries, "before", 3.0)
                sn_e = _snap_to_boundary(spike_s + 30.0, boundaries, "after", 3.0)
                dur = sn_e - sn_s
                if 15.0 <= dur <= 55.0:
                    candidates.append({
                        "start_sec": sn_s,
                        "end_sec": sn_e,
                        "source": "velocity_spike",
                        "headline": f"High Energy ({v['wpm']:.0f} wpm)",
                        "gist": "High Energy Moment",
                        "summary": "",
                        "base_score": 70.0,
                    })

    # ── Fallback: Boundary-aware zone windows (NOT sequential slicing) ──
    if not candidates and words:
        logger.info("No signal candidates — generating boundary-aware zone windows.")
        total_dur = words[-1]["end"] - words[0]["start"]
        num_zones = max(3, int(total_dur / 60.0) + 1)
        zone_size = total_dur / num_zones

        for z in range(num_zones):
            zone_mid = words[0]["start"] + z * zone_size + zone_size / 2
            best_s = _snap_to_boundary(zone_mid - 15.0, boundaries, "before", 10.0)
            best_e = _snap_to_boundary(best_s + 30.0, boundaries, "after", 5.0)
            if best_e - best_s >= 15.0:
                candidates.append({
                    "start_sec": best_s,
                    "end_sec": best_e,
                    "source": "zone_window",
                    "headline": f"Video Segment {z + 1}",
                    "gist": "Video Highlight",
                    "summary": "",
                    "base_score": 65.0,
                })

    return candidates


def _score_with_signals(
    candidates: list[dict],
    sentiments: list,
    acoustic_events: list,
    highlights: list,
    velocity_timeline: list,
    words: list,
) -> list[dict]:
    """Score candidates using weighted multi-signal analysis.

    Scoring breakdown (max 100):
      base_score (60-80) + sentiment (0-10) + speakers (0-8)
      + acoustics (0-10) + highlights (0-8) + velocity (0-6)
      + sentiment_contrast (0-5) + completeness (0-5)
    """
    scored: list[dict] = []

    for cand in candidates:
        c_s = cand["start_sec"]
        c_e = cand["end_sec"]
        dur = c_e - c_s
        if not (15.0 <= dur <= 60.0):
            continue

        c_s_ms = int(c_s * 1000)
        c_e_ms = int(c_e * 1000)

        # Overlap guard
        if any(abs(s["start_ms"] - c_s_ms) < 10000 for s in scored):
            continue

        score = cand.get("base_score", 70.0)

        # ── Sentiment intensity ──
        w_sent = [
            s for s in sentiments
            if int(s["start"] * 1000) >= c_s_ms and int(s["end"] * 1000) <= c_e_ms
        ]
        non_neutral = [s for s in w_sent if s.get("sentiment") != "NEUTRAL"]
        score += min(10.0, len(non_neutral) * 3.0)

        # Sentiment contrast (shift within clip = dramatic arc)
        labels = {s.get("sentiment") for s in non_neutral}
        if "POSITIVE" in labels and "NEGATIVE" in labels:
            score += 5.0

        # ── Speaker dynamics ──
        clip_w = [w for w in words if c_s_ms <= int(w["start"] * 1000) <= c_e_ms]
        speakers = set(w.get("speaker") for w in clip_w if w.get("speaker") is not None)
        if len(speakers) > 1:
            score += min(8.0, len(speakers) * 4.0)

        # ── Acoustic events ──
        w_acst = [
            e for e in acoustic_events
            if e["start_ms"] >= c_s_ms and e["end_ms"] <= c_e_ms
        ]
        if w_acst:
            score += min(10.0, len(w_acst) * 5.0)

        # ── Highlight density ──
        w_hl = [
            h for h in highlights
            if any(
                int(t["start"] * 1000) >= c_s_ms and int(t["end"] * 1000) <= c_e_ms
                for t in h.get("timestamps", [])
            )
        ]
        score += min(8.0, len(w_hl) * 3.0)

        # ── Velocity variance ──
        w_vel = [
            v for v in velocity_timeline
            if v["window_start_ms"] >= c_s_ms and v["window_end_ms"] <= c_e_ms
        ]
        avg_wpm = (
            sum(v["wpm"] for v in w_vel) / len(w_vel) if w_vel else 160.0
        )
        if len(w_vel) >= 2:
            wpms = [v["wpm"] for v in w_vel]
            variance = max(wpms) - min(wpms)
            if variance > 40:
                score += min(6.0, variance / 15.0)

        # ── Content completeness ──
        if clip_w:
            if clip_w[0]["word"] and clip_w[0]["word"][0].isupper():
                score += 2.0
            if clip_w[-1]["word"].rstrip().endswith((".", "?", "!")):
                score += 3.0

        final_score = min(100.0, round(score, 1))

        h_words = [w["word"] for w in clip_w[:6]]
        h_text = " ".join(h_words) if h_words else cand["headline"]

        scored.append({
            "id": f"short_clip_{len(scored) + 1}",
            "type": "short",
            "headline": cand["headline"],
            "summary": cand["summary"],
            "gist": cand["gist"],
            "hook_quote": h_text,
            "start_ms": c_s_ms,
            "end_ms": c_e_ms,
            "duration_seconds": round(dur, 2),
            "viral_score": final_score,
            "is_shorts_ready": True,
            "words": _build_clip_words(words, c_s_ms, c_e_ms),
            "signals": {
                "source": cand["source"],
                "speakers_count": len(speakers),
                "sentiment_count": len(w_sent),
                "acoustic_events": [e["event"] for e in w_acst],
                "highlights_count": len(w_hl),
                "average_wpm": round(avg_wpm, 1),
                "pacing_note": "Multi-signal scored (enhanced heuristic)",
            },
        })

    return scored


# ---------------------------------------------------------------------------
# DIVERSITY & FINAL SELECTION
# ---------------------------------------------------------------------------

def _select_with_diversity(
    scored_clips: list[dict],
    total_duration_sec: float,
    target_count: int,
) -> list[dict]:
    """Greedy diversified selection with temporal proximity penalty.

    Clips near already-selected ones get their effective score reduced,
    naturally spreading picks across the entire timeline.
    """
    if len(scored_clips) <= target_count:
        for i, c in enumerate(scored_clips):
            c["id"] = f"short_clip_{i + 1}"
        return scored_clips

    pool = sorted(scored_clips, key=lambda c: c["viral_score"], reverse=True)
    min_gap_ms = max(30000, int(total_duration_sec * 1000 / (target_count * 1.5)))
    selected: list[dict] = []

    for _ in range(target_count):
        if not pool:
            break

        best_idx, best_eff = -1, -1.0
        for idx, cand in enumerate(pool):
            eff = cand["viral_score"]
            for sel in selected:
                dist = abs(cand["start_ms"] - sel["start_ms"])
                if dist < min_gap_ms:
                    eff -= 15.0 * (1.0 - dist / min_gap_ms)
            if eff > best_eff:
                best_eff = eff
                best_idx = idx

        if best_idx >= 0:
            selected.append(pool.pop(best_idx))

    selected.sort(key=lambda c: c["start_ms"])
    for i, c in enumerate(selected):
        c["id"] = f"short_clip_{i + 1}"
    return selected


# ---------------------------------------------------------------------------
# MAIN ORCHESTRATOR
# ---------------------------------------------------------------------------

def score_and_rank_short_clips(
    sentiments: list,
    acoustic_events: list,
    highlights: list,
    velocity_timeline: list,
    words: list,
    total_duration_sec: float,
    chapters: list | None = None,
) -> list[dict]:
    """OpusClip-grade viral clip extraction engine.

    1. PRIMARY — Gemini AI discovers self-contained viral moments with full
       social metadata (title, hook, hashtags, etc.).
    2. FALLBACK — Enhanced multi-signal heuristics when Gemini is unavailable:
       boundary detection → candidate generation → signal scoring → diversity.
    """
    target_count = calculate_sweet_spot_clip_count(total_duration_sec)
    boundaries = _find_natural_boundaries(words)

    # ── Primary: AI-powered discovery ──
    ai_clips = _discover_clips_with_ai(
        words=words,
        chapters=chapters,
        sentiments=sentiments,
        highlights=highlights,
        total_duration_sec=total_duration_sec,
        target_clip_count=target_count,
        boundaries=boundaries,
    )
    if ai_clips:
        return ai_clips

    # ── Fallback: enhanced heuristics ──
    logger.info("Using enhanced heuristic clip selection pipeline.")

    candidates = _generate_heuristic_candidates(
        sentiments=sentiments,
        acoustic_events=acoustic_events,
        highlights=highlights,
        velocity_timeline=velocity_timeline,
        words=words,
        chapters=chapters,
        boundaries=boundaries,
    )

    scored = _score_with_signals(
        candidates=candidates,
        sentiments=sentiments,
        acoustic_events=acoustic_events,
        highlights=highlights,
        velocity_timeline=velocity_timeline,
        words=words,
    )

    if not scored:
        logger.warning("No clips could be scored — returning empty list.")
        return []

    return _select_with_diversity(scored, total_duration_sec, target_count)


def calculate_sweet_spot_clip_count(total_duration_sec: float) -> int:
    """Target clip count — generous pool so users have plenty of options."""
    duration_min = total_duration_sec / 60.0
    if duration_min <= 5:
        return 5
    elif duration_min <= 15:
        return 8
    elif duration_min <= 30:
        return 10
    elif duration_min <= 60:
        return 14
    elif duration_min <= 120:
        return 16
    else:
        return 18




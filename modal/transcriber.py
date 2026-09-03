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
from models import EnrichTranscriptRequest, SubmitTranscribeRequest, TranscribeRequest
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

    def _process_and_enrich_transcript(
        self,
        transcript,
        translate_language: str | None = None,
        prompt: str | None = None,
        keyterms: list[str] | None = None,
    ):
        """Map words, extract chapters/sentiments/highlights, score viral clips and enrich with Gemini."""
        words = []
        speaker_map = {}
        next_speaker_id = 0
        paragraphs = []
        full_text = transcript.text

        target_lang = translate_language
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
        # 1. Check Speech Understanding summarization response
        su_json = getattr(transcript, "json_response", {}) or {}
        su_obj = su_json.get("speech_understanding") or {}
        su_response = su_obj.get("response") or {}
        summarization_data = su_response.get("summarization") or {}
        su_summaries = summarization_data.get("summary") or []

        if su_summaries:
            for c in su_summaries:
                chapters_out.append({
                    "headline": c.get("headline", ""),
                    "summary": c.get("text", "") or c.get("summary", ""),
                    "gist": c.get("headline", "") or c.get("gist", ""),
                    "start": (c.get("start") or 0) / 1000.0,
                    "end": (c.get("end") or 0) / 1000.0,
                })
        # 2. Check transcript.chapters (from auto_chapters)
        elif getattr(transcript, "chapters", None):
            for c in transcript.chapters:
                chapters_out.append({
                    "headline": getattr(c, "headline", "") or "",
                    "summary": getattr(c, "summary", "") or "",
                    "gist": getattr(c, "gist", "") or "",
                    "start": (getattr(c, "start", 0) or 0) / 1000.0,
                    "end": (getattr(c, "end", 0) or 0) / 1000.0,
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

        # Enrich candidate short clips with Gemini social metadata (title, hook, hashtags, etc.)
        viral_clips_out = enrich_clips_with_gemini(
            viral_clips_out, words, full_text=full_text, chapters=chapters_out
        )

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

    def _submit_transcription(self, req: SubmitTranscribeRequest):
        """Core logic to submit audio to AssemblyAI asynchronously."""
        import assemblyai as aai
        import requests

        logger.info("=== SUBMIT TRANSCRIBE REQUEST ===")
        logger.info("video_url: %s...", (req.video_url or "")[:100])

        if not req.video_url:
            raise InvalidInputError("video_url is required to submit transcription")

        vurl = validate_url(req.video_url, label="video_url")

        aai.settings.api_key = os.environ.get("ASSEMBLYAI_API_KEY")
        if not aai.settings.api_key:
            raise InvalidInputError(
                "ASSEMBLYAI_API_KEY environment variable is missing in Modal secret"
            )

        config_kwargs = {
            "speech_models": ["universal-3-5-pro", "universal-2"],
            "speaker_labels": True,
            "disfluencies": True,
            "auto_highlights": True,
            "sentiment_analysis": True,
            "filter_profanity": True,
            "auto_chapters": True,
        }

        if req.transcribe_language and req.transcribe_language != "auto":
            config_kwargs["language_code"] = req.transcribe_language
        else:
            config_kwargs["language_detection"] = True

        if req.translate_language and req.translate_language != "none":
            config_kwargs["speech_understanding"] = {
                "request": {
                    "translation": {
                        "target_languages": [req.translate_language],
                        "match_original_utterance": True,
                    }
                }
            }

        default_prompt = (
            "Video or podcast recording with spoken dialogue, key topics, and discussions."
        )
        config_kwargs["prompt"] = req.prompt if getattr(req, "prompt", None) else default_prompt
        if getattr(req, "keyterms", None):
            config_kwargs["keyterms_prompt"] = req.keyterms

        config = aai.TranscriptionConfig(**config_kwargs)
        transcriber = aai.Transcriber(config=config)

        # For remote non-YouTube URLs (e.g. presigned R2 URLs), attempt direct URL submission first
        if not is_youtube_url(vurl):
            try:
                logger.info("Attempting direct URL submission to AssemblyAI...")
                transcript = transcriber.submit(vurl)
                logger.info("AssemblyAI submission accepted directly for URL. ID: %s", transcript.id)
                return {
                    "success": True,
                    "transcript_id": transcript.id,
                    "status": str(transcript.status.value if hasattr(transcript.status, "value") else transcript.status),
                }
            except Exception as e:
                logger.warning("Direct URL submission to AssemblyAI failed (%s), falling back to media extraction: %s", type(e).__name__, e)

        with tempfile.TemporaryDirectory() as tmpdir:
            if is_youtube_url(vurl):
                logger.info("YouTube URL detected. Downloading audio only via yt-dlp...")
                local_media = download_youtube_audio(vurl, tmpdir)
            else:
                logger.info("Downloading remote media for local extraction...")
                local_media = os.path.join(tmpdir, "input_media")
                with requests.get(vurl, stream=True, timeout=120) as r:
                    r.raise_for_status()
                    with open(local_media, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

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
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                raise RenderError(f"FFmpeg audio extraction failed: {result.stderr[-500:]}")

            logger.info("Uploading and submitting local WAV to AssemblyAI...")
            transcript = transcriber.submit(local_wav)
            logger.info("AssemblyAI submit successful. Transcript ID: %s", transcript.id)

            return {
                "success": True,
                "transcript_id": transcript.id,
                "status": str(transcript.status.value if hasattr(transcript.status, "value") else transcript.status),
            }

    def _enrich_transcript(self, req: EnrichTranscriptRequest):
        """Core logic to fetch completed transcript from AssemblyAI and run viral scoring + Gemini enrichment."""
        import assemblyai as aai

        logger.info("=== ENRICH TRANSCRIPT REQUEST ===")
        logger.info("transcript_id: %s", req.transcript_id)

        aai.settings.api_key = os.environ.get("ASSEMBLYAI_API_KEY")
        if not aai.settings.api_key:
            raise InvalidInputError(
                "ASSEMBLYAI_API_KEY environment variable is missing in Modal secret"
            )

        transcript = aai.Transcript.get_by_id(req.transcript_id)
        if transcript.status == aai.TranscriptStatus.error:
            logger.error("AssemblyAI transcript reported error: %s", transcript.error)
            raise TranscriptionError(f"AssemblyAI transcription failed: {transcript.error}")

        if transcript.status != aai.TranscriptStatus.completed:
            logger.warning("Transcript %s is not yet completed (status: %s)", req.transcript_id, transcript.status)
            return {
                "success": False,
                "status": str(transcript.status.value if hasattr(transcript.status, "value") else transcript.status),
                "error": f"Transcript is not completed yet (status={transcript.status})"
            }

        return self._process_and_enrich_transcript(
            transcript=transcript,
            translate_language=req.translate_language,
            prompt=req.prompt,
            keyterms=req.keyterms,
        )

    @modal.fastapi_endpoint(method="POST")
    def submit_transcription(self, req: SubmitTranscribeRequest):
        """Endpoint to submit audio to AssemblyAI asynchronously."""
        return self._submit_transcription(req)

    @modal.fastapi_endpoint(method="POST")
    def enrich_transcript(self, req: EnrichTranscriptRequest):
        """Endpoint to fetch completed transcript from AssemblyAI and run viral scoring + Gemini enrichment."""
        return self._enrich_transcript(req)

    @modal.fastapi_endpoint(method="POST")
    def transcribe(self, req: TranscribeRequest):
        """Unified endpoint: supports submit, enrich, or monolithic transcribe."""
        import assemblyai as aai
        import time

        # Mode A: Enrich an already-completed AssemblyAI transcript
        if req.transcript_id:
            return self._enrich_transcript(
                EnrichTranscriptRequest(
                    transcript_id=req.transcript_id,
                    translate_language=req.translate_language,
                    prompt=req.prompt,
                    keyterms=req.keyterms,
                )
            )

        # Mode B: Submit-only (async)
        if req.submit_only:
            return self._submit_transcription(
                SubmitTranscribeRequest(
                    video_url=req.video_url or "",
                    transcribe_language=req.transcribe_language,
                    translate_language=req.translate_language,
                    prompt=req.prompt,
                    keyterms=req.keyterms,
                )
            )

        # Mode C: Monolithic fallback for backwards compatibility
        logger.info("=== MONOLITHIC TRANSCRIBE REQUEST ===")
        submit_res = self._submit_transcription(
            SubmitTranscribeRequest(
                video_url=req.video_url or "",
                transcribe_language=req.transcribe_language,
                translate_language=req.translate_language,
                prompt=req.prompt,
                keyterms=req.keyterms,
            )
        )
        t_id = submit_res["transcript_id"]
        aai.settings.api_key = os.environ.get("ASSEMBLYAI_API_KEY")

        logger.info("Polling AssemblyAI for transcript %s...", t_id)
        while True:
            t = aai.Transcript.get_by_id(t_id)
            if t.status == aai.TranscriptStatus.completed:
                logger.info("Transcript %s completed. Enriching...", t_id)
                return self._process_and_enrich_transcript(
                    transcript=t,
                    translate_language=req.translate_language,
                    prompt=req.prompt,
                    keyterms=req.keyterms,
                )
            elif t.status == aai.TranscriptStatus.error:
                raise TranscriptionError(f"AssemblyAI transcription failed: {t.error}")
            time.sleep(3)


def enrich_clips_with_gemini(
    viral_clips: list[dict],
    words: list[dict],
    full_text: str = "",
    chapters: list[dict] | None = None,
) -> list[dict]:
    """Enrich candidate short clips with Gemini-generated viral scores and social metadata."""
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

        prompt = f"""You are an expert viral short-form content curator and algorithm specialist for TikTok, IG Reels, and YouTube Shorts.
Analyze these candidate video clips and return a structured JSON object matching the schema.

CRITICAL ACCURACY & CONTEXT RULES:
- Overall Video Context Snippet: {context_snippet}
- Rely ONLY on the actual transcript context to determine who is speaking or being discussed.
- DO NOT hallucinate famous podcasters or celebrity names UNLESS they are explicitly mentioned by name in the transcript.
- Match titles, descriptions, and hashtags strictly to the actual speakers and content of the video.

VIRAL SCORING RUBRIC (viralScore from 0.0 to 10.0):
- Evaluate hook strength (first 3 seconds), emotional intensity/resonance, punchline/insight, curiosity gap, and retention potential.
- Top-tier standout moments (insane hooks, explosive debates, incredible insights, high dopamine) MUST receive 9.0 - 9.9.
- Strong, engaging clips should score 8.0 - 8.9.
- Good informative/interesting clips should score 7.0 - 7.9.
- Lower energy or weak hook clips should score below 7.0.

For each candidate clip, generate:
- title: Short, curiosity-inducing clickbait title (max 7 words)
- hookText: Bold 1-3 word scroll-stopping caption for the first 3 seconds
- viralScore: Precise viral potential score from 0.0 to 10.0 (e.g. 9.6, 9.2, 8.8, 8.4) based on the rubric
- viralReason: 1 punchy sentence explaining the specific psychological or algorithmic trigger that makes this clip perform
- description: Engaging social media post description
- hashtags: Top 5 space-separated hashtags (e.g. #shorts #viral)
- clipType: one of ["hot_take", "funny_exchange", "quotable", "debate", "aha_moment", "storytelling", "mind_blowing_fact"]

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

        models_to_try = ["gemini-2.5-flash", "gemini-3.6-flash"]
        response_text = None

        for model in models_to_try:
            for attempt in range(3):
                try:
                    logger.info("Calling Gemini model %s (attempt %d/3)...", model, attempt + 1)
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
                        logger.info("Gemini model %s succeeded!", model)
                        break
                except Exception as e:
                    err_msg = str(e)
                    logger.warning("Gemini model %s (attempt %d/3) failed: %s", model, attempt + 1, err_msg)
                    # If 503 high demand or 429 rate limit, wait with backoff and retry
                    if "503" in err_msg or "UNAVAILABLE" in err_msg or "429" in err_msg:
                        import time
                        time.sleep(2 * (attempt + 1))
                        continue
                    else:
                        break  # Fall back to next model immediately for other errors
            if response_text:
                break

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
                    if gem.get("viralScore") is not None:
                        try:
                            score_val = float(gem["viralScore"])
                            if score_val > 10.0:
                                score_val = score_val / 10.0
                            score_val = round(max(0.0, min(10.0, score_val)), 1)
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

                # Re-rank candidate clips by Gemini viral score descending
                viral_clips.sort(key=lambda x: x.get("viral_score", 0.0), reverse=True)
                for i, c in enumerate(viral_clips):
                    c["id"] = f"short_clip_{i + 1}"

                logger.info(
                    "Successfully scored and enriched %d clips with Gemini metadata (top viral score: %s).",
                    len(viral_clips),
                    viral_clips[0].get("viral_score") if viral_clips else "N/A",
                )
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
# MULTI-SIGNAL VIRAL CLIP SCORING ENGINE
#
# Pipeline:
#   1. Natural Boundary Snapping (sentence ends, pauses, speaker turns)
#   2. Multi-Signal Candidate Generation (chapters, sentiments, highlights,
#      speaker exchanges, velocity spikes)
#   3. Multi-Signal Scoring (intensity, contrast, dynamics, acoustics, pacing)
#   4. Temporal Diversity Selection (penalty-based greedy selection)
# ═══════════════════════════════════════════════════════════════════════════════


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
# Multi-Signal Candidate Anchor Generation
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
                        "base_score": 8.0,
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
            "base_score": 7.8,
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
                "base_score": 7.6,
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
                        "base_score": 7.7 + min(0.8, turns * 0.2),
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
                        "base_score": 7.5,
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
                    "base_score": 7.0,
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
    """Score candidates using calibrated weighted multi-signal analysis (0.0 to 10.0 range).

    Scoring breakdown (0.0-10.0 range):
      base_score (7.0-8.5) + sentiment (0-0.8) + speakers (0-0.6)
      + acoustics (0-0.6) + highlights (0-0.5) + velocity (0-0.4)
      + sentiment_contrast (0-0.4) + completeness (0-0.3)
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

        score = cand.get("base_score", 7.5)
        if score > 10.0:
            score = score / 10.0

        # ── Sentiment intensity (0 to 0.8 pts) ──
        w_sent = [
            s for s in sentiments
            if int(s["start"] * 1000) >= c_s_ms and int(s["end"] * 1000) <= c_e_ms
        ]
        non_neutral = [s for s in w_sent if s.get("sentiment") != "NEUTRAL"]
        score += min(0.8, len(non_neutral) * 0.2)

        # Sentiment contrast (shift within clip = dramatic arc, +0.4 pts)
        labels = {s.get("sentiment") for s in non_neutral}
        if "POSITIVE" in labels and "NEGATIVE" in labels:
            score += 0.4

        # ── Speaker dynamics (0 to 0.6 pts) ──
        clip_w = [w for w in words if c_s_ms <= int(w["start"] * 1000) <= c_e_ms]
        speakers = set(w.get("speaker") for w in clip_w if w.get("speaker") is not None)
        if len(speakers) > 1:
            score += min(0.6, (len(speakers) - 1) * 0.3)

        # ── Acoustic events (0 to 0.6 pts) ──
        w_acst = [
            e for e in acoustic_events
            if e["start_ms"] >= c_s_ms and e["end_ms"] <= c_e_ms
        ]
        if w_acst:
            score += min(0.6, len(w_acst) * 0.3)

        # ── Highlight density (0 to 0.5 pts) ──
        w_hl = [
            h for h in highlights
            if any(
                int(t["start"] * 1000) >= c_s_ms and int(t["end"] * 1000) <= c_e_ms
                for t in h.get("timestamps", [])
            )
        ]
        score += min(0.5, len(w_hl) * 0.15)

        # ── Velocity variance (0 to 0.4 pts) ──
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
            if variance > 30:
                score += min(0.4, variance / 100.0)

        # ── Content completeness (0 to 0.3 pts) ──
        if clip_w:
            if clip_w[0]["word"] and clip_w[0]["word"][0].isupper():
                score += 0.1
            if clip_w[-1]["word"].rstrip().endswith((".", "?", "!")):
                score += 0.2

        final_score = round(min(10.0, max(1.0, score)), 1)

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
                    eff -= 1.5 * (1.0 - dist / min_gap_ms)
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
    """Viral clip extraction and scoring engine relying strictly on multi-signal analysis.

    Pipeline:
      1. Boundary detection (natural pauses, sentence ends, speaker turns)
      2. Multi-signal candidate generation (chapters, sentiment peaks, highlights, speaker exchanges, velocity spikes)
      3. Weighted signal scoring (sentiment intensity, contrast, speaker dynamics, acoustics, highlight density, velocity variance)
      4. Diversity & temporal spacing selection (greedy selection with proximity penalty)
    """
    target_count = calculate_sweet_spot_clip_count(total_duration_sec)
    boundaries = _find_natural_boundaries(words)

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
        logger.warning("No clips could be scored from signals — returning empty list.")
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




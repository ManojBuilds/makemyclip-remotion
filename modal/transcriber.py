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
from sentence_utils import (
    build_sentence_stream,
    calculate_speech_velocity,
    calculate_sweet_spot_clip_count,
    extract_acoustic_events,
    prune_leading_fillers,
)
from utils import StageTimer, is_direct_media_url, is_youtube_url, is_ytdlp_supported_url, validate_url
from viral_constants import (
    CONCLUSION_INDICATORS,
    FILLER_WORDS,
    HOOK_INDICATORS,
    WEAK_ENDING_WORDS,
)
from viral_discovery import (
    discover_viral_clips_with_gemini,
    enrich_clips_with_gemini,
    validate_and_refine_clips_with_gemini,
)
from viral_heuristics import (
    generate_sentence_candidates,
    score_and_rank_short_clips,
)
from ytdlp_helper import download_media_audio, download_youtube_audio, remove_bgutil_pot_provider

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

        # Build structured grammatical sentence units with timing & speaker metadata
        total_duration = words[-1]["end"] - words[0]["start"] if words else 0.0
        sentences = build_sentence_stream(words)

        # Primary Tier: LLM Semantic Discovery with Gemini (1M-token context, understands hooks & punchlines)
        viral_clips_out = []
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if gemini_key and len(sentences) >= 3:
            logger.info("Attempting Gemini primary semantic discovery for viral clips...")
            viral_clips_out = discover_viral_clips_with_gemini(
                sentences=sentences,
                words=words,
                full_text=full_text,
                chapters=chapters_out,
                highlights=highlights_out,
                sentiments=sentiments_out,
                total_duration_sec=total_duration,
                gemini_key=gemini_key,
                prompt_context=prompt,
                keyterms=keyterms,
            )

        # Fallback Tier: Enhanced sentence-aware multi-signal heuristic engine
        if not viral_clips_out or len(viral_clips_out) < 3:
            logger.info("Using enhanced sentence-aware multi-signal fallback engine...")
            velocity_timeline = calculate_speech_velocity(words)
            acoustic_events = extract_acoustic_events(words, full_text)
            viral_clips_out = score_and_rank_short_clips(
                sentiments=sentiments_out,
                acoustic_events=acoustic_events,
                highlights=highlights_out,
                velocity_timeline=velocity_timeline,
                words=words,
                sentences=sentences,
                total_duration_sec=total_duration,
                chapters=chapters_out,
            )
            # Enrich candidate short clips with Gemini social metadata if available
            if gemini_key and viral_clips_out:
                viral_clips_out = enrich_clips_with_gemini(
                    viral_clips_out, words, full_text=full_text, chapters=chapters_out,
                    prompt_context=prompt, keyterms=keyterms,
                )

        # Final validation pass: review clip set for quality, diversity, and ending strength
        if gemini_key and viral_clips_out and len(viral_clips_out) >= 2:
            viral_clips_out = validate_and_refine_clips_with_gemini(
                clips=viral_clips_out,
                sentences=sentences,
                words=words,
                full_text=full_text,
                chapters=chapters_out,
                gemini_key=gemini_key,
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

        # For direct raw media URLs (e.g. presigned R2 URLs or direct .mp4/.wav), attempt direct URL submission first
        if is_direct_media_url(vurl):
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
            if is_ytdlp_supported_url(vurl):
                logger.info("Supported video platform URL detected. Downloading audio only via yt-dlp...")
                local_media = download_media_audio(vurl, tmpdir)
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


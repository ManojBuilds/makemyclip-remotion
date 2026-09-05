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


FILLER_WORDS = {
    "um", "uh", "like", "so", "yeah", "yes", "right", "well", "and",
    "basically", "actually", "you know", "i mean", "okay", "ok"
}

HOOK_INDICATORS = [
    "why do", "how to", "what if", "did you know", "have you noticed",
    "the biggest mistake", "the problem is", "the secret to", "nobody talks about",
    "never do", "always remember", "unpopular opinion", "the truth about",
    "i realized", "worst mistake", "best advice", "shocking truth", "insane story",
    "stop doing", "don't ever", "this changed my", "mind-blowing", "most people don't",
    "if you want", "here's why", "the reason why", "the crazy thing is", "do you think",
    "can you imagine"
]


def build_sentence_stream(words: list[dict]) -> list[dict]:
    """Segment words into grammatical sentence units with timing and speaker metadata."""
    if not words:
        return []

    sentences: list[dict] = []
    current_words: list[dict] = []

    for i, w in enumerate(words):
        current_words.append(w)
        text = w["word"].rstrip().rstrip("\"')}]")
        is_punct = text.endswith((".", "?", "!"))

        is_long_pause = False
        is_speaker_turn = False
        if i < len(words) - 1:
            gap = words[i + 1]["start"] - w["end"]
            if gap > 0.65:
                is_long_pause = True
            if (
                w.get("speaker") is not None
                and words[i + 1].get("speaker") is not None
                and w.get("speaker") != words[i + 1].get("speaker")
            ):
                is_speaker_turn = True

        # Split sentence on punctuation, speaker turn, pause gap, or length safeguard
        is_clause_split = len(current_words) >= 25 and (text.endswith((",", ";", ":")) or is_long_pause)
        is_runaway_split = len(current_words) >= 38

        if (
            is_punct
            or (is_speaker_turn and len(current_words) >= 3)
            or (is_long_pause and len(current_words) >= 4)
            or is_clause_split
            or is_runaway_split
        ):
            s_text = " ".join(cw["word"] for cw in current_words).strip()
            if s_text:
                sentences.append({
                    "index": len(sentences),
                    "text": s_text,
                    "start": current_words[0]["start"],
                    "end": current_words[-1]["end"],
                    "start_ms": int(round(current_words[0]["start"] * 1000)),
                    "end_ms": int(round(current_words[-1]["end"] * 1000)),
                    "speaker": current_words[0].get("speaker"),
                    "words": current_words,
                })
            current_words = []

    if current_words:
        s_text = " ".join(cw["word"] for cw in current_words).strip()
        if s_text:
            sentences.append({
                "index": len(sentences),
                "text": s_text,
                "start": current_words[0]["start"],
                "end": current_words[-1]["end"],
                "start_ms": int(round(current_words[0]["start"] * 1000)),
                "end_ms": int(round(current_words[-1]["end"] * 1000)),
                "speaker": current_words[0].get("speaker"),
                "words": current_words,
            })

    return sentences


def prune_leading_fillers(clip_words: list[dict]) -> tuple[float, list[dict]]:
    """Prune conversational filler words from the very start of a clip so it opens on a punchy word."""
    if not clip_words or len(clip_words) <= 5:
        return (clip_words[0]["start"] if clip_words else 0.0, clip_words)

    start_idx = 0
    while start_idx < min(4, len(clip_words) - 5):
        clean_word = clip_words[start_idx]["word"].strip().lower().rstrip(".,!?")
        if clean_word in FILLER_WORDS:
            start_idx += 1
        else:
            break

    pruned = clip_words[start_idx:]
    return (pruned[0]["start"], pruned)


def _clean_text_for_matching(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9\s]", "", (text or "").lower()).strip()


def _find_matching_sentence(
    quote: str,
    target_time: float,
    sentences: list[dict],
    is_start: bool = True,
    search_window_sec: float = 60.0,
) -> int:
    """Find the best sentence index matching a quote near target_time, with global fallback."""
    if not sentences:
        return 0

    clean_quote = _clean_text_for_matching(quote)
    quote_tokens = set(clean_quote.split()) if clean_quote else set()

    # 1. Proximity-window search (within search_window_sec)
    candidates = []
    for idx, s in enumerate(sentences):
        t = s["start"] if is_start else s["end"]
        diff = abs(t - target_time)
        if diff <= search_window_sec:
            s_clean = _clean_text_for_matching(s["text"])
            score = 0.0
            if clean_quote and clean_quote in s_clean:
                score = 4.0
            elif quote_tokens:
                s_tokens = set(s_clean.split())
                overlap = len(quote_tokens & s_tokens)
                if overlap > 0:
                    score = (overlap / max(1, len(quote_tokens))) * 2.0
            candidates.append((score, -diff, idx))

    if candidates:
        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        if candidates[0][0] > 0.4:
            return candidates[0][2]

    # 2. Global quote substring search across all sentences if quote is substantial
    if clean_quote and len(clean_quote.split()) >= 3:
        for idx, s in enumerate(sentences):
            s_clean = _clean_text_for_matching(s["text"])
            if clean_quote in s_clean:
                return idx

    # 3. Proximity fallback
    best_idx = 0
    best_dist = float("inf")
    for idx, s in enumerate(sentences):
        t = s["start"] if is_start else s["end"]
        dist = abs(t - target_time)
        if dist < best_dist:
            best_dist = dist
            best_idx = idx

    return best_idx


def _clips_overlap_too_much(
    s1: float, e1: float, s2: float, e2: float, max_overlap_ratio: float = 0.35
) -> bool:
    """Check if two clip intervals overlap by more than max_overlap_ratio of the shorter clip."""
    overlap_start = max(s1, s2)
    overlap_end = min(e1, e2)
    overlap = max(0.0, overlap_end - overlap_start)
    if overlap <= 0:
        return False
    min_dur = min(e1 - s1, e2 - s2)
    if min_dur <= 0:
        return True
    return (overlap / min_dur) > max_overlap_ratio


def discover_viral_clips_with_gemini(
    sentences: list[dict],
    words: list[dict],
    full_text: str = "",
    chapters: list[dict] | None = None,
    highlights: list[dict] | None = None,
    sentiments: list[dict] | None = None,
    total_duration_sec: float = 0.0,
    gemini_key: str = "",
) -> list[dict]:
    """Primary discovery engine: Uses Gemini 2.5 Flash (1M token window) to identify the most viral, complete moments."""
    if not gemini_key or not sentences or len(sentences) < 3:
        return []

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=gemini_key)
        target_count = calculate_sweet_spot_clip_count(total_duration_sec)

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

        prompt = f"""You are a master viral short-form content curator and growth strategist for TikTok, YouTube Shorts, and Instagram Reels.
Your objective: Find the {target_count} absolute most viral, captivating, and high-retention short clips from this recording.

{chapters_context}

{hl_context}

FULL TRANSCRIPT WITH TIMESTAMPS:
{transcript_text}

CRITICAL RULES FOR SELECTING VIRAL CLIPS:
1. **The Hook (First 3-5 Seconds)**:
   - Must immediately grab attention and stop thumbs from scrolling past.
   - Look for: shocking confessions, controversial claims, intriguing questions, high-stakes revelations, or emotional debates.
   - Avoid slow intros, conversational filler ("Um, so yeah, basically..."), or administrative banter.
2. **Self-Contained Narrative Arc**:
   - The clip MUST make complete sense to a random viewer with zero prior context.
   - Must have a coherent setup -> tension/insight -> punchline or satisfying payoff.
   - NEVER cut off mid-thought or mid-sentence. The thought MUST conclude cleanly.
3. **Clip Duration**:
   - Target 25 to 60 seconds (sweet spot for short-form retention).
   - Up to 75 seconds ONLY for gripping stories or intense debates. NEVER under 18 seconds.
4. **Distribution & Topic Diversity**:
   - Spread the {target_count} clips across different chapters and topics throughout the entire recording. Do not cluster all clips in one spot.
5. **Exact Quote Anchoring**:
   - `startQuote`: The EXACT first 4 to 8 words spoken at the beginning of the clip.
   - `endQuote`: The EXACT last 4 to 8 words spoken at the end of the clip.
   - `startTimeSec` & `endTimeSec`: Approximate timestamps in seconds.

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

        models_to_try = ["gemini-2.5-flash", "gemini-2.5-pro"]
        response_text = None

        for model in models_to_try:
            for attempt in range(2):
                try:
                    logger.info("Calling Gemini model %s for viral discovery (attempt %d/2)...", model, attempt + 1)
                    res = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=schema,
                            temperature=0.3,
                            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                        ),
                    )
                    if res.text:
                        response_text = res.text
                        logger.info("Gemini model %s successfully discovered viral clips!", model)
                        break
                except Exception as e:
                    err_msg = str(e)
                    logger.warning("Gemini model %s attempt %d failed: %s", model, attempt + 1, err_msg)
                    if "503" in err_msg or "UNAVAILABLE" in err_msg or "429" in err_msg:
                        import time
                        time.sleep(2 * (attempt + 1))
                        continue
                    else:
                        break
            if response_text:
                break

        if not response_text:
            return []

        import json
        raw_text = response_text.strip()
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw_text = "\n".join(lines).strip()

        parsed = json.loads(raw_text)
        suggestions = parsed.get("clips", [])
        if not isinstance(suggestions, list) or not suggestions:
            return []

        candidates_out = []
        for raw in suggestions:
            approx_s = float(raw.get("startTimeSec", 0.0))
            approx_e = float(raw.get("endTimeSec", approx_s + 35.0))
            start_q = raw.get("startQuote", "")
            end_q = raw.get("endQuote", "")

            start_idx = _find_matching_sentence(start_q, approx_s, sentences, is_start=True, search_window_sec=40.0)
            end_idx = _find_matching_sentence(end_q, approx_e, sentences, is_start=False, search_window_sec=40.0)

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

            if not (15.0 <= duration <= 85.0):
                continue

            # Check overlap against already chosen clips
            if any(_clips_overlap_too_much(actual_start_sec, actual_end_sec, c["start_sec"], c["end_sec"]) for c in candidates_out):
                continue

            raw_score = float(raw.get("viralScore", 8.5))
            if raw_score > 10.0:
                raw_score = raw_score / 10.0
            viral_score = round(max(1.0, min(9.9, raw_score)), 1)

            start_ms = int(actual_start_sec * 1000)
            end_ms = int(actual_end_sec * 1000)

            title = raw.get("title", "Viral Highlight")
            hook_text = raw.get("hookText", "WATCH THIS").upper().rstrip("?")
            if not hook_text:
                hook_text = "WATCH THIS"

            candidates_out.append({
                "id": f"short_clip_{len(candidates_out) + 1}",
                "type": "short",
                "headline": title,
                "title": title,
                "gist": title,
                "summary": raw.get("description", ""),
                "description": raw.get("description", ""),
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
                "viralReason": raw.get("viralReason", "High engagement viral short format."),
                "hashtags": raw.get("hashtags", "#shorts #viral #podcast"),
                "clipType": raw.get("clipType", "hot_take"),
                "is_shorts_ready": True,
                "words": _build_clip_words(words, start_ms, end_ms),
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


def enrich_clips_with_gemini(
    viral_clips: list[dict],
    words: list[dict],
    full_text: str = "",
    chapters: list[dict] | None = None,
) -> list[dict]:
    """Enrich candidate short clips with Gemini-generated viral scores and social metadata."""
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key or not viral_clips:
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

        prompt = f"""You are an expert viral short-form content curator and algorithm specialist for TikTok, IG Reels, and YouTube Shorts.
Analyze these pre-extracted video clips and return a structured JSON object matching the schema.

CRITICAL VIRAL GUIDELINES:
- Context: {context_snippet}
- TITLE: Must be an irresistible, scroll-stopping curiosity hook (max 6-7 words). Avoid generic labels. Use psychological hooks, strong emotional statements, contrasts, or surprising quotes.
- HOOKTEXT: Exactly 1 to 3 words in ALL CAPS (e.g. "WAIT FOR IT", "SHOTS FIRED!", "BIG MISTAKE", "UNREAL"). Must NOT end with a question mark.
- VIRALSCORE: Precise viral potential score from 7.0 to 9.9.
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

        models_to_try = ["gemini-2.5-flash", "gemini-3.6-flash"]
        response_text = None

        for model in models_to_try:
            for attempt in range(2):
                try:
                    logger.info("Calling Gemini %s for clip enrichment (attempt %d/2)...", model, attempt + 1)
                    res = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=schema,
                            temperature=0.3,
                            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                        ),
                    )
                    if res.text:
                        response_text = res.text
                        break
                except Exception as e:
                    err_msg = str(e)
                    logger.warning("Gemini enrichment attempt failed (%s): %s", model, err_msg)
                    if "503" in err_msg or "UNAVAILABLE" in err_msg or "429" in err_msg:
                        import time
                        time.sleep(2 * (attempt + 1))
                        continue
                    else:
                        break
            if response_text:
                break

        if response_text:
            import json
            raw_text = response_text.strip()
            if raw_text.startswith("```"):
                lines = raw_text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw_text = "\n".join(lines).strip()

            parsed = json.loads(raw_text)
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


# ═══════════════════════════════════════════════════════════════════════════════
# ENHANCED SENTENCE-AWARE MULTI-SIGNAL HEURISTIC ENGINE (FALLBACK)
# ═══════════════════════════════════════════════════════════════════════════════

def _score_sentence_hook(text: str) -> float:
    """Evaluate hook power of an opening sentence (0.0 to 1.5 pts)."""
    clean = text.lower().strip()
    score = 0.0

    # Question mark indicates curiosity hook
    if clean.endswith("?"):
        score += 0.8

    # Check for hook phrases
    for hook in HOOK_INDICATORS:
        if hook in clean:
            score += 0.7
            break

    # Contrast word at start (e.g. "But the real reason...")
    first_word = clean.split()[0] if clean.split() else ""
    if first_word in {"but", "however", "actually", "honestly", "listen"}:
        score += 0.3

    return min(1.5, score)


def _generate_sentence_candidates(
    sentences: list[dict],
    words: list[dict],
    sentiments: list,
    acoustic_events: list,
    highlights: list,
    velocity_timeline: list,
    chapters: list | None,
) -> list[dict]:
    """Generate candidates from multi-sentence windows strictly aligned to sentence boundaries."""
    if not sentences:
        return []

    candidates: list[dict] = []
    avg_wpm = (
        sum(v["wpm"] for v in velocity_timeline) / len(velocity_timeline)
        if velocity_timeline else 160.0
    )

    n_sentences = len(sentences)

    for i in range(n_sentences):
        cur_start_sent = sentences[i]
        start_sec = cur_start_sent["start"]

        # Check multi-sentence windows of 18 to 65 seconds (up to 28 sentences for snappy dialogue)
        for j in range(i + 1, min(i + 28, n_sentences)):
            cur_end_sent = sentences[j]
            raw_dur = cur_end_sent["end"] - start_sec

            if raw_dur < 18.0:
                continue
            if raw_dur > 65.0:
                break

            # Prune fillers from start
            sub_words = [
                w for w in words
                if w["start"] >= start_sec - 0.05 and w["end"] <= cur_end_sent["end"] + 0.05
            ]
            pruned_start, pruned_words = prune_leading_fillers(sub_words)
            dur = cur_end_sent["end"] - pruned_start

            if not (18.0 <= dur <= 65.0):
                continue

            c_s_ms = int(round(pruned_start * 1000))
            c_e_ms = int(round(cur_end_sent["end"] * 1000))

            # --- Scoring signals ---
            base_score = 7.2

            # 1. Opening hook score
            hook_score = _score_sentence_hook(cur_start_sent["text"])
            base_score += hook_score

            # 2. Speaker dynamic (turns within window)
            window_speakers = set(
                sentences[k].get("speaker") for k in range(i, j + 1)
                if sentences[k].get("speaker") is not None
            )
            turns = sum(
                1 for k in range(i, j)
                if sentences[k].get("speaker") != sentences[k + 1].get("speaker")
            )
            if len(window_speakers) > 1:
                base_score += min(0.8, 0.3 + turns * 0.15)

            # 3. Acoustic events (laughter, applause)
            w_acst = [
                e for e in acoustic_events
                if e["start_ms"] >= c_s_ms and e["end_ms"] <= c_e_ms
            ]
            if w_acst:
                base_score += min(0.6, len(w_acst) * 0.3)

            # 4. Sentiments (intensity + contrast)
            w_sent = [
                s for s in sentiments
                if int(s["start"] * 1000) >= c_s_ms and int(s["end"] * 1000) <= c_e_ms
            ]
            non_neutral = [s for s in w_sent if s.get("sentiment") != "NEUTRAL"]
            if non_neutral:
                base_score += min(0.6, len(non_neutral) * 0.15)
            labels = {s.get("sentiment") for s in non_neutral}
            if "POSITIVE" in labels and "NEGATIVE" in labels:
                base_score += 0.4

            # 5. Highlights
            w_hl = [
                h for h in highlights
                if any(
                    int(t["start"] * 1000) >= c_s_ms and int(t["end"] * 1000) <= c_e_ms
                    for t in h.get("timestamps", [])
                )
            ]
            if w_hl:
                base_score += min(0.5, len(w_hl) * 0.15)

            # 6. Pacing & velocity
            w_vel = [
                v for v in velocity_timeline
                if v["window_start_ms"] >= c_s_ms and v["window_end_ms"] <= c_e_ms
            ]
            if w_vel:
                max_wpm = max(v["wpm"] for v in w_vel)
                if max_wpm > avg_wpm * 1.3:
                    base_score += 0.3

            final_score = round(max(1.0, min(9.9, base_score)), 1)

            first_words = [w["word"].strip() for w in pruned_words[:6]] if pruned_words else cur_start_sent["text"].split()[:6]
            headline = " ".join(first_words) if first_words else "Viral Highlight"

            candidates.append({
                "start_sec": pruned_start,
                "end_sec": cur_end_sent["end"],
                "start_ms": c_s_ms,
                "end_ms": c_e_ms,
                "duration_seconds": round(dur, 2),
                "headline": headline,
                "summary": cur_start_sent["text"],
                "gist": headline,
                "hook_quote": "WATCH THIS",
                "viral_score": final_score,
                "speakers_count": len(window_speakers),
                "turns_count": turns,
            })

    return candidates


def score_and_rank_short_clips(
    sentiments: list,
    acoustic_events: list,
    highlights: list,
    velocity_timeline: list,
    words: list,
    sentences: list[dict],
    total_duration_sec: float,
    chapters: list | None = None,
) -> list[dict]:
    """Overhauled multi-signal sentence-aware engine (Fallback if Gemini is unavailable)."""
    target_count = calculate_sweet_spot_clip_count(total_duration_sec)

    candidates = _generate_sentence_candidates(
        sentences=sentences,
        words=words,
        sentiments=sentiments,
        acoustic_events=acoustic_events,
        highlights=highlights,
        velocity_timeline=velocity_timeline,
        chapters=chapters,
    )

    if not candidates:
        return []

    # Greedy diversity selection with proximity penalty
    pool = sorted(candidates, key=lambda c: c["viral_score"], reverse=True)
    min_gap_sec = max(30.0, total_duration_sec / (target_count * 1.5))
    selected: list[dict] = []

    for _ in range(target_count):
        if not pool:
            break

        best_idx, best_eff = -1, -1.0
        for idx, cand in enumerate(pool):
            # Check overlap with already selected
            if any(_clips_overlap_too_much(cand["start_sec"], cand["end_sec"], sel["start_sec"], sel["end_sec"]) for sel in selected):
                continue

            eff = cand["viral_score"]
            for sel in selected:
                dist = abs(cand["start_sec"] - sel["start_sec"])
                if dist < min_gap_sec:
                    eff -= 1.5 * (1.0 - dist / min_gap_sec)

            if eff > best_eff:
                best_eff = eff
                best_idx = idx

        if best_idx >= 0:
            selected.append(pool.pop(best_idx))

    selected.sort(key=lambda c: c["start_sec"])

    out: list[dict] = []
    for i, c in enumerate(selected):
        c_id = f"short_clip_{i + 1}"
        out.append({
            "id": c_id,
            "type": "short",
            "headline": c["headline"],
            "title": c["headline"],
            "gist": c["gist"],
            "summary": c["summary"],
            "description": c["summary"],
            "hook_quote": c["hook_quote"],
            "hookText": c["hook_quote"],
            "start_ms": c["start_ms"],
            "end_ms": c["end_ms"],
            "start_sec": c["start_sec"],
            "end_sec": c["end_sec"],
            "startTime": c["start_sec"],
            "endTime": c["end_sec"],
            "duration_seconds": c["duration_seconds"],
            "viral_score": c["viral_score"],
            "viralScore": c["viral_score"],
            "viralReason": "Multi-signal audio intelligence peak (sentence-aligned)",
            "hashtags": "#shorts #viral #podcast",
            "clipType": "hot_take",
            "is_shorts_ready": True,
            "words": _build_clip_words(words, c["start_ms"], c["end_ms"]),
            "signals": {
                "source": "multi_signal_fallback",
                "pacing_note": "Multi-signal scored (sentence-aligned)",
            },
        })

    return out


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





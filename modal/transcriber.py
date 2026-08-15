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

            # Enrich short clips directly with Gemini social metadata in Modal
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

        models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
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


def score_and_rank_short_clips(
    sentiments: list,
    acoustic_events: list,
    highlights: list,
    velocity_timeline: list,
    words: list,
    total_duration_sec: float,
    chapters: list | None = None,
) -> list[dict]:
    """Universal Micro-Clip Extractor for ANY video type (Podcasts, Tutorials, Vlogs, Gaming, Reviews).
    Extracts candidate anchors from 3 complementary sources:
      1. AssemblyAI Chapters (Ideal for Educational, Tech, Tutorials, Reviews)
      2. AssemblyAI Sentiment Peaks (Ideal for Podcasts, Debates, Interviews)
      3. AssemblyAI Highlights & Acoustic Spikes (Ideal for Vlogs, Gaming, Reactions)
    """
    candidate_anchors = []

    # 1. Source A: Chapters (Educational, Tutorials, Tech, Reviews)
    if chapters:
        for ch in chapters:
            ch_start = int(ch.get("start", 0) * 1000)
            ch_end = int(ch.get("end", 0) * 1000)
            ch_dur = (ch_end - ch_start) / 1000.0

            if 15.0 <= ch_dur <= 60.0:
                candidate_anchors.append({
                    "start_ms": ch_start,
                    "end_ms": ch_end,
                    "source": "chapter",
                    "headline": ch.get("headline", "Topic Highlight"),
                    "gist": ch.get("gist", "Key Topic"),
                    "summary": ch.get("summary", ""),
                })
            elif ch_dur > 60.0:
                candidate_anchors.append({
                    "start_ms": ch_start,
                    "end_ms": min(ch_start + 35000, ch_end),
                    "source": "chapter",
                    "headline": ch.get("headline", "Topic Highlight"),
                    "gist": ch.get("gist", "Key Topic"),
                    "summary": ch.get("summary", ""),
                })

    # 2. Source B: Sentiment Peaks (Podcasts, Debates, Interviews)
    intense_sentiments = [
        s for s in sentiments if s.get("confidence", 0) > 0.85 and s.get("sentiment") != "NEUTRAL"
    ]
    for peak in intense_sentiments:
        p_start = max(0, int(peak["start"] * 1000) - 5000)
        p_end = min(p_start + 35000, int(peak["end"] * 1000) + 25000)
        candidate_anchors.append({
            "start_ms": p_start,
            "end_ms": p_end,
            "source": "sentiment",
            "headline": f"Peak: {peak['text'][:40]}...",
            "gist": f"Viral Peak ({peak['sentiment']})",
            "summary": peak["text"],
        })

    # 3. Source C: Highlights & Keyphrases (Vlogs, Gaming, Commentary)
    for h in (highlights or [])[:10]:
        for t in h.get("timestamps", []):
            h_start = max(0, int(t["start"] * 1000) - 3000)
            h_end = min(h_start + 35000, int(t["end"] * 1000) + 20000)
            candidate_anchors.append({
                "start_ms": h_start,
                "end_ms": h_end,
                "source": "highlight",
                "headline": f"Highlight: {h.get('text', '')[:40]}",
                "gist": h.get('text', 'Key Highlight'),
                "summary": h.get('text', ''),
            })

    # Filter and score candidate clips
    scored_clips = []
    shorts_counter = 1

    for cand in candidate_anchors:
        c_start = cand["start_ms"]
        c_end = cand["end_ms"]
        dur = (c_end - c_start) / 1000.0

        if 15.0 <= dur <= 60.0:
            overlap = any(abs(c["start_ms"] - c_start) < 10000 for c in scored_clips)
            if not overlap:
                w_sent = [s for s in sentiments if int(s["start"] * 1000) >= c_start and int(s["end"] * 1000) <= c_end]
                w_acoustics = [e for e in acoustic_events if e["start_ms"] >= c_start and e["end_ms"] <= c_end]
                w_highlights = [
                    h for h in highlights if any(int(t["start"] * 1000) >= c_start and int(t["end"] * 1000) <= c_end for t in h.get("timestamps", []))
                ]
                w_velocity = [v for v in velocity_timeline if v["window_start_ms"] >= c_start and v["window_end_ms"] <= c_end]
                avg_wpm = sum(v["wpm"] for v in w_velocity) / len(w_velocity) if w_velocity else 160.0

                clip_w = [w for w in words if c_start <= int(w["start"] * 1000) <= c_end]
                unique_speakers = set(w.get("speaker") for w in clip_w if w.get("speaker") is not None)

                s_score = 75.0
                s_score += len(w_sent) * 5.0
                s_score += (30.0 if w_acoustics else 0.0)
                s_score += len(w_highlights) * 4.0
                if len(unique_speakers) > 1:
                    s_score += 8.0
                if cand["source"] == "chapter":
                    s_score += 10.0
                if avg_wpm > 175:
                    s_score += 6.0

                final_short_score = min(100.0, round(s_score, 1))

                h_words = [w["word"] for w in clip_w[:6]]
                h_text = " ".join(h_words) if h_words else cand["headline"]

                short_words_list = [
                    {
                        "word": w["word"].strip().lower(),
                        "punctuated_word": w["word"].strip(),
                        "start": round(max(0.0, w["start"] - (c_start / 1000.0)), 3),
                        "end": round(max(0.05, w["end"] - (c_start / 1000.0)), 3),
                        "confidence": round(w.get("confidence", 0.99), 3),
                        "speaker": str(w.get("speaker", 0)),
                    }
                    for w in clip_w
                ]

                scored_clips.append({
                    "id": f"short_clip_{shorts_counter}",
                    "type": "short",
                    "headline": cand["headline"],
                    "summary": cand["summary"],
                    "gist": cand["gist"],
                    "hook_quote": h_text,
                    "start_ms": c_start,
                    "end_ms": c_end,
                    "duration_seconds": round(dur, 2),
                    "viral_score": final_short_score,
                    "is_shorts_ready": True,
                    "words": short_words_list,
                    "signals": {
                        "source": cand["source"],
                        "speakers_count": len(unique_speakers),
                        "sentiment_count": len(w_sent),
                        "acoustic_events": [e["event"] for e in w_acoustics],
                        "highlights_count": len(w_highlights),
                        "average_wpm": round(avg_wpm, 1),
                        "pacing_note": "Universal Multi-Signal Extractor",
                    },
                })
                shorts_counter += 1

    # Filter strictly for short-form ready clips (15s to 60s)
    short_clips_only = [
        c for c in scored_clips
        if c.get("is_shorts_ready", True) and 15.0 <= c.get("duration_seconds", 0) <= 60.0
    ]

    # Dynamic Fallback: If no sentiment peaks yielded clips, construct candidate windows directly from words
    if not short_clips_only and words:
        logger.info("[score_and_rank_short_clips] No sentiment peak clips found. Extracting candidate clips from transcript...")
        min_start = words[0]["start"]
        max_end = words[-1]["end"]
        clip_dur = 35.0
        curr = min_start
        counter = 1

        while curr < max_end - 10 and counter <= 6:
            c_start_ms = int(curr * 1000)
            c_end_ms = int(min(curr + clip_dur, max_end) * 1000)
            dur_sec = (c_end_ms - c_start_ms) / 1000.0

            if dur_sec >= 15.0:
                clip_w = [w for w in words if c_start_ms <= int(w["start"] * 1000) <= c_end_ms]
                h_text = " ".join([w["word"] for w in clip_w[:5]]) if clip_w else "Highlight"

                short_clips_only.append({
                    "id": f"short_clip_{counter}",
                    "type": "short",
                    "headline": f"Video Segment {counter}",
                    "summary": f"Video highlight from {curr:.1f}s to {curr + dur_sec:.1f}s",
                    "gist": "Video Highlight",
                    "hook_quote": h_text,
                    "start_ms": c_start_ms,
                    "end_ms": c_end_ms,
                    "duration_seconds": round(dur_sec, 2),
                    "viral_score": 80.0,
                    "is_shorts_ready": True,
                    "words": [
                        {
                            "word": w["word"].strip().lower(),
                            "punctuated_word": w["word"].strip(),
                            "start": round(max(0.0, w["start"] - (c_start_ms / 1000.0)), 3),
                            "end": round(max(0.05, w["end"] - (c_start_ms / 1000.0)), 3),
                            "confidence": round(w.get("confidence", 0.99), 3),
                            "speaker": str(w.get("speaker", 0)),
                        }
                        for w in clip_w
                    ],
                    "signals": {
                        "pacing_note": "Segment extracted from video transcript",
                    },
                })
                counter += 1
            curr += clip_dur - 5.0

    short_clips_only.sort(key=lambda x: x["viral_score"], reverse=True)

    # Sweet-Spot Dynamic Clip Count (1 high-value clip per ~4-5 mins, bounded 3 to 12)
    target_clip_count = calculate_sweet_spot_clip_count(total_duration_sec)

    if len(short_clips_only) > target_clip_count:
        t_third = (total_duration_sec * 1000) / 3.0
        t_two_third = (total_duration_sec * 1000) * 2.0 / 3.0

        early = [c for c in short_clips_only if c["start_ms"] < t_third]
        mid = [c for c in short_clips_only if t_third <= c["start_ms"] < t_two_third]
        late = [c for c in short_clips_only if c["start_ms"] >= t_two_third]

        per_bucket = max(1, target_clip_count // 3)
        selected = []
        for bucket in (early, mid, late):
            selected.extend(bucket[:per_bucket])

        for c in short_clips_only:
            if len(selected) >= target_clip_count:
                break
            if c not in selected:
                selected.append(c)

        return selected[:target_clip_count]

    return short_clips_only[:target_clip_count]


def calculate_sweet_spot_clip_count(total_duration_sec: float) -> int:
    """Calculate clip count providing a generous selection pool (5 to 18 clips) so users
    always have plenty of highly usable clips to post to TikTok/Reels/Shorts.
    """
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



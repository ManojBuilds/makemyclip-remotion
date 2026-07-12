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
    timeout=600,
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
        validate_url(req.video_url, label="video_url")

        # Configure AssemblyAI key
        aai.settings.api_key = os.environ.get("ASSEMBLYAI_API_KEY")
        if not aai.settings.api_key:
            raise InvalidInputError(
                "ASSEMBLYAI_API_KEY environment variable is missing in Modal secret"
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            vurl = req.video_url

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
                    "speech_models": ["universal-3-pro", "universal-2"],
                    "speaker_labels": True,
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

            logger.info(
                "Returning %d words, %d paragraphs, %d speakers",
                len(words),
                len(paragraphs),
                len(speaker_map),
            )

            return {
                "success": True,
                "fullText": full_text,
                "words": words,
                "paragraphs": paragraphs,
            }

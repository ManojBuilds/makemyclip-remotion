"""CaptionBurner Modal service.

Burns ASS-rendered captions onto an existing video using FFmpeg + libass.
Independent of the AI reframer so caption-only re-renders are fast.

Supports two quality tiers:
  - "preview": Fast 360p encode for in-browser preview (superfast, CRF 32)
  - "export":  Full 1080p encode for HD download (fast, CRF 23)
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import uuid

import modal

from ass_builder import generate_ass
from config import ai_secret, app, image
from errors import DownloadError, InvalidInputError, RenderError
from models import BurnCaptionsRequest, CaptionStyle
from r2_storage import upload_to_r2
from utils import StageTimer, validate_url

logger = logging.getLogger("makemyclip.burner")

# FFmpeg burn timeout. Burns are CPU-only and rarely exceed ~3 min for a
# typical 60s clip even with complex captions, so this is a safety ceiling
# that prevents a stuck encode from holding the worker for the full Modal
# container timeout.
_FFMPEG_BURN_TIMEOUT_S = 480  # 8 minutes

# Path to the watermark PNG baked into the Modal container image.
_WATERMARK_PATH = "/root/watermark.png"


def get_watermark_path() -> str:
    """Return absolute path to watermark PNG image (Modal environment or local workspace)."""
    if os.path.exists(_WATERMARK_PATH):
        return _WATERMARK_PATH
    local_wm = os.path.abspath(os.path.join(os.path.dirname(__file__), "watermark.png"))
    if os.path.exists(local_wm):
        return local_wm
    return _WATERMARK_PATH


def probe_video_dimensions(video_path: str) -> tuple[int, int]:
    """Probe input video (width, height). Returns (1080, 1920) default on error."""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            video_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        w, h = map(int, res.stdout.strip().split("x"))
        return w, h
    except Exception:
        return 1080, 1920


def get_watermark_config(video_width: int, video_height: int) -> tuple[int, int, int]:
    """Calculates watermark sizing and positioning margins proportional to video width.
    - Sizing: 45% of video width (~162px on 360p, ~486px on 1080p, ~864px on 4K)
    - Position: Top-left corner (unobstructed by TikTok/Reels UI) with safe margins
    """
    wm_width = max(145, int(video_width * 0.45))
    margin_left = max(16, int(video_width * 0.04))
    margin_top = max(24, int(video_height * 0.04))

    return wm_width, margin_left, margin_top


# Quality presets
_QUALITY_PRESETS = {
    "preview": {
        "scale": "scale=360:-2",
        "preset": "superfast",
        "crf": "32",
        "r2_prefix": "previews",
        "file_prefix": "prev",
        "audio": ["-c:a", "copy"],
    },
    "export_free": {
        "scale": "scale=-2:720",
        "preset": "fast",
        "crf": "28",
        "r2_prefix": "renders",
        "file_prefix": "cap",
        "audio": ["-c:a", "aac", "-b:a", "128k"],
    },
    "export": {
        "scale": None,
        "preset": "fast",
        "crf": "22",
        "r2_prefix": "renders",
        "file_prefix": "cap",
        "audio": ["-c:a", "aac", "-b:a", "128k"],
    },
}


def _resolve_export_key(quality: str, plan: str) -> str:
    """Map (quality, plan) to the correct _QUALITY_PRESETS key.

    - preview → always "preview"
    - export + free → "export_free" (720p, watermarked)
    - export + creator/power → "export" (1080p)
    """
    if quality == "preview":
        return "preview"
    if plan == "free":
        return "export_free"
    return "export"


def burn_captions_local(
    local_video: str,
    local_output: str,
    transcript: list[dict],
    styling: CaptionStyle | dict,
    show_watermark: bool = False,
    crop_mode: str = "reframe",
    quality: str = "export",
    plan: str = "free",
    tmpdir: str = None,
) -> tuple[str, str | None]:
    """Burns captions locally onto an existing video file, uploads to R2,

    and generates a thumbnail if quality is "preview".
    """
    if isinstance(styling, dict):
        styling = CaptionStyle(**styling)

    preset_key = _resolve_export_key(quality, plan)
    qp = _QUALITY_PRESETS[preset_key]
    logger.info("Resolved quality preset: %s (quality=%s, plan=%s)", preset_key, quality, plan)

    local_ass = os.path.join(tmpdir, f"subs_{uuid.uuid4()}.ass")

    # 2. Generate ASS subtitles
    with StageTimer("generate_ass"):
        generate_ass(transcript, styling, local_ass, crop_mode=crop_mode)

    # 3. Burn with FFmpeg — quality-dependent settings
    with StageTimer("ffmpeg_burn"):
        logger.info("Burning captions [%s] with FFmpeg...", quality)

        watermark_path = get_watermark_path()
        watermark_exists = os.path.exists(watermark_path)
        has_subs = bool(
            os.path.exists(local_ass) and os.path.getsize(local_ass) > 0
        )

        if show_watermark and watermark_exists:
            w, h = probe_video_dimensions(local_video)
            if qp["scale"]:
                scale_factor = 1.0
                scale_str = qp["scale"].replace("scale=", "")
                parts = scale_str.split(":")
                if len(parts) >= 2:
                    try:
                        w_val = int(parts[0])
                        h_val = int(parts[1])
                        if w_val > 0 and w > 0:
                            scale_factor = float(w_val) / float(w)
                        elif h_val > 0 and h > 0:
                            scale_factor = float(h_val) / float(h)
                    except ValueError:
                        pass
                effective_w = int(w * scale_factor)
                effective_h = int(h * scale_factor)
            else:
                effective_w, effective_h = w, h

            wm_width, margin_left, margin_top = get_watermark_config(
                effective_w, effective_h
            )

            # High quality alpha compositing (70% opacity, anti-aliased bicubic scaling)
            # Watermark is rendered in TOP-LEFT corner (safe from Reels/TikTok UI), BELOW subtitles/captions layer
            wm_filter = f"[1:v]scale={wm_width}:-1:flags=bicubic,format=rgba,colorchannelmixer=aa=0.7[wm]"

            if qp["scale"]:
                v_prep = f"[0:v]{qp['scale']}[v_base];[v_base][wm]overlay={margin_left}:{margin_top}[v_wm]"
            else:
                v_prep = f"[0:v][wm]overlay={margin_left}:{margin_top}[v_wm]"

            if has_subs:
                fc = f"{wm_filter};{v_prep};[v_wm]ass='{local_ass}'[out]"
            else:
                fc = f"{wm_filter};{v_prep}[out]"

            cmd = [
                "ffmpeg",
                "-y",
                "-i", local_video,
                "-i", watermark_path,
                "-filter_complex", fc,
                "-map", "[out]",
                "-map", "0:a?",
                "-c:v", "libx264",
                "-preset", qp["preset"],
                "-crf", qp["crf"],
                "-pix_fmt", "yuv420p",
                "-profile:v", "high",
                *qp["audio"],
                "-threads", "2",
                "-movflags", "+faststart",
                local_output,
            ]
        else:
            filters = []
            if qp["scale"]:
                filters.append(qp["scale"])
            if has_subs:
                filters.append(f"ass='{local_ass}'")

            vf_str = ",".join(filters) if filters else "null"

            cmd = [
                "ffmpeg",
                "-y",
                "-i", local_video,
                "-vf", vf_str,
                "-c:v", "libx264",
                "-preset", qp["preset"],
                "-crf", qp["crf"],
                "-pix_fmt", "yuv420p",
                "-profile:v", "high",
                *qp["audio"],
                "-threads", "2",
                "-movflags", "+faststart",
                local_output,
            ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_FFMPEG_BURN_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired as e:
            raise RenderError(
                f"FFmpeg caption burn timed out after {_FFMPEG_BURN_TIMEOUT_S}s"
            ) from e

        if result.stdout:
            logger.debug("FFmpeg stdout (tail): %s", result.stdout[-500:])
        if result.stderr:
            logger.debug("FFmpeg stderr (tail): %s", result.stderr[-1000:])
        if result.returncode != 0:
            raise RenderError(f"FFmpeg failed: {result.stderr[-500:]}")

    # 4. Upload to R2 (best-effort when running in local dev environments)
    caption_video_url = local_output
    try:
        with StageTimer("upload_r2"):
            filename = f"{qp['file_prefix']}_{uuid.uuid4()}.mp4"
            caption_video_url = upload_to_r2(
                local_output, f"{qp['r2_prefix']}/{filename}"
            )
    except Exception as e:
        logger.warning("R2 upload skipped or failed (returning local file path): %s", e)

    # 5. Extract thumbnail (only for preview)
    thumbnail_url = None
    if quality == "preview":
        local_thumb = os.path.join(tmpdir, f"thumb_{uuid.uuid4()}.webp")
        try:
            with StageTimer("thumbnail_extract"):
                logger.info("Extracting thumbnail...")
                thumb_cmd = [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    "00:00:01",
                    "-i",
                    local_output,
                    "-vframes",
                    "1",
                    "-vf",
                    "scale=360:-1",
                    "-q:v",
                    "80",
                    local_thumb,
                ]
                thumb_result = subprocess.run(
                    thumb_cmd,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if thumb_result.returncode != 0:
                    logger.warning(
                        "Thumbnail seek to 1s failed, retrying at 0s"
                    )
                    thumb_cmd[2] = "00:00:00"
                    subprocess.run(
                        thumb_cmd, capture_output=True, text=True, timeout=15
                    )

            with StageTimer("upload_r2_thumb"):
                thumb_filename = f"thumb_{uuid.uuid4()}.webp"
                thumbnail_url = upload_to_r2(
                    local_thumb, f"thumbnails/{thumb_filename}"
                )
        except Exception as e:
            logger.error("Failed to generate or upload thumbnail: %s", e)

    return caption_video_url, thumbnail_url


@app.cls(image=image, timeout=1200, secrets=[ai_secret], max_containers=10)
@modal.concurrent(max_inputs=2)
class CaptionBurner:
    @modal.method()
    def burn(
        self,
        video_url: str,
        transcript: list[dict],
        styling: CaptionStyle | dict,
        show_watermark: bool = False,
        crop_mode: str = "reframe",
        quality: str = "export",
        plan: str = "free",
    ) -> dict:
        """Download video, generate ASS captions, burn with FFmpeg, upload to R2."""
        import requests

        if isinstance(styling, dict):
            styling = CaptionStyle(**styling)

        word_count = sum(
            len(b.get("words", [])) if isinstance(b, dict) and "words" in b else 1
            for b in (transcript or [])
        )
        logger.info(
            "Starting burn [%s]: ~%d words, font=%s, watermark=%s",
            quality,
            word_count,
            styling.font_family,
            show_watermark,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            local_video = os.path.join(tmpdir, "input.mp4")
            local_output = os.path.join(tmpdir, "output.mp4")

            # 1. Download source video
            with StageTimer("download_video"):
                logger.info("Downloading video from %s...", video_url[:100])
                try:
                    with requests.get(video_url, stream=True, timeout=300) as r:
                        r.raise_for_status()
                        with open(local_video, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                except requests.RequestException as e:
                    raise DownloadError(f"Failed to download video: {e}") from e

            file_size = os.path.getsize(local_video)
            logger.info("Downloaded %s bytes", f"{file_size:,}")
            if file_size == 0:
                raise InvalidInputError("Downloaded video is empty (0 bytes)")

            caption_video_url, thumbnail_url = burn_captions_local(
                local_video=local_video,
                local_output=local_output,
                transcript=transcript,
                styling=styling,
                show_watermark=show_watermark,
                crop_mode=crop_mode,
                quality=quality,
                plan=plan,
                tmpdir=tmpdir,
            )

            logger.info(
                "✅ Burn complete [%s]. Video URL: %s, Thumbnail URL: %s",
                quality,
                caption_video_url,
                thumbnail_url,
            )
            return {
                "video_url": caption_video_url,
                "thumbnail_url": thumbnail_url,
            }

    @modal.fastapi_endpoint(method="POST")
    def endpoint(self, req: BurnCaptionsRequest):
        """Public endpoint for caption burning."""
        vurl = validate_url(req.video_url, label="video_url")
        res = self.burn.remote(
            vurl,
            req.transcript,
            req.styling,
            show_watermark=req.show_watermark,
            crop_mode=req.crop_mode,
            quality=req.quality,
            plan=req.plan,
        )
        logger.info("Endpoint returned: %s", res)
        return {
            "success": True,
            "url": res["video_url"],
            "thumbnail_url": res["thumbnail_url"],
        }

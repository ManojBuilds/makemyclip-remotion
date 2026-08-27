"""Video and Audio Utilities for AI Reframer.

Contains helper functions for:
- Audio RMS energy calculation for emphasis zoom punch
- Audio/video muxing with FFmpeg hardware encoder acceleration
- Premium blurred background generation for letterbox cards
"""

from __future__ import annotations

import logging
import os
import subprocess
import wave
import numpy as np
try:
    import cv2
except ImportError:
    cv2 = None

logger = logging.getLogger("makemyclip.video_utils")

_FFMPEG_LONG_TIMEOUT_S = 1200


def compute_audio_rms_energy(audio_wav_path: str, fps: float = 25.0, max_frames: int | None = None) -> np.ndarray:
    """Compute per-frame RMS audio energy from a 16kHz WAV file.

    Returns a 1D numpy array of float RMS energy values aligned with video frames.
    """
    if not os.path.exists(audio_wav_path) or os.path.getsize(audio_wav_path) == 0:
        return np.zeros(0, dtype=np.float32)

    try:
        with wave.open(audio_wav_path, "rb") as wf:
            n_channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            raw_bytes = wf.readframes(n_frames)

        audio_samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if n_channels > 1:
            audio_samples = audio_samples.reshape(-1, n_channels).mean(axis=1)

        samples_per_frame = int(sample_rate / fps)
        total_video_frames = max_frames if max_frames is not None else int(np.ceil(len(audio_samples) / samples_per_frame))
        rms_per_frame = np.zeros(total_video_frames, dtype=np.float32)

        for fidx in range(total_video_frames):
            start_s = fidx * samples_per_frame
            end_s = min(start_s + samples_per_frame, len(audio_samples))
            if start_s < len(audio_samples) and end_s > start_s:
                chunk = audio_samples[start_s:end_s]
                rms_per_frame[fidx] = np.sqrt(np.mean(chunk**2))

        return rms_per_frame
    except Exception as e:
        logger.warning("Failed to compute audio RMS energy: %s", e)
        return np.zeros(0, dtype=np.float32)


def make_blurred_bg(img: np.ndarray, target_w: int = 1080, target_h: int = 1920) -> np.ndarray:
    """Generate a premium blurred background card from the input source frame.

    Applies:
    - 9:16 aspect ratio center cropping (prevents horizontal stretching)
    - Downsample + Gaussian blur
    - 55% brightness darkening
    - Top-to-bottom depth gradient overlay
    - Subtle warm color tone shift (Red +8%, Green +3%)
    """
    img_h, img_w = img.shape[:2]

    # Center-crop input to target 9:16 aspect ratio before blurring to prevent stretching
    target_aspect = target_w / float(target_h)
    src_aspect = img_w / float(img_h)

    if src_aspect > target_aspect:
        crop_w = int(img_h * target_aspect)
        offset_x = (img_w - crop_w) // 2
        img_crop = img[:, offset_x : offset_x + crop_w]
    else:
        crop_h = int(img_w / target_aspect)
        offset_y = (img_h - crop_h) // 2
        img_crop = img[offset_y : offset_y + crop_h, :]

    # Fast downsample blur
    small_h = 180
    small_w = int(small_h * target_aspect)
    small = cv2.resize(img_crop, (small_w, small_h), interpolation=cv2.INTER_AREA)
    blurred_small = cv2.GaussianBlur(small, (21, 21), 0)

    # Scale to full target resolution
    blurred = cv2.resize(blurred_small, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

    # Darken to 55%
    blurred = cv2.convertScaleAbs(blurred, alpha=0.55, beta=0)

    # Gradient overlay for depth
    gradient = np.linspace(0.70, 1.0, target_h, dtype=np.float32).reshape(-1, 1, 1)
    blurred = np.clip(blurred.astype(np.float32) * gradient, 0, 255).astype(np.uint8)

    # Warm color tinting
    blurred_f = blurred.astype(np.float32)
    blurred_f[:, :, 2] = np.clip(blurred_f[:, :, 2] * 1.08, 0, 255)  # Red +8%
    blurred_f[:, :, 1] = np.clip(blurred_f[:, :, 1] * 1.03, 0, 255)  # Green +3%
    blurred = blurred_f.astype(np.uint8)

    return blurred


def mux_audio_video(
    video_path: str,
    audio_path: str,
    output_path: str,
    fps: float,
    use_nvenc: bool = False,
) -> None:
    """Mux video + audio into a final MP4 with sync correction."""
    video_codec = (
        ["h264_nvenc", "-preset", "p4", "-cq", "22"]
        if use_nvenc
        else ["libx264", "-preset", "ultrafast", "-crf", "22"]
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-r", str(fps),
        "-c:v", *video_codec,
        "-pix_fmt", "yuv420p",
        "-profile:v", "high",
        "-c:a", "aac",
        "-b:a", "128k",
        "-af", "aresample=async=1000:min_hard_comp=0.100000:first_pts=0",
        "-movflags", "+faststart",
        output_path,
        "-loglevel", "panic",
    ]

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=_FFMPEG_LONG_TIMEOUT_S
    )
    if result.returncode != 0:
        from errors import RenderError
        raise RenderError(f"Audio mux failed: {result.stderr[-500:]}")

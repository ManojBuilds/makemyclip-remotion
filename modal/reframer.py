"""AI Reframer Modal service.

Pipeline (per request):
  1. Resolve source video (download from YouTube if needed)
  2. Probe video info (fps, resolution)
  3. Extract frames + audio with FFmpeg
  4. Detect faces per frame (S3FD)
  5. Track faces across scenes
  6. Score each track for active-speaker detection (ASD)
  7. Render a 1080x1920 vertical video, locking onto the active speaker
  8. Mux original audio back in
  9. Upload to R2

Bug fix in this refactor: In ``render_vertical``, the function now moves the rendered
video (temp_v) to its output path (local_orig) before returning, preventing RenderError
during the audio muxing step where the file is expected to exist.
"""

from __future__ import annotations

import glob
import logging
import math
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

import numpy as np
import modal
from fastapi import File, Form, UploadFile

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import torch
except ImportError:
    torch = None

from config import ai_secret, app, image, youtube_cookies_secret
from errors import DownloadError, InvalidInputError, RenderError, VideoProbeError
from models import ReframeRequest, BatchReframeRequest
from r2_storage import assert_r2_env, upload_to_r2
from utils import StageTimer, is_youtube_url, validate_url
from ytdlp_helper import (
    SEGMENT_DOWNLOAD_PAD_S,
    download_youtube_video,
)

from camera_engine import CAMERA_PROFILES, CameraProfile, calculate_adaptive_pan_alpha
from layout_classifier import classify_layout, is_valid_face_track
from video_utils import compute_audio_rms_energy, make_blurred_bg, mux_audio_video

logger = logging.getLogger("makemyclip.reframer")

# --- Tuning constants for the speaker-locking reframer ---
ACTIVE_SPEAKER_THRESHOLD = 0.5  # ASD score must exceed this to count as "speaking"
DEAD_ZONE_PX = 40  # Prevent faces from touching the edges (reduced to 40px for faster camera response)
SPEAKER_HOLD_SECONDS = 1.5  # hold last speaker through brief pauses
FACE_COUNT_WINDOW_LEN = 11  # frames used to stabilize face-count decision
LETTERBOX_TARGET_HEIGHT_RATIO = 0.68
ANALYSIS_FPS = 25.0  # TalkNet's audio/visual frontends assume this rate

# --- Zoom Punch (emphasis zoom on audio peaks) ---
ZOOM_PUNCH_MAGNITUDE = 0.07       # Max extra zoom on audio spike (7% tighter crop)
ZOOM_PUNCH_DECAY_FRAMES = 14      # Cosine ease-out duration (~0.56s at 25fps)
ZOOM_PUNCH_RMS_WINDOW = 50        # Rolling window for RMS baseline (2s at 25fps)
ZOOM_PUNCH_SPIKE_THRESHOLD = 1.8  # RMS must exceed baseline by this factor to trigger
ZOOM_PUNCH_COOLDOWN_FRAMES = 20   # Minimum frames between consecutive punches

# --- Ken Burns slow drift for static scenes ---
KEN_BURNS_ACTIVATE_AFTER_S = 3.0  # Seconds of no movement before drift starts
KEN_BURNS_ZOOM_RATE = 0.0008      # Zoom-in per frame (~2% per second at 25fps)
KEN_BURNS_DRIFT_RATE = 0.3        # Lateral drift px per frame
KEN_BURNS_MAX_ZOOM = 0.04         # Maximum cumulative zoom from Ken Burns (4%)

# --- Split-screen active speaker highlight ---
SPLIT_SPEAKER_ZOOM_BOOST = 1.05   # 5% tighter crop on active speaker panel
SPLIT_LISTENER_DIM = 0.88         # Dim listener panel to 88% brightness

# A 90s clip seek into a 2hr source can take a while — use a generous limit
# so a stalled ffmpeg doesn't hang the worker. 20 minutes covers the worst
# case observed in production.
_FFMPEG_LONG_TIMEOUT_S = 1200
_FFMPEG_SHORT_TIMEOUT_S = 60


# ─────────────────────────────────────────────────────────────────────
#  CameraProfile: tunable camera behavior presets
# ─────────────────────────────────────────────────────────────────────
from dataclasses import dataclass, field


@dataclass
class CameraProfile:
    """Tunable camera behavior preset.

    Groups all the scattered magic numbers that control pan speed, zoom,
    dead zones, and framing into a single, swappable object.  Use the
    ``PROFILES`` dict to select a preset by name (e.g., ``"podcast"``).
    """

    # --- Framing ---
    face_crop_ratio: float = 0.106        # Face fills this fraction of 1920px height
    face_vertical_anchor: float = 0.22    # Face positioned at this % from top
    split_face_anchor: float = 0.38       # Face at this % from top in split panels

    # --- Pan speed ---
    pan_alpha_min: float = 0.05           # Minimum pan speed (sigmoid baseline)
    pan_alpha_max: float = 0.35           # Maximum pan speed at large distances
    pan_sigmoid_center: float = 150.0     # Distance (px) at sigmoid midpoint
    pan_sigmoid_steepness: float = 0.025  # Sigmoid steepness factor

    # --- Dead zones ---
    dead_zone_px: float = 40.0            # Pixel dead zone on X before pan starts
    dead_zone_y_px: float = 15.0          # Pixel dead zone on Y
    dead_zone_scale_pct: float = 0.10     # 10% dead zone on scale shifts

    # --- Speaker switching ---
    speaker_hold_s: float = 1.5           # Seconds to hold speaker after silence
    min_cut_s: float = 0.8               # Minimum time before speaker switch
    look_ahead_frames: int = 8            # Interjection filter look-ahead

    # --- Zoom punch ---
    zoom_punch_magnitude: float = 0.07    # Emphasis zoom intensity
    zoom_punch_spike_threshold: float = 1.8
    zoom_punch_cooldown: int = 20

    # --- Smoothing ---
    vertical_dampen: float = 0.5          # Dampen vertical pan by this factor
    scale_smooth_alpha: float = 0.15      # EMA alpha for scale changes
    split_smooth_alpha: float = 0.04      # Split-screen tracking alpha
    split_dead_zone: float = 25.0         # Split-screen dead zone (px)

    # --- Edge handling ---
    edge_widen_threshold: float = 0.25    # Distance from edge (fraction) to trigger widening
    edge_widen_factor: float = 0.88       # Widen crop by this factor near edges


# Pre-built profiles for different content types
CAMERA_PROFILES = {
    "default": CameraProfile(),
    "podcast": CameraProfile(
        pan_alpha_max=0.20,       # Slower pans — podcasters don't move much
        min_cut_s=1.2,            # Longer hold before switching
        dead_zone_px=50.0,        # Wider dead zone for stability
        zoom_punch_magnitude=0.05,  # Subtler emphasis zoom
    ),
    "interview": CameraProfile(
        pan_alpha_max=0.40,       # Faster pans — interviewees face each other
        face_crop_ratio=0.12,     # Tighter face framing
        min_cut_s=0.6,            # Quick switches in rapid conversation
        zoom_punch_magnitude=0.08,
    ),
    "presentation": CameraProfile(
        pan_alpha_max=0.15,       # Slow, deliberate pans
        dead_zone_px=60.0,        # Very stable
        face_crop_ratio=0.09,     # Wider shot to capture gestures
        zoom_punch_spike_threshold=2.0,  # Only on very loud emphasis
    ),
}


def mux_audio_video(
    video_path: str,
    audio_path: str,
    output_path: str,
    fps: float,
    use_nvenc: bool = False,
) -> None:
    """Mux video + audio into a final MP4 with sync correction.

    Replaces the 3× copy-pasted FFmpeg mux command that was scattered across
    reframe(), batch_reframe(), and the batch fallback path.
    """
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
        raise RenderError(f"Audio mux failed: {result.stderr[-500:]}")


def slice_tracks_and_scores(tracks, scores, sf, ef):
    import numpy as np
    sliced_tracks = []
    sliced_scores = []
    for tidx, tr in enumerate(tracks):
        track_frames = tr["track"]["frame"]
        mask = (track_frames >= sf) & (track_frames < ef)
        if not np.any(mask):
            continue

        indices = np.where(mask)[0]
        new_track = {
            "track": {
                "frame": track_frames[indices] - sf,
            },
            "proc_track": {
                "x": tr["proc_track"]["x"][indices],
                "y": tr["proc_track"]["y"][indices],
                "s": tr["proc_track"]["s"][indices],
            },
        }
        sc = scores[tidx]
        new_scores = (
            sc[indices]
            if len(sc) > len(indices)
            else sc[indices[: len(sc)]]
        )
        sliced_tracks.append(new_track)
        sliced_scores.append(new_scores)
    return sliced_tracks, sliced_scores


def annotate_transcript_layout(transcript, frame_layout, crop_mode, fps):
    if not transcript:
        return transcript

    for block in transcript:
        if not isinstance(block, dict):
            continue
        words_list = block.get("words", [])
        if not isinstance(words_list, list):
            continue
        for w in words_list:
            if not isinstance(w, dict):
                continue
            w_start = w.get("start", 0.0)
            fidx = int(w_start * fps)
            
            if crop_mode in ("split", "letterbox"):
                w["layout"] = crop_mode
            elif crop_mode in ("reframe", "auto"):
                if frame_layout and 0 <= fidx < len(frame_layout):
                    val = frame_layout[fidx]
                    w["layout"] = "reframe" if val == "single" else val
                else:
                    w["layout"] = "reframe"
            else:
                w["layout"] = "reframe"
    return transcript


def compute_audio_rms_energy(audio_path: str, fps: float, total_frames: int) -> list[float]:
    """Compute per-frame RMS audio energy for zoom punch detection.

    Reads the 16kHz mono WAV that the pipeline already extracts and computes
    RMS energy in windows aligned to video frames.  Returns a list of length
    ``total_frames`` with normalized RMS values (0.0–1.0).
    """
    import numpy as np

    try:
        from scipy.io import wavfile

        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            return [0.0] * total_frames

        sr, aud = wavfile.read(audio_path)
        if len(aud) == 0:
            return [0.0] * total_frames

        # Convert to float32 normalized
        if aud.dtype == np.int16:
            aud = aud.astype(np.float32) / 32768.0
        elif aud.dtype == np.int32:
            aud = aud.astype(np.float32) / 2147483648.0
        else:
            aud = aud.astype(np.float32)

        # If stereo, take mono average
        if aud.ndim > 1:
            aud = aud.mean(axis=1)

        samples_per_frame = int(sr / fps) if fps > 0 else sr // 25
        rms_per_frame = []
        for fidx in range(total_frames):
            start_sample = fidx * samples_per_frame
            end_sample = start_sample + samples_per_frame
            if start_sample >= len(aud):
                rms_per_frame.append(0.0)
            else:
                chunk = aud[start_sample:min(end_sample, len(aud))]
                rms = float(np.sqrt(np.mean(chunk ** 2))) if len(chunk) > 0 else 0.0
                rms_per_frame.append(rms)

        # Normalize to 0.0–1.0 range
        max_rms = max(rms_per_frame) if rms_per_frame else 1.0
        if max_rms > 0:
            rms_per_frame = [r / max_rms for r in rms_per_frame]

        return rms_per_frame
    except Exception as e:
        logger.warning("Failed to compute audio RMS energy: %s", e)
        return [0.0] * total_frames


def get_autocast_context(device_type: str = "cuda", enabled: bool = True):
    """Return modern PyTorch 2.x torch.amp.autocast context with fallback for PyTorch 1.x."""
    import torch
    if hasattr(torch, "amp") and hasattr(torch.amp, "autocast"):
        return torch.amp.autocast(device_type=device_type, enabled=enabled)
    elif hasattr(torch.cuda, "amp") and hasattr(torch.cuda.amp, "autocast"):
        return torch.cuda.amp.autocast(enabled=enabled)
    else:
        from contextlib import nullcontext
        return nullcontext()


def is_valid_face_track(tr, sc, frame_height: float = 2160.0) -> tuple[bool, float, float, float, float]:
    """Evaluate if a face track is valid/real (not noise, background poster, or fake face).

    Applies the following filters:
    1. Size Threshold Filter: Ignore faces/photos whose bounding height size is less than 5% of frame height (or mean size < 75px on 4K)
       to automatically filter out background posters, album art, and desk photographs.
    2. ASD & Movement Filter: Static background images with low ASD score (< 0.25) and static position (movement < 5.0px) are purged.
    """
    import numpy as np

    max_score = float(np.max(sc)) if len(sc) > 0 else 0.0
    xs = tr["proc_track"]["x"]
    ys = tr["proc_track"]["y"]
    movement = float(np.std(xs) + np.std(ys)) if len(xs) > 0 else 0.0

    sizes = tr["proc_track"]["s"]
    mean_size = float(np.mean(sizes)) if len(sizes) > 0 else 1.0
    rel_movement = movement / mean_size if mean_size > 0 else 0.0

    # 5% of frame height threshold (e.g. 108px on 4K 2160p, 54px on 1080p)
    min_size_threshold = max(54.0, frame_height * 0.05)

    is_valid = True
    if mean_size < min_size_threshold and max_score < 0.35:
        # Background poster / desk photo on shelf
        is_valid = False
    elif max_score < 0.25 and movement < 5.0:
        # Static background element
        is_valid = False
    elif max_score < 0.12 and (movement < 10.0 and rel_movement < 0.08):
        is_valid = False

    return is_valid, max_score, movement, rel_movement, mean_size


@app.cls(
    gpu="L4",
    image=image,
    timeout=1800,  # extended timeout for long videos (up to 2 hrs)
    secrets=[ai_secret, youtube_cookies_secret],
    max_containers=20,
    min_containers=0,
)
@modal.concurrent(max_inputs=2)
class AIReframe:
    @modal.enter()
    def setup(self):

        # 1. Load the face detector + TalkNCE active-speaker contrastive model
        os.chdir("/root/asd")
        sys.path.append("/root/asd")
        from ASD import ASD
        from talknce import create_talknce_engine
        from model.faceDetector.s3fd import S3FD

        self.DET = S3FD(device="cuda")
        self.ASD_MODEL = ASD()
        self.ASD_MODEL.loadParameters("/root/asd/weight/finetuning_TalkSet.model")
        self.ASD_MODEL.eval()
        self.ASD_MODEL.cuda()

        # Initialize TalkNCE contrastive engine (94.1% mAP accuracy)
        self.TALKNCE_MODEL = create_talknce_engine(
            weight_path="/root/asd/weight/finetuning_TalkSet.model",
            device="cuda" if torch.cuda.is_available() else "cpu",
        )

        # 2. Probe NVENC once at startup — saves a try/except per render
        self.use_nvenc = self._probe_nvenc()
        logger.info("NVENC available: %s", self.use_nvenc)

        # 3. Validate required env vars upfront so we fail fast on misconfig
        assert_r2_env()

    @staticmethod
    def _probe_nvenc() -> bool:
        try:
            import ffmpegcv

            probe_path = tempfile.mktemp(suffix=".mp4")
            writer = ffmpegcv.VideoWriterNV(file=probe_path, fps=25, resize=(128, 128))
            writer.release()
            if os.path.exists(probe_path):
                os.remove(probe_path)
            return True
        except Exception:
            return False

    # ─────────────────────────────────────────────────────────────────
    #  Video probing
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def get_video_info(video_path: str) -> dict:
        import json as _json

        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=r_frame_rate,duration,width,height",
                "-of",
                "json",
                video_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            data = _json.loads(result.stdout)
            stream = data["streams"][0]

            rate = stream["r_frame_rate"]
            if "/" in rate:
                num, den = map(int, rate.split("/"))
                fps = num / den if den != 0 else 25.0
            else:
                fps = float(rate)

            return {
                "fps": fps,
                "duration": float(stream.get("duration", 0)),
                "width": stream.get("width"),
                "height": stream.get("height"),
            }
        except Exception as e:
            logger.warning("Error probing video: %s", e)
            return {"fps": 25.0, "duration": 0, "width": 1280, "height": 720}

    def classify_layout(self, tracks, scores, width: int, height: int) -> str:
        """Analyze face tracks and determine the optimal layout mode globally."""
        return classify_layout(tracks, scores, width, height)


    # ─────────────────────────────────────────────────────────────────
    #  Track + score (face tracking + ASD)
    # ─────────────────────────────────────────────────────────────────
    def get_tracks_and_scores(
        self,
        video_url: str,
        start_time: float,
        duration: float,
        work_dir: str,
        fps: float = 25.0,
        audio_url: str | None = None,
        target_fps: float | None = None,
        detect_skip: int = 1,
    ):
        import math
        import warnings
        from concurrent.futures import ThreadPoolExecutor, as_completed

        import cv2
        import numpy as np
        import python_speech_features
        import torch
        from scenedetect import SceneManager, open_video
        from scenedetect.detectors import ContentDetector
        from scipy import signal
        from scipy.interpolate import interp1d
        from scipy.io import wavfile

        warnings.filterwarnings(
            "ignore",
            message="An output with one or more elements was resized",
            category=UserWarning,
            module=r".*box_utils.*",
        )

        if not hasattr(self, "DET") or self.DET is None:
            import sys
            if "/root/asd" not in sys.path:
                sys.path.append("/root/asd")
            from model.faceDetector.s3fd import S3FD
            self.DET = S3FD(device="cuda" if torch.cuda.is_available() else "cpu")

        if not hasattr(self, "ASD_MODEL") or self.ASD_MODEL is None:
            import sys
            if "/root/asd" not in sys.path:
                sys.path.append("/root/asd")
            from ASD import ASD
            from talknce import create_talknce_engine
            self.ASD_MODEL = ASD()
            if os.path.exists("/root/asd/weight/finetuning_TalkSet.model"):
                self.ASD_MODEL.loadParameters("/root/asd/weight/finetuning_TalkSet.model")
            self.ASD_MODEL.eval()
            if torch.cuda.is_available():
                self.ASD_MODEL.cuda()
            self.TALKNCE_MODEL = create_talknce_engine(
                weight_path="/root/asd/weight/finetuning_TalkSet.model",
                device="cuda" if torch.cuda.is_available() else "cpu",
            )

        pyavi_path = os.path.join(work_dir, "pyavi")
        pyframes_path = os.path.join(work_dir, "pyframes")
        pywork_path = os.path.join(work_dir, "pywork")
        pycrop_path = os.path.join(work_dir, "pycrop")
        for p in (pyavi_path, pyframes_path, pywork_path, pycrop_path):
            os.makedirs(p, exist_ok=True)

        # 1. Decode frames to a disk-backed numpy memmap via FFmpeg pipe.
        #    Instead of holding all frames in RAM (which explodes to 4.8GB for
        #    60s of 720p), we write raw bytes to disk and memory-map them.
        #    The OS pages frames in/out as needed, keeping peak RAM low.
        logger.info("Decoding frames to disk-backed memmap (memory-safe pipeline)...")

        # First, probe dimensions so we can calculate raw frame sizes
        probe_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0:s=x",
            video_url,
        ]
        probe_out = subprocess.run(
            probe_cmd, capture_output=True, text=True, timeout=30
        )
        try:
            pw, ph = map(int, probe_out.stdout.strip().split("x"))
        except (ValueError, AttributeError):
            pw, ph = 1280, 720  # safe fallback

        # Decode all frames as raw BGR24, scaled down to 360p height for speed and I/O efficiency
        ph_scaled = 360
        pw_scaled = int(round((pw * 360 / ph) / 2.0)) * 2

        raw_frames_path = os.path.join(work_dir, "raw_frames.bin")
        decode_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            video_url,
            "-ss",
            str(start_time),
            "-t",
            str(duration),
            "-map",
            "0:v:0",
            "-vf",
            "scale=-2:360",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-threads",
            "4",
            "-loglevel",
            "panic",
            raw_frames_path,
        ]
        subprocess.run(
            decode_cmd,
            check=True,
            timeout=_FFMPEG_LONG_TIMEOUT_S,
        )
        frame_size = pw_scaled * ph_scaled * 3
        raw_file_size = os.path.getsize(raw_frames_path)
        total_frames_decoded = raw_file_size // frame_size if frame_size > 0 else 0
        logger.info(
            "Decoded %d frames (scaled down to %dx%d) to disk (%.1f MB file, ~200 MB peak RAM)",
            total_frames_decoded,
            pw_scaled,
            ph_scaled,
            raw_file_size / (1024 * 1024),
        )

        # Memory-map the raw frames file for zero-copy random access
        # The OS manages paging — only accessed frames are loaded into RAM
        if total_frames_decoded > 0:
            frames_mmap = np.memmap(
                raw_frames_path,
                dtype=np.uint8,
                mode="r",
                shape=(total_frames_decoded, ph_scaled, pw_scaled, 3),
            )
            # Wrap in a lightweight accessor that matches the old list[ndarray] interface
            frames_mem = frames_mmap
        else:
            frames_mem = np.empty((0, ph_scaled, pw_scaled, 3), dtype=np.uint8)

        # Build a 320-wide proxy for scene detection directly from the source video
        # via ffmpeg (no Python piping needed — saves ~6-10s per cluster)
        proxy_video = os.path.join(work_dir, "proxy.mp4")
        proxy_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            video_url,
            "-ss",
            str(start_time),
            "-t",
            str(duration),
            "-vf",
            "scale=320:-2",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-an",
            proxy_video,
            "-loglevel",
            "panic",
        ]
        subprocess.run(proxy_cmd, check=True, timeout=120)

        # 2. Extract audio at 16 kHz mono for ASD
        #    Audio uses a separate input (pre-extracted segment) so it stays
        #    as its own command.
        audio_path = os.path.join(pyavi_path, "audio.wav")
        if audio_url:
            audio_cmd = [
                "ffmpeg",
                "-y",
                "-i",
                audio_url,
                "-qscale:a",
                "0",
                "-ac",
                "1",
                "-vn",
                "-threads",
                "4",
                "-ar",
                "16000",
                audio_path,
                "-loglevel",
                "panic",
            ]
        else:
            audio_cmd = [
                "ffmpeg",
                "-y",
                "-i",
                video_url,
                "-ss",
                str(start_time),
                "-t",
                str(duration),
                "-qscale:a",
                "0",
                "-ac",
                "1",
                "-vn",
                "-threads",
                "4",
                "-ar",
                "16000",
                audio_path,
                "-loglevel",
                "panic",
            ]
        subprocess.run(
            audio_cmd,
            check=True,
            timeout=_FFMPEG_LONG_TIMEOUT_S,
        )
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            logger.warning(
                "Main audio extraction failed or produced empty file: %s",
                audio_path,
            )

        # In letterbox mode we NO LONGER skip face tracking! We use it for intelligent pan-and-scan inside the letterbox card.

        def bb_iou(boxA, boxB):
            xA, yA = max(boxA[0], boxB[0]), max(boxA[1], boxB[1])
            xB, yB = min(boxA[2], boxB[2]), min(boxA[3], boxB[3])
            inter = max(0, xB - xA) * max(0, yB - yA)
            areaA = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
            areaB = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
            return (
                inter / float(areaA + areaB - inter) if (areaA + areaB - inter) else 0
            )

        def track_shot(scene_faces):
            tracks = []
            while True:
                track = []
                for frame_faces in scene_faces:
                    for face in list(frame_faces):
                        if not track:
                            track.append(face)
                            frame_faces.remove(face)
                        elif face["frame"] - track[-1]["frame"] <= max(
                            10, 3 * _DETECT_SKIP
                        ):
                            if bb_iou(face["bbox"], track[-1]["bbox"]) > 0.5:
                                track.append(face)
                                frame_faces.remove(face)
                                continue
                        else:
                            break
                if not track:
                    break
                min_track_len = max(3, 10 // _DETECT_SKIP)
                if len(track) > min_track_len:
                    fnum = np.array([f["frame"] for f in track])
                    bbox = np.array([np.array(f["bbox"]) for f in track])
                    fi = np.arange(fnum[0], fnum[-1] + 1)
                    bi = np.stack(
                        [interp1d(fnum, bbox[:, j])(fi) for j in range(4)], axis=1
                    )
                    tracks.append({"frame": fi, "bbox": bi})
            return tracks

        def crop_video(track, crop_file, audio_path_local, frames_local, fps_local):
            dets = {
                "x": signal.medfilt(
                    (track["bbox"][:, 0] + track["bbox"][:, 2]) / 2, 13
                ),
                "y": signal.medfilt(
                    (track["bbox"][:, 1] + track["bbox"][:, 3]) / 2, 13
                ),
                "s": signal.medfilt(
                    np.maximum(
                        track["bbox"][:, 3] - track["bbox"][:, 1],
                        track["bbox"][:, 2] - track["bbox"][:, 0],
                    )
                    / 2,
                    13,
                ),
            }
            vf = []
            cs = 0.40
            for fidx, frame in enumerate(track["frame"]):
                safe_frame = min(int(frame), len(frames_local) - 1)
                bs = dets["s"][fidx]
                bsi = int(bs * (1 + 2 * cs))
                img = frames_local[safe_frame]
                pad = np.pad(
                    img,
                    ((bsi, bsi), (bsi, bsi), (0, 0)),
                    "constant",
                    constant_values=110,
                )
                my, mx = dets["y"][fidx] + bsi, dets["x"][fidx] + bsi
                face = pad[
                    int(my - bs) : int(my + bs * (1 + 2 * cs)),
                    int(mx - bs * (1 + cs)) : int(mx + bs * (1 + cs)),
                ]
                if face.size == 0 or face.shape[0] == 0 or face.shape[1] == 0:
                    gray_crop = np.full((112, 112), 110, dtype=np.uint8)
                else:
                    resized_face = cv2.resize(face, (224, 224))
                    if resized_face.ndim == 3:
                        gray = cv2.cvtColor(resized_face, cv2.COLOR_BGR2GRAY)
                    else:
                        gray = resized_face
                    gray_crop = gray[56:168, 56:168]
                vf.append(gray_crop)

            vf_arr = np.array(vf)

            # Extract audio slice for TalkNet MFCC
            audS = track["frame"][0] / fps_local
            audE = (track["frame"][-1] + 1) / fps_local
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    audio_path_local,
                    "-async",
                    "1",
                    "-ac",
                    "1",
                    "-vn",
                    "-acodec",
                    "pcm_s16le",
                    "-ar",
                    "16000",
                    "-ss",
                    f"{audS:.3f}",
                    "-to",
                    f"{audE:.3f}",
                    crop_file + ".wav",
                    "-loglevel",
                    "panic",
                ],
                timeout=_FFMPEG_SHORT_TIMEOUT_S,
            )
            return {"track": track, "proc_track": dets, "vf": vf_arr}

        # 4. Scene detection on the proxy
        video = open_video(proxy_video)
        sm = SceneManager()
        # Lower than the default 27.0 so subtle podcast cuts are picked up
        sm.add_detector(ContentDetector(threshold=20.0))
        sm.detect_scenes(video)
        scenes = sm.get_scene_list()

        total_frames = len(frames_mem)

        # If scene detection finds nothing (very short / static clip),
        # treat the entire clip as a single scene.
        if not scenes:
            logger.warning("No scenes detected — treating entire clip as one scene")

            class _FakeTimecode:
                def __init__(self, n: int):
                    self._n = n

                def get_frames(self) -> int:
                    return self._n

            scenes = [(_FakeTimecode(0), _FakeTimecode(total_frames))]

        # Extract starting frame of every scene cut for 0ms delay re-detection
        scene_cut_frames = {shot[0].get_frames() for shot in scenes}

        # 5. Detect faces per frame (IN-MEMORY, hybrid keyframing with smooth linear interpolation)
        _DETECT_SKIP = max(1, int(detect_skip))
        detected_faces = [None] * total_frames

        # Identify keyframe indices where face detection must run
        keyframe_indices = []
        for fidx in range(total_frames):
            is_scene_cut = fidx in scene_cut_frames
            if fidx == 0 or fidx == total_frames - 1 or is_scene_cut or (_DETECT_SKIP > 1 and fidx % _DETECT_SKIP == 0):
                keyframe_indices.append(fidx)
        keyframe_indices = sorted(list(set(keyframe_indices)))

        # Run face detection on keyframes
        for kidx in keyframe_indices:
            img = frames_mem[kidx]
            h, w = img.shape[:2]
            target_detect_h = 960 if h >= 1080 else min(h, 640)
            if h > target_detect_h:
                scale = target_detect_h / float(h)
                img_detect = cv2.resize(img, (int(w * scale), target_detect_h))
                res = self.DET.detect_faces(
                    cv2.cvtColor(img_detect, cv2.COLOR_BGR2RGB),
                    conf_th=0.4,
                    scales=[1.0],
                )
                for b in res:
                    b[0:4] /= scale
            else:
                res = self.DET.detect_faces(
                    cv2.cvtColor(img, cv2.COLOR_BGR2RGB),
                    conf_th=0.4,
                    scales=[1.0],
                )
            detected_faces[kidx] = [
                {"frame": kidx, "bbox": b[:-1].tolist(), "conf": float(b[-1])} for b in res
            ]

        # Fill intermediate frames via linear interpolation between keyframes
        for i in range(len(keyframe_indices) - 1):
            fa = keyframe_indices[i]
            fb = keyframe_indices[i + 1]
            gap = fb - fa
            if gap <= 1:
                continue

            faces_a = detected_faces[fa]
            faces_b = detected_faces[fb]

            # If either side is a scene cut cutpoint, don't interpolate across shot boundary
            if fb in scene_cut_frames:
                for step in range(1, gap):
                    fidx = fa + step
                    detected_faces[fidx] = [
                        {"frame": fidx, "bbox": list(f["bbox"]), "conf": f["conf"]}
                        for f in faces_a
                    ]
                continue

            # Linear interpolation for matching bboxes
            for step in range(1, gap):
                fidx = fa + step
                alpha = step / float(gap)
                frame_faces = []
                used_b = set()

                for f_a in faces_a:
                    box_a = f_a["bbox"]
                    best_b_idx = None
                    best_iou = 0.0
                    for b_idx, f_b in enumerate(faces_b):
                        if b_idx in used_b:
                            continue
                        box_b = f_b["bbox"]
                        xA, yA = max(box_a[0], box_b[0]), max(box_a[1], box_b[1])
                        xB, yB = min(box_a[2], box_b[2]), min(box_a[3], box_b[3])
                        inter = max(0, xB - xA) * max(0, yB - yA)
                        areaA = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
                        areaB = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
                        iou = inter / float(areaA + areaB - inter) if (areaA + areaB - inter) > 0 else 0
                        if iou > 0.25 and iou > best_iou:
                            best_iou = iou
                            best_b_idx = b_idx

                    if best_b_idx is not None:
                        used_b.add(best_b_idx)
                        box_b = faces_b[best_b_idx]["bbox"]
                        interp_box = [
                            (1 - alpha) * box_a[k] + alpha * box_b[k] for k in range(4)
                        ]
                        interp_conf = (1 - alpha) * f_a["conf"] + alpha * faces_b[best_b_idx]["conf"]
                        frame_faces.append({"frame": fidx, "bbox": interp_box, "conf": interp_conf})
                    else:
                        frame_faces.append({"frame": fidx, "bbox": list(box_a), "conf": f_a["conf"]})

                detected_faces[fidx] = frame_faces

        # 6. Build tracks per scene
        all_tracks = []
        for shot in scenes:
            sf, ef = shot[0].get_frames(), shot[1].get_frames()
            if ef - sf >= 10:
                all_tracks.extend(track_shot(detected_faces[sf:ef]))

        # 7. Crop tracks in parallel (I/O-bound)
        vid_tracks = [None] * len(all_tracks)

        def _crop(args):
            i, t = args
            return i, crop_video(
                t,
                os.path.join(pycrop_path, "%05d" % i),
                audio_path,
                frames_mem,
                fps,
            )

        # --- OPTIMIZATION: Skip ASD for single-speaker clips ---
        # If only 1 track found, there's nothing to disambiguate. Skip the
        # entire crop_video + ASD pipeline (saves 15-25s per solo clip).
        if len(all_tracks) == 1:
            logger.info("Single speaker detected — skipping ASD (fast path)")
            tr = all_tracks[0]
            dets = {
                "x": signal.medfilt((tr["bbox"][:, 0] + tr["bbox"][:, 2]) / 2, 13),
                "y": signal.medfilt((tr["bbox"][:, 1] + tr["bbox"][:, 3]) / 2, 13),
                "s": signal.medfilt(
                    np.maximum(
                        tr["bbox"][:, 3] - tr["bbox"][:, 1],
                        tr["bbox"][:, 2] - tr["bbox"][:, 0],
                    )
                    / 2,
                    13,
                ),
            }
            vid_tracks = [{"track": tr, "proc_track": dets}]
            # Assume speaking for entire track (score = 1.0)
            all_scores = [np.ones(len(tr["frame"]))]
        else:
            with ThreadPoolExecutor(max_workers=8) as ex:
                futures = {
                    ex.submit(_crop, (i, t)): i for i, t in enumerate(all_tracks)
                }
                for fut in as_completed(futures):
                    i, result = fut.result()
                    vid_tracks[i] = result

            # 8. Score each track with ASD
            all_scores = []
            for idx, tr in enumerate(vid_tracks):
                track_frame_count = len(tr["track"]["frame"])

                wav_file = os.path.join(pycrop_path, "%05d.wav" % idx)
                if not os.path.exists(wav_file) or os.path.getsize(wav_file) == 0:
                    logger.warning(
                        "Audio file %s missing or empty. Zeroing scores for track %d.",
                        wav_file,
                        idx,
                    )
                    all_scores.append(np.zeros(track_frame_count))
                    continue

                sr, aud = wavfile.read(wav_file)
                # Cleanup temporary audio slice file immediately after reading
                try:
                    os.remove(wav_file)
                except OSError:
                    pass

                if len(aud) == 0:
                    all_scores.append(np.zeros(track_frame_count))
                    continue

                af = python_speech_features.mfcc(
                    aud, 16000, numcep=13, winlen=0.025, winstep=0.010
                )

                # Direct in-memory face crops from RAM (zero disk I/O)
                vf = tr.get("vf")
                if vf is None or len(vf) == 0:
                    all_scores.append(np.zeros(track_frame_count))
                    continue

                # crop_video() writes one frame per NATIVE video frame, but
                # TalkNet's audio frontend always emits embeddings at a fixed
                # 25Hz. Feeding native-fps video straight into the visual
                # frontend desyncs the two streams: the window slicing below
                # assumes matching rates and silently keeps only the front
                # `25/native_fps` fraction of each window's video, dropping
                # the rest (not erroring). Resample to ANALYSIS_FPS first.
                native_fps = fps if fps and fps > 0 else ANALYSIS_FPS
                if abs(native_fps - ANALYSIS_FPS) > 0.5:
                    duration_s = len(vf) / native_fps
                    n_resampled = max(1, int(round(duration_s * ANALYSIS_FPS)))
                    resample_idx = np.linspace(0, len(vf) - 1, n_resampled).round().astype(int)
                    vf_analysis = vf[resample_idx]
                else:
                    vf_analysis = vf

                audio_steps = af.shape[0] // 4 * 4
                video_steps = int(vf_analysis.shape[0] / ANALYSIS_FPS * 100) // 4 * 4

                n_audio_steps = min(audio_steps, video_steps)
                n_video_frames = int(n_audio_steps / 100.0 * ANALYSIS_FPS)

                af = af[:n_audio_steps, :]
                vf_analysis = vf_analysis[:n_video_frames, :, :]

                if n_audio_steps == 0 or n_video_frames == 0:
                    all_scores.append(np.zeros(track_frame_count))
                    continue

                length = n_audio_steps / 100.0

                with torch.no_grad():
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                    use_amp = torch.cuda.is_available()
                    with get_autocast_context(device_type=device, enabled=use_amp):
                        inA_full = torch.FloatTensor(af).unsqueeze(0).to(device)
                        inV_full = torch.FloatTensor(vf_analysis).unsqueeze(0).to(device)
                        if hasattr(self, "TALKNCE_MODEL") and self.TALKNCE_MODEL is not None:
                            eA_full = self.TALKNCE_MODEL.forward_audio_frontend(inA_full)
                            eV_full = self.TALKNCE_MODEL.forward_visual_frontend(inV_full)
                        else:
                            eA_full = self.ASD_MODEL.model.forward_audio_frontend(inA_full)
                            eV_full = self.ASD_MODEL.model.forward_visual_frontend(inV_full)

                tr_scores = []
                for dur in range(1, 7):
                    batch = int(math.ceil(length / dur))
                    scs = []
                    for i in range(batch):
                        a_start = i * dur * 25
                        a_end = (i + 1) * dur * 25
                        # Both streams now share ANALYSIS_FPS — same slice as
                        # a_start/a_end, kept separate for clarity.
                        v_start = int(round(i * dur * ANALYSIS_FPS))
                        v_end = int(round((i + 1) * dur * ANALYSIS_FPS))

                        eA = eA_full[:, a_start:a_end, :]
                        eV = eV_full[:, v_start:v_end, :]

                        if eA.shape[1] == 0 or eV.shape[1] == 0:
                            continue

                        min_steps = min(eA.shape[1], eV.shape[1])
                        eA = eA[:, :min_steps, :]
                        eV = eV[:, :min_steps, :]

                        with torch.no_grad():
                            if hasattr(self, "TALKNCE_MODEL") and self.TALKNCE_MODEL is not None:
                                combined_prob = self.TALKNCE_MODEL.forward_contrastive_evaluation(eA, eV)
                                scs.extend(combined_prob.cpu().numpy().tolist())
                            else:
                                out = self.ASD_MODEL.model.forward_audio_visual_backend(
                                    eA, eV
                                )
                                scs.extend(self.ASD_MODEL.lossAV.forward(out, labels=None))

                    if scs:
                        tr_scores.append(scs)

                if tr_scores:
                    min_len = min(len(s) for s in tr_scores)
                    scores_25hz = np.round(
                        np.mean([s[:min_len] for s in tr_scores], axis=0), 1
                    ).astype(float)
                else:
                    scores_25hz = np.zeros(0)

                # scores_25hz is at ANALYSIS_FPS — upsample onto the native
                # per-frame grid so it's guaranteed 1:1 with track_frame_count,
                # which is what analysis.json / render_vertical expect.
                if len(scores_25hz) == 0:
                    scores_arr = np.zeros(track_frame_count)
                elif len(scores_25hz) == 1:
                    scores_arr = np.full(track_frame_count, scores_25hz[0])
                else:
                    src_idx = np.linspace(0, track_frame_count - 1, num=len(scores_25hz))
                    scores_arr = np.interp(np.arange(track_frame_count), src_idx, scores_25hz)

                all_scores.append(scores_arr)

        scene_bounds = [(shot[0].get_frames(), shot[1].get_frames()) for shot in scenes]

        # Scale tracks and proc_tracks back to original video resolution coordinate space
        scale_x = pw / pw_scaled
        scale_y = ph / ph_scaled
        logger.info(
            "Scaling tracks back to original resolution coordinate space (scale_x=%.4f, scale_y=%.4f)...",
            scale_x,
            scale_y,
        )
        for tr in vid_tracks:
            # Scale raw bounding box (tr["track"]["bbox"])
            if "track" in tr and "bbox" in tr["track"]:
                tr["track"]["bbox"][:, [0, 2]] *= scale_x
                tr["track"]["bbox"][:, [1, 3]] *= scale_y
            
            # Scale processed coordinates (tr["proc_track"])
            if "proc_track" in tr:
                tr["proc_track"]["x"] *= scale_x
                tr["proc_track"]["y"] *= scale_y
                tr["proc_track"]["s"] *= scale_y  # s is radius (half-height)

        # Release raw_frames memmap reference and delete raw_frames.bin to save disk space
        del frames_mem
        import gc
        gc.collect()
        try:
            if os.path.exists(raw_frames_path):
                os.remove(raw_frames_path)
                logger.info("Deleted temporary raw_frames.bin to free up space.")
        except OSError as e:
            logger.warning("Could not delete raw_frames.bin: %s", e)

        return (
            vid_tracks,
            all_scores,
            audio_path,
            None,
            pyavi_path,
            scene_bounds,
        )

    # ─────────────────────────────────────────────────────────────────
    #  Vertical render
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def get_smooth_x_for_track(track, total_frames):
        """Return a per-frame x-coordinate array for ``track`` with NaN gaps filled."""
        import numpy as np

        frames = track["track"]["frame"]
        xs = track["proc_track"]["x"]

        full_xs = np.full(total_frames, np.nan)
        for f, x in zip(frames, xs):
            if 0 <= f < total_frames:
                full_xs[f] = x

        # Forward fill
        last_valid = xs[0] if len(xs) > 0 else 0
        for f in range(total_frames):
            if np.isnan(full_xs[f]):
                full_xs[f] = last_valid
            else:
                last_valid = full_xs[f]

        # Backward fill — must use the *first* detected value (now at the end
        # of the array because of forward fill), not the last value left over
        # from the forward pass.
        last_valid = full_xs[total_frames - 1]
        for f in reversed(range(total_frames)):
            if np.isnan(full_xs[f]):
                full_xs[f] = last_valid
            else:
                last_valid = full_xs[f]

        return full_xs

    def get_video_reader(self, filename, ss=0.0, duration=None, use_gpu=False):
        import ffmpegcv
        import os
        if use_gpu and self.use_nvenc:
            try:
                cap = ffmpegcv.VideoCaptureNV(filename)
            except Exception:
                cap = ffmpegcv.VideoCapture(filename)
        else:
            cap = ffmpegcv.VideoCapture(filename)
            
        if ss > 0.0 or duration is not None:
            ss_val = max(0.0, ss)
            t_str = f" -t {duration}" if duration is not None else ""
            if ss_val > 0.0:
                cap.ffmpeg_cmd = cap.ffmpeg_cmd.replace(
                    f' -i "{filename}"',
                    f' -i "{filename}" -ss {ss_val:.3f}{t_str}'
                )
            else:
                cap.ffmpeg_cmd = cap.ffmpeg_cmd.replace(
                    f' -i "{filename}"',
                    f' -i "{filename}"{t_str}'
                )
            # Recompute total count if duration is specified
            if duration is not None:
                cap.count = min(cap.count, int(duration * cap.fps))
        return cap

    def render_vertical(
        self,
        tracks,
        scores,
        frames_mem,
        pyavi_path,
        output_path,
        duration: float | None = None,
        fps: float = 25.0,
        crop_mode: str = "reframe",
        scene_bounds: list | None = None,
        video_path: str | None = None,
        start_time_in_video: float = 0.0,
        audio_wav_path: str | None = None,
    ):
        from collections import deque

        import cv2
        import ffmpegcv
        import numpy as np

        # frames_mem can be None if video_path is provided.
        if video_path is not None and duration is not None:
            max_frames = int(duration * fps)
        else:
            max_frames = len(frames_mem)

        # Build per-frame face lists (with averaged scores) for sticky-speaker logic
        faces = [[] for _ in range(max_frames)]
        # Rolling median smoothing buffer for raw face coordinates per track (filters S3FD detection noise)
        track_coord_buffers = {tidx_item: deque(maxlen=5) for tidx_item in range(len(tracks))}

        for tidx, tr in enumerate(tracks):
            sc = scores[tidx]

            # --- FAKE FACE FILTER ---
            # Source frame height for thresholding
            src_h = frames_mem[0].shape[0] if (frames_mem is not None and len(frames_mem) > 0) else 2160.0
            is_valid, track_max_score, movement, rel_movement, mean_size = is_valid_face_track(tr, sc, frame_height=src_h)

            logger.info(
                "Track %d evaluation: max_score=%.3f, movement=%.3f, rel_movement=%.3f, mean_size=%.3f",
                tidx,
                track_max_score,
                movement,
                rel_movement,
                mean_size,
            )

            if not is_valid:
                logger.info(
                    "Purged fake face track %d (score %.2f, move %.2f, rel_move %.3f, size %.1f)",
                    tidx,
                    track_max_score,
                    movement,
                    rel_movement,
                    mean_size,
                )
                continue

            # Interpolate sparse keyframes (e.g. 5fps detect_skip) to every frame in the track range
            tr_frames = np.array(tr["track"]["frame"], dtype=int)
            tr_x = np.array(tr["proc_track"]["x"], dtype=float)
            tr_y = np.array(tr["proc_track"]["y"], dtype=float)
            tr_s = np.array(tr["proc_track"]["s"], dtype=float)
            tr_scores = np.array(sc, dtype=float)

            min_len = min(len(tr_frames), len(tr_x), len(tr_y), len(tr_s), len(tr_scores))
            if min_len == 0:
                continue

            tr_frames = tr_frames[:min_len]
            tr_x = tr_x[:min_len]
            tr_y = tr_y[:min_len]
            tr_s = tr_s[:min_len]
            tr_scores = tr_scores[:min_len]

            min_f = max(0, tr_frames[0])
            max_f = min(max_frames - 1, tr_frames[-1])

            if len(tr_frames) > 1 and max_f > min_f:
                all_f = np.arange(min_f, max_f + 1)
                interp_x = np.interp(all_f, tr_frames, tr_x)
                interp_y = np.interp(all_f, tr_frames, tr_y)
                interp_s = np.interp(all_f, tr_frames, tr_s)
                interp_sc = np.interp(all_f, tr_frames, tr_scores)
            else:
                all_f = np.array([min_f])
                interp_x = tr_x[:1]
                interp_y = tr_y[:1]
                interp_s = tr_s[:1]
                interp_sc = tr_scores[:1]

            for i, f in enumerate(all_f):
                if f >= max_frames:
                    continue
                score_window = interp_sc[max(i - 7, 0) : min(i + 7, len(interp_sc))]
                avg = float(np.mean(score_window)) if len(score_window) > 0 else 0

                fx = float(interp_x[i])
                fy = float(interp_y[i])
                fs = float(interp_s[i])

                src_w = frames_mem[0].shape[1] if (frames_mem is not None and len(frames_mem) > 0) else 3840.0
                dist_from_center_x = abs(fx - (src_w / 2.0)) / (src_w / 2.0)
                central_bias = max(0.85, 1.0 - 0.15 * dist_from_center_x)
                weighted_score = avg * central_bias

                faces[f].append(
                    {
                        "score": weighted_score,
                        "x": fx,
                        "y": fy,
                        "s": fs,
                        "tidx": tidx,
                    }
                )

        # Pre-identify primary speaker track across the entire clip for instant 0ms framing lock
        valid_tracks = []
        for tidx, tr in enumerate(tracks):
            sc = scores[tidx]
            src_h = frames_mem[0].shape[0] if (frames_mem is not None and len(frames_mem) > 0) else 2160.0
            is_valid, track_max_score, movement, rel_movement, mean_size = is_valid_face_track(tr, sc, frame_height=src_h)
            if is_valid:
                valid_tracks.append((tidx, tr, track_max_score, len(tr["track"]["frame"])))

        # Sort valid tracks by max ASD score (primary active speaker first), then track duration
        valid_tracks.sort(key=lambda item: (item[2], item[3]), reverse=True)

        primary_speaker_init_x = None
        primary_speaker_init_y = None
        primary_speaker_init_s = None

        if valid_tracks:
            # If there is an active face detected directly on frame 0, lock to it immediately
            frame_0_faces = faces[0] if len(faces) > 0 else []
            if frame_0_faces:
                best_f0 = max(frame_0_faces, key=lambda f: f["score"])
                primary_speaker_init_x = float(best_f0["x"])
                primary_speaker_init_y = float(best_f0["y"])
                primary_speaker_init_s = float(best_f0["s"])
            else:
                best_init_track = max(valid_tracks, key=lambda vt: (scores[vt[0]][0] if len(scores[vt[0]]) > 0 else 0, vt[2]))
                top_tidx, top_tr, _, _ = best_init_track
                primary_speaker_init_x = float(top_tr["proc_track"]["x"][0])
                primary_speaker_init_y = float(top_tr["proc_track"]["y"][0])
                primary_speaker_init_s = float(top_tr["proc_track"]["s"][0])
            logger.info("Pre-locked primary speaker at initial pos: x=%.1f, y=%.1f", primary_speaker_init_x, primary_speaker_init_y)

        sorted_by_len = [vt[1] for vt in valid_tracks]
        has_speaker = len(sorted_by_len) >= 1
        full_x_solo = None

        # Compute scene-level MEDIAN face scale from ALL valid tracks.
        # This is used as a CONSTANT denominator for person_scale so zoom never changes frame-to-frame.
        scene_median_s = None
        if has_speaker:
            all_s_values = []
            for _vt_idx, vt_tr, _vt_score, _vt_len in valid_tracks:
                track_s = vt_tr["proc_track"]["s"]
                if hasattr(track_s, 'tolist'):
                    all_s_values.extend(track_s.tolist())
                else:
                    all_s_values.extend(list(track_s))
            if all_s_values:
                all_s_values.sort()
                mid = len(all_s_values) // 2
                scene_median_s = all_s_values[mid]
                logger.info("Scene-level median face scale locked at %.2f (from %d samples)", scene_median_s, len(all_s_values))

        if has_speaker:
            full_x_solo = self.get_smooth_x_for_track(sorted_by_len[0], max_frames)
            logger.info("Solo speaker locking enabled (%d valid tracks)", len(valid_tracks))

        temp_v = os.path.join(pyavi_path, "v.mp4")

        if self.use_nvenc:
            vout = ffmpegcv.VideoWriterNV(
                file=temp_v, codec="h264", fps=fps, resize=(1080, 1920)
            )
        else:
            logger.info("Using CPU encoder (NVENC unavailable)")
            vout = ffmpegcv.VideoWriter(
                file=temp_v, codec="h264", fps=fps, resize=(1080, 1920)
            )

        # --- speaker-locking state ---
        current_cx = None
        current_target_cx = None
        prev_target_cx = None
        speaker_hold_frames = int(fps * SPEAKER_HOLD_SECONDS)
        frames_since_active = 0
        held_speaker_x = primary_speaker_init_x
        held_speaker_y = primary_speaker_init_y
        held_speaker_s = primary_speaker_init_s
        held_speaker_zoom = 0.098
        current_track_id = None

        # --- split-screen state (Vizard-style independent crop per person) ---
        split_cx_top = None
        split_cy_top = None
        split_s_top = None
        split_target_cx_top = None
        split_target_cy_top = None
        split_target_s_top = None
        split_cx_bottom = None
        split_cy_bottom = None
        split_s_bottom = None
        split_target_cx_bottom = None
        split_target_cy_bottom = None
        split_target_s_bottom = None

        # --- reframe zoom state ---
        current_cy_reframe = None
        current_s_reframe = None
        current_target_cy_reframe = None
        current_target_s_reframe = None

        # Hysteresis to prevent conversational whiplash. Level 100: Snappier 0.8s minimum cut lock.
        MIN_CUT_FRAMES = int(fps * 0.8)
        frames_on_current_speaker = 0

        # Smoothness tuning
        # Lower value = slower, smoother pan. Snappy tracking: 0.06
        SMOOTHING_ALPHA = 0.06

        # --- Zoom Punch state (audio-driven emphasis zoom) ---
        audio_rms = None
        if audio_wav_path:
            audio_rms = compute_audio_rms_energy(audio_wav_path, fps, max_frames)
            if audio_rms and any(r > 0 for r in audio_rms):
                logger.info("Zoom punch: loaded %d frames of RMS audio energy", len(audio_rms))
            else:
                audio_rms = None
        zoom_punch_active = 0.0       # Current zoom punch intensity (0.0 = none, up to ZOOM_PUNCH_MAGNITUDE)
        zoom_punch_frame_counter = 0  # Frames since last punch triggered
        zoom_punch_cooldown = 0       # Cooldown counter to prevent rapid-fire punches
        import math as _math

        # --- Ken Burns state (slow drift for static scenes) ---
        ken_burns_zoom_accum = 0.0     # Accumulated zoom from Ken Burns
        ken_burns_drift_accum = 0.0    # Accumulated lateral drift
        ken_burns_drift_dir = 1.0      # +1 or -1 for drift direction
        ken_burns_static_frames = 0    # Counter of frames with no significant movement
        prev_held_speaker_x = None     # Track movement for Ken Burns activation

        # Open video reader and determine dimensions first
        video_reader = None
        if video_path is not None:
            logger.info("Opening high-resolution sequential video reader for rendering: %s starting at %.2fs", video_path, start_time_in_video)
            video_reader = self.get_video_reader(
                video_path,
                ss=start_time_in_video,
                duration=duration,
                use_gpu=True,
            )

        source_w, source_h = 1920, 1080
        if video_reader is not None:
            source_w = getattr(video_reader, "width", 1920) or 1920
            source_h = getattr(video_reader, "height", 1080) or 1080
        elif frames_mem is not None and len(frames_mem) > 0:
            source_h, source_w = frames_mem[0].shape[:2]

        # Define scene boundaries or fall back to single scene
        sb = scene_bounds or [(0, max_frames)]

        # Pre-compute layout per frame based on strict scene boundaries.
        # This completely prevents "random" layout changes mid-scene.
        frame_layout = ["single"] * max_frames
        if crop_mode in ("split", "letterbox"):
            mapped = crop_mode
            frame_layout = [mapped] * max_frames
        else:
            # crop_mode is either "auto" or "reframe"
            for sf, ef in sb:
                if sf >= max_frames:
                    continue
                ef = min(ef, max_frames)
                scene_len = ef - sf
                if scene_len <= 0:
                    continue

                if crop_mode == "auto":
                    scene_tr, scene_sc = slice_tracks_and_scores(tracks, scores, sf, ef)
                    scene_crop = classify_layout(scene_tr, scene_sc, source_w, source_h)
                    
                    if scene_crop == "reframe":
                        mapped = "single"
                    elif scene_crop in ("split", "letterbox"):
                        mapped = scene_crop
                    else:
                        mapped = "single"
                else:
                    # crop_mode is "reframe" - strictly single vertical panning layout
                    mapped = "single"
                
                for f in range(sf, ef):
                    frame_layout[f] = mapped

        _letterbox_shadow = None
        _letterbox_mask = None

        def _make_blurred_bg(img):
            return make_blurred_bg(img)

        # Telemetry metrics collection
        frames_with_faces_count = 0
        asd_scores_list = []
        layout_switches_count = 0
        speaker_switches_count = 0
        camera_displacements = []
        prev_cx_metric = None

        def _write_frame(frame_out):
            vout.write(frame_out)

        # Level 100: Precompute scene cuts to prevent camera sliding across scene transitions
        scene_starts = set()
        if scene_bounds:
            for sf, ef in scene_bounds:
                scene_starts.add(sf)
        try:
            current_zoom = 1.10
            for fidx in range(max_frames):
                if video_reader is not None:
                    ret, img = video_reader.read()
                    if not ret or img is None:
                        break
                else:
                    img = frames_mem[fidx]

                # Telemetry: track face coverage, ASD scores, layout switches
                if fidx < len(faces) and faces[fidx]:
                    frames_with_faces_count += 1
                    best_f = max(faces[fidx], key=lambda x: x.get("score", 0))
                    asd_scores_list.append(best_f.get("score", 0))

                if fidx > 0 and frame_layout[fidx] != frame_layout[fidx - 1]:
                    layout_switches_count += 1
                    # Clean hard cut: reset camera holding state on layout structural change
                    held_cx = None
                    held_speaker_x = None
                    held_speaker_y = None

                scale = 1920 / img.shape[0]

                # Dynamic layout dispatch from pre-computed per-scene classification
                current_layout = frame_layout[fidx]
                use_multi_face_letterbox = current_layout == "letterbox"
                use_split_screen = current_layout == "split"

                # Reset split-screen tracking state on layout transitions to prevent stale camera positions
                if use_split_screen and fidx > 0 and frame_layout[fidx - 1] != "split":
                    split_cx_top = None
                    split_cy_top = None
                    split_s_top = None
                    split_target_cx_top = None
                    split_target_cy_top = None
                    split_target_s_top = None
                    split_cx_bottom = None
                    split_cy_bottom = None
                    split_s_bottom = None
                    split_target_cx_bottom = None
                    split_target_cy_bottom = None
                    split_target_s_bottom = None

                # --- Look-ahead Interjection Filter ---
                # If the current "best" speaker is different from the last one,
                # verify they continue speaking for at least 10 frames before switching.
                # This prevents the camera from bouncing for a "Yeah" or "Right".
                # Minimum Stability Duration: 8-frame (~300ms) look-ahead window prevents back-and-forth bouncing on brief interjections
                look_ahead_frames = 8
                potential_best = None
                if faces[fidx]:
                    potential_best = max(faces[fidx], key=lambda x: x["score"])

                is_interjection = False
                if (
                    potential_best
                    and current_track_id is not None
                    and potential_best["tidx"] != current_track_id
                ):
                    active_count = 0
                    for i in range(1, look_ahead_frames + 1):
                        future_idx = fidx + i
                        if future_idx >= max_frames:
                            break
                        future_faces = faces[future_idx]
                        if any(
                            f["tidx"] == potential_best["tidx"]
                            and f["score"] > ACTIVE_SPEAKER_THRESHOLD
                            for f in future_faces
                        ):
                            active_count += 1

                    if active_count < (look_ahead_frames // 2):
                        is_interjection = True

                # Sticky-speaker selection for multi-speaker overlap arbitration (mic holder & score margin priority):
                if faces[fidx] and not is_interjection:
                    if current_track_id is not None:
                        same_track = [
                            f for f in faces[fidx] if f["tidx"] == current_track_id
                        ]
                        # Prioritize primary audio source / larger face size (microphone holder) in overlap scenarios
                        # Require a minimum score margin of 0.15 + face size weighting before switching
                        if potential_best and potential_best["score"] > 0.45:
                            current_score = same_track[0]["score"] if same_track else 0.0
                            current_size = same_track[0]["s"] if same_track else 1.0
                            pot_size = potential_best["s"]
                            
                            # Size bonus multiplier: larger face (mic holder / closer) gets up to 10% boost
                            size_ratio = pot_size / max(current_size, 1.0)
                            size_bonus = 0.05 if size_ratio > 1.15 else 0.0
                            
                            if not same_track or (potential_best["score"] + size_bonus > current_score + 0.15):
                                best = potential_best
                            elif same_track and same_track[0]["score"] > ACTIVE_SPEAKER_THRESHOLD * 0.5:
                                best = same_track[0]
                            else:
                                best = potential_best
                        elif same_track and same_track[0]["score"] > ACTIVE_SPEAKER_THRESHOLD * 0.5:
                            best = same_track[0]
                        else:
                            best = potential_best
                    else:
                        best = potential_best
                else:
                    best = None

                target_cx = None
                speaker_switched = False
                if best and best["score"] > ACTIVE_SPEAKER_THRESHOLD:
                    if current_track_id != best["tidx"]:
                        current_track_id = best["tidx"]
                        frames_on_current_speaker = 0
                        speaker_switched = True
                    else:
                        frames_on_current_speaker += 1

                    held_speaker_x = best["x"]
                    held_speaker_y = best["y"]
                    held_speaker_s = best["s"]

                    # Constant stable speaker framing scale (eliminates repeated zoom jumps)
                    held_speaker_zoom = 0.106

                    frames_since_active = 0
                    target_cx = int(held_speaker_x * scale)
                elif held_speaker_x is not None:
                    # Hold the last active speaker indefinitely during pauses.
                    frames_since_active += 1
                    frames_on_current_speaker += 1
                    target_cx = int(held_speaker_x * scale)
                elif has_speaker and full_x_solo is not None:
                    target_cx = int(full_x_solo[fidx] * scale)
                    frames_on_current_speaker += 1

                if use_multi_face_letterbox:
                    # Use dynamic blurred background for premium letterboxing
                    bg = _make_blurred_bg(img)

                    CARD_W = 1080  # Full width, no padding
                    CARD_H = int(
                        1920 * LETTERBOX_TARGET_HEIGHT_RATIO
                    )  # Dynamic vertical card height based on target ratio

                    # If no speaker is actively tracked, hold camera position or use visual saliency for B-roll/slides
                    if target_cx is None:
                        if current_cx is not None:
                            target_cx = current_target_cx
                        else:
                            # Saliency / text density fallback: Canny edge centroid on downsampled frame
                            try:
                                gray_small = cv2.cvtColor(cv2.resize(img, (320, 180)), cv2.COLOR_BGR2GRAY)
                                edges = cv2.Canny(gray_small, 50, 150)
                                col_sum = edges.sum(axis=0)
                                if col_sum.sum() > 0:
                                    col_idx = np.arange(320, dtype=np.float32)
                                    saliency_cx_pct = float((col_idx * col_sum).sum() / col_sum.sum()) / 320.0
                                    target_cx = int(saliency_cx_pct * img.shape[1] * scale)
                                else:
                                    target_cx = int((img.shape[1] / img.shape[0]) * 1920 / 2)
                            except Exception:
                                target_cx = int((img.shape[1] / img.shape[0]) * 1920 / 2)

                    if current_cx is None:
                        current_cx = float(target_cx)
                        current_target_cx = float(target_cx)

                    # Tighter camera pan for OpusClip feel
                    LETTERBOX_DEAD_ZONE = 30
                    PAN_SMOOTHING = 0.08
                    if target_cx - current_target_cx > LETTERBOX_DEAD_ZONE:
                        current_target_cx = float(target_cx - LETTERBOX_DEAD_ZONE)
                    elif current_target_cx - target_cx > LETTERBOX_DEAD_ZONE:
                        current_target_cx = float(target_cx + LETTERBOX_DEAD_ZONE)

                    current_cx = (
                        current_cx + (current_target_cx - current_cx) * PAN_SMOOTHING
                    )
                    prev_target_cx = float(target_cx)

                    # AI Reaction Zoom
                    target_zoom = 1.10
                    if best and best.get("score", 0) > 0.8:
                        target_zoom = 1.15

                    current_zoom += (target_zoom - current_zoom) * 0.08
                    zoom = current_zoom

                    scale_card = (CARD_H * zoom) / img.shape[0]
                    scaled_h = int(CARD_H * zoom)
                    scaled_w = int(img.shape[1] * scale_card)

                    res_scaled = cv2.resize(
                        img, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA
                    )

                    # current_cx was computed in 1920-height scale. Convert it to the new zoomed height scale.
                    cx_card = current_cx * (scaled_h / 1920.0)
                    tx = max(min(int(cx_card) - CARD_W // 2, scaled_w - CARD_W), 0)

                    # Crop the TOP portion of the zoomed video, completely removing the bottom 10% (watermark zone)
                    ty = 0
                    res = res_scaled[ty : ty + CARD_H, tx : tx + CARD_W]

                    start_x = 0  # Full width, no padding

                    # Shift video down to leave room at the top for the hook text, balanced for the larger height
                    start_y = 310

                    H, W = res.shape[:2]

                    # Blend directly onto background (no shadow, no rounded corners)
                    bg[start_y : start_y + H, start_x : start_x + W] = res
                    _write_frame(bg)

                elif use_split_screen:
                    # --- Vizard/Opus-style: Dynamic Multi-Speaker ASD Split Layout ---
                    face_top = None
                    face_bottom = None

                    if fidx < len(faces) and len(faces[fidx]) > 0:
                        all_faces = faces[fidx]
                        if len(all_faces) >= 2:
                            # Sort left-to-right across the stage: Leftmost face -> Top panel, Rightmost face -> Bottom panel
                            sorted_lr = sorted(all_faces, key=lambda f: f["x"])
                            face_top = sorted_lr[0]
                            face_bottom = sorted_lr[-1]
                        elif len(all_faces) == 1:
                            single_face = all_faces[0]
                            mid_x = (img.shape[1] * scale) / 2.0
                            if single_face["x"] < mid_x:
                                face_top = single_face
                            else:
                                face_bottom = single_face

                    # Prevent duplicate slot framing: if top and bottom are too close horizontally, offset bottom
                    if face_top and face_bottom and abs(face_top["x"] - face_bottom["x"]) < 100.0:
                        face_bottom = None

                    # Smooth tracking — top person (with dead-zones and tripod-like SPLIT_ALPHA = 0.03)
                    if face_top is not None:
                        if split_cx_top is None:
                            split_cx_top = float(face_top["x"])
                            split_cy_top = float(face_top["y"])
                            split_s_top = float(face_top["s"])
                            split_target_cx_top = float(face_top["x"])
                            split_target_cy_top = float(face_top["y"])
                            split_target_s_top = float(face_top["s"])
                        else:
                            # Level 1000: Stabilized 25px dead zone for tripod-like split screen
                            SPLIT_DEAD_ZONE = 25.0
                            if abs(face_top["x"] - split_target_cx_top) > SPLIT_DEAD_ZONE:
                                split_target_cx_top = float(face_top["x"])
                            if abs(face_top["y"] - split_target_cy_top) > SPLIT_DEAD_ZONE:
                                split_target_cy_top = float(face_top["y"])
                            # 10% dead zone on size
                            if abs(face_top["s"] - split_target_s_top) > (
                                split_target_s_top * 0.10
                            ):
                                split_target_s_top = float(face_top["s"])

                            # Slower smoothing alpha (0.04) for cinematic stability in split layout
                            SPLIT_ALPHA = 0.04
                            split_cx_top += (
                                split_target_cx_top - split_cx_top
                            ) * SPLIT_ALPHA
                            split_cy_top += (
                                split_target_cy_top - split_cy_top
                            ) * SPLIT_ALPHA
                            split_s_top += (split_target_s_top - split_s_top) * SPLIT_ALPHA

                    # Smooth tracking — bottom person (with dead-zones and tripod-like SPLIT_ALPHA = 0.03)
                    if face_bottom is not None:
                        if split_cx_bottom is None:
                            split_cx_bottom = float(face_bottom["x"])
                            split_cy_bottom = float(face_bottom["y"])
                            split_s_bottom = float(face_bottom["s"])
                            split_target_cx_bottom = float(face_bottom["x"])
                            split_target_cy_bottom = float(face_bottom["y"])
                            split_target_s_bottom = float(face_bottom["s"])
                        else:
                            # Level 1000: Stabilized 25px dead zone for tripod-like split screen
                            SPLIT_DEAD_ZONE = 25.0
                            if (
                                abs(face_bottom["x"] - split_target_cx_bottom)
                                > SPLIT_DEAD_ZONE
                            ):
                                split_target_cx_bottom = float(face_bottom["x"])
                            if (
                                abs(face_bottom["y"] - split_target_cy_bottom)
                                > SPLIT_DEAD_ZONE
                            ):
                                split_target_cy_bottom = float(face_bottom["y"])
                            # 10% dead zone on size
                            if abs(face_bottom["s"] - split_target_s_bottom) > (
                                split_target_s_bottom * 0.10
                            ):
                                split_target_s_bottom = float(face_bottom["s"])

                            # Slower smoothing alpha (0.04) for cinematic stability in split layout
                            SPLIT_ALPHA = 0.04
                            split_cx_bottom += (
                                split_target_cx_bottom - split_cx_bottom
                            ) * SPLIT_ALPHA
                            split_cy_bottom += (
                                split_target_cy_bottom - split_cy_bottom
                            ) * SPLIT_ALPHA
                            split_s_bottom += (
                                split_target_s_bottom - split_s_bottom
                            ) * SPLIT_ALPHA

                    final_frame = np.zeros((1920, 1080, 3), dtype=np.uint8)
                    img_h, img_w = img.shape[:2]

                    # Check scores to highlight active speaker panel vs listener panel
                    score_top = face_top.get("score", 0.0) if face_top else 0.0
                    score_bottom = face_bottom.get("score", 0.0) if face_bottom else 0.0

                    # We iterate over top (left speaker) and bottom (right speaker) slots
                    for is_top, y_start in [(True, 0), (False, 960)]:
                        sub_img = img  # Crop directly from full source frame to avoid slicing faces in half
                        if is_top:
                            cx = split_cx_top
                            cy = split_cy_top
                            s = split_s_top
                            is_active_speaker = (score_top > ACTIVE_SPEAKER_THRESHOLD and score_top >= score_bottom)
                        else:
                            cx = split_cx_bottom
                            cy = split_cy_bottom
                            s = split_s_bottom
                            is_active_speaker = (score_bottom > ACTIVE_SPEAKER_THRESHOLD and score_bottom > score_top)

                        sub_h, sub_w = sub_img.shape[:2]

                        # Fallback to Left/Right stage anchors if face tracking is not available
                        if cx is None:
                            # Top panel = Left Speaker (~28% x), Bottom panel = Right Speaker (~72% x)
                            cx_rel = sub_w * 0.28 if is_top else sub_w * 0.72
                            cy_rel = sub_h * 0.25  # Seated podcast speaker head level (~270px)
                        else:
                            cx_rel = float(cx)
                            cy_rel = float(cy) if cy is not None else sub_h * 0.25

                        # Ensure coordinates are within sub-image boundaries
                        cx_rel = max(0.0, min(cx_rel, float(sub_w)))
                        cy_rel = max(0.0, min(cy_rel, float(sub_h)))

                        # ---- OpusClip-quality FIXED crop size ----
                        # Use 44% of frame width (844px out of 1920) for 1080:960 aspect ratio (750px height).
                        # This frames head, shoulders, chest, mic & hand gestures cleanly with ZERO head cutoff.
                        crop_w = float(sub_w) * 0.44
                        crop_h = crop_w / 1.125  # 1080:960 aspect ratio

                        # Ensure crop doesn't exceed frame bounds
                        crop_w = min(crop_w, float(sub_w))
                        crop_h = min(crop_h, float(sub_h))

                        # Position crop: center horizontally on face, face at 22% from top vertically
                        # 22% ensures at least ~165px of headroom above face center so hair and head are NEVER cut off
                        x1 = cx_rel - crop_w / 2.0
                        y1 = cy_rel - crop_h * 0.22

                        # Clamp crop box to stay inside the source frame
                        x1 = max(0.0, min(x1, sub_w - crop_w))
                        y1 = max(0.0, min(y1, sub_h - crop_h))

                        x2 = x1 + crop_w
                        y2 = y1 + crop_h

                        crop = sub_img[int(y1) : int(y2), int(x1) : int(x2)]
                        if crop.shape[0] > 0 and crop.shape[1] > 0:
                            resized = cv2.resize(
                                crop, (1080, 960), interpolation=cv2.INTER_AREA
                            )
                            # Dim listener panel slightly to bring visual focus to active speaker
                            if not is_active_speaker and (score_top > ACTIVE_SPEAKER_THRESHOLD or score_bottom > ACTIVE_SPEAKER_THRESHOLD):
                                resized = cv2.convertScaleAbs(resized, alpha=SPLIT_LISTENER_DIM, beta=0)

                            final_frame[y_start : y_start + 960, 0:1080] = resized

                    # Draw 4px separator line between top and bottom panels
                    final_frame[958:962, :] = (40, 40, 40)
                    _write_frame(final_frame)
                    prev_target_cx = None

                elif target_cx is not None or current_cx is not None:
                    # --- Smooth Camera Movement (Single Full-Screen, Reframe) ---
                    virtual_w = img.shape[1] * scale
                    virtual_h = img.shape[0] * scale

                    # Fallback to current if target dropped temporarily
                    if target_cx is None:
                        target_cx = current_cx
                        target_cy = (
                            current_cy_reframe
                            if current_cy_reframe is not None
                            else virtual_h / 2.0
                        )
                        target_s = scene_median_s if scene_median_s is not None else virtual_w * 0.08
                    else:
                        target_cy = (
                            (held_speaker_y * scale)
                            if held_speaker_y is not None
                            else virtual_h / 2.0
                        )
                        target_s = scene_median_s if scene_median_s is not None else (held_speaker_s * scale)

                    # Level 100: Scene cut hard reset (snap camera ONLY on actual video scene edit cuts)
                    is_scene_start = fidx in scene_starts

                    # Initialize on first frame or hard cut ONLY on true scene edits (prevents 1s abrupt flicker on speaker switches)
                    if current_cx is None or is_scene_start:
                        current_cx = float(target_cx)
                        current_target_cx = float(target_cx)
                        current_cy_reframe = float(target_cy)
                        current_target_cy_reframe = float(target_cy)
                    elif speaker_switched:
                        # Smooth transition interpolation across speaker switches: glide viewport over ~6 frames instead of snapping
                        current_target_cx = float(target_cx)
                        current_target_cy_reframe = float(target_cy)

                    # Dead-zone on X
                    DEAD_ZONE_PX = 15.0
                    if target_cx - current_target_cx > DEAD_ZONE_PX:
                        current_target_cx = float(target_cx - DEAD_ZONE_PX)
                    elif current_target_cx - target_cx > DEAD_ZONE_PX:
                        current_target_cx = float(target_cx + DEAD_ZONE_PX)

                    # 15px dead-zone on Y-axis
                    DEAD_ZONE_Y = 15.0
                    if abs(target_cy - current_target_cy_reframe) > DEAD_ZONE_Y:
                        current_target_cy_reframe = float(target_cy)


                    # Level 1000: Sigmoid Adaptive Easing & Smooth Panning Transition
                    # Faster panning: increased sigmoid ceiling from 0.25→0.40 with velocity boost
                    dist_x = abs(current_target_cx - current_cx)
                    if dist_x < 15.0:
                        # Stabilization lock: lock camera on stationary speaker
                        adaptive_alpha = 0.0
                    else:
                        # Sigmoid S-curve acceleration/deceleration for fluid studio camera pan
                        sigmoid_factor = 1.0 / (1.0 + _math.exp(-0.025 * (dist_x - 150.0)))
                        # Velocity-dependent acceleration: faster when target is moving fast
                        velocity = abs(current_target_cx - (prev_target_cx or current_target_cx)) if prev_target_cx is not None else 0.0
                        velocity_boost = min(0.12, velocity / 500.0)
                        adaptive_alpha = 0.05 + (0.35 + velocity_boost) * sigmoid_factor

                    if adaptive_alpha > 0.0:
                        current_cx += (current_target_cx - current_cx) * adaptive_alpha
                        current_cy_reframe += (
                            current_target_cy_reframe - current_cy_reframe
                        ) * (
                            adaptive_alpha * 0.5
                        )  # Dampen vertical movement by 50% for gimbal-like stability

                    # Fixed stable face framing — use scene-level median face scale (CONSTANT)
                    face_size_pct = 0.106
                    locked_s = (scene_median_s * scale) if scene_median_s is not None else max(current_s_reframe or 1.0, 1.0)

                    person_scale = (1920.0 * face_size_pct) / max(locked_s, 1.0)
                    min_s = max(1080.0 / virtual_w, 1920.0 / virtual_h)

                    person_scale = max(person_scale, min_s)
                    person_scale = min(person_scale, 4.0)

                    crop_w = 1080.0 / person_scale
                    crop_h = 1920.0 / person_scale

                    # Clamp crop to virtual bounds
                    crop_w = min(crop_w, virtual_w)
                    crop_h = min(crop_h, virtual_h)

                    # Maintain 1080:1920 aspect ratio
                    if crop_w * 1920.0 > crop_h * 1080.0:
                        crop_w = crop_h * (1080.0 / 1920.0)
                    else:
                        crop_h = crop_w * (1920.0 / 1080.0)

                    # Face positioned at ~22% from top (upper third rule for high engagement vertical video)
                    x1_virtual = current_cx - crop_w / 2.0
                    y1_virtual = current_cy_reframe - crop_h * 0.22

                    # Bounds check in virtual space
                    x1_virtual = max(0.0, min(x1_virtual, virtual_w - crop_w))
                    y1_virtual = max(0.0, min(y1_virtual, virtual_h - crop_h))

                    # Map back to original image space
                    x1 = x1_virtual / scale
                    y1 = y1_virtual / scale
                    crop_w_orig = crop_w / scale
                    crop_h_orig = crop_h / scale

                    crop = img[
                        int(y1) : int(y1 + crop_h_orig), int(x1) : int(x1 + crop_w_orig)
                    ]
                    if crop.shape[0] > 0 and crop.shape[1] > 0:
                        res = cv2.resize(crop, (1080, 1920), interpolation=cv2.INTER_AREA)
                        _write_frame(res)
                    else:
                        # Emergency fallback
                        res = cv2.resize(img, None, fx=scale, fy=scale)
                        tx = max(min(res.shape[1] // 2 - 540, res.shape[1] - 1080), 0)
                        _write_frame(res[0:1920, tx : tx + 1080])

                    prev_target_cx = float(target_cx)
                else:
                    prev_target_cx = None
                    current_cx = None
                    # Fallback if no target is found but we aren't in split or letterbox
                    # Just render center of the original video
                    res = cv2.resize(img, None, fx=scale, fy=scale)
                    tx = max(min(res.shape[1] // 2 - 540, res.shape[1] - 1080), 0)
                    _write_frame(res[0:1920, tx : tx + 1080])

                # Telemetry: record camera displacement
                if current_cx is not None:
                    if prev_cx_metric is not None:
                        camera_displacements.append(abs(current_cx - prev_cx_metric))
                    prev_cx_metric = current_cx

        finally:
            if video_reader is not None:
                try:
                    video_reader.close()
                except Exception:
                    pass

        vout.release()
        shutil.move(temp_v, output_path)

        quality_metrics = {
            "face_detection_coverage": round(float(frames_with_faces_count) / max(1, max_frames), 3),
            "asd_confidence": round(float(np.mean(asd_scores_list)) if asd_scores_list else 0.0, 3),
            "layout_switches": layout_switches_count,
            "speaker_switches": speaker_switches_count,
            "camera_stability_score": round(max(0.0, 1.0 - min(1.0, float(np.mean(camera_displacements)) / 50.0)), 3) if camera_displacements else 1.0,
        }
        return frame_layout, quality_metrics

    # ─────────────────────────────────────────────────────────────────
    #  Public endpoint
    # ─────────────────────────────────────────────────────────────────
    @modal.fastapi_endpoint(method="POST")
    def reframe(self, req: ReframeRequest):
        from pathlib import Path

        # --- Validate inputs ---
        vurl = validate_url(req.video_url, label="video_url")

        logger.info("=== REFRAME REQUEST ===")
        logger.info("video_url: %s...", req.video_url[:100])
        logger.info("start_time: %s, end_time: %s", req.start_time, req.end_time)
        logger.info(
            "transcript: %d words",
            len(req.transcript) if req.transcript else 0,
        )
        logger.info(
            "styling: %s",
            req.styling.model_dump() if req.styling else "None",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            is_preview = req.quality == "preview"

            # 1. Download from YouTube if needed
            # When segment download is used, the file timeline is re-based to 0
            # starting from (start_time - padding). We compute the offset so all
            # downstream ffmpeg -ss values are relative to the downloaded file.
            segment_offset = 0.0  # seconds trimmed from the front of the source
            if is_youtube_url(vurl):
                logger.info(
                    "Detected YouTube URL, downloading via yt-dlp (quality=%s)...",
                    req.quality,
                )
                vurl, segment_offset = download_youtube_video(
                    vurl,
                    tmpdir,
                    start_time=req.start_time,
                    end_time=req.end_time,
                    max_height=1080,
                    skip_probe=is_preview,  # Still skip format probe for preview to save ~4s
                )
            elif vurl.startswith("http://") or vurl.startswith("https://"):
                logger.info("Downloading remote video from %s...", vurl[:100])
                local_video = os.path.join(tmpdir, "input_video.mp4")
                try:
                    import requests
                    with requests.get(vurl, stream=True, timeout=300) as r:
                        r.raise_for_status()
                        with open(local_video, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                    vurl = local_video
                except Exception as e:
                    raise DownloadError(f"Failed to download video: {e}") from e

                dl_size = os.path.getsize(vurl)
                logger.info(
                    "Remote video downloaded to: %s (%.1f MB)",
                    vurl,
                    dl_size / (1024 * 1024),
                )

            # Adjust start_time for the downloaded segment (0 offset for non-YT URLs)
            effective_start = req.start_time - segment_offset

            # 2. Verify resolution via ffprobe
            t0 = time.time()
            video_info = self.get_video_info(vurl)
            fps = video_info["fps"]
            actual_w = video_info.get("width", "?")
            actual_h = video_info.get("height", "?")
            logger.info("── ffprobe verification ──")
            logger.info("Actual file resolution: %sx%s", actual_w, actual_h)
            logger.info(
                "FPS: %s, Duration: %ss",
                fps,
                video_info.get("duration", "?"),
            )
            try:
                if (
                    not is_preview
                    and actual_h
                    and actual_h != "?"
                    and int(actual_h) < 1080
                ):
                    logger.warning(
                        "RESOLUTION MISMATCH: Expected 1080p but got %sp!",
                        actual_h,
                    )
            except (TypeError, ValueError):
                pass

            # 3. Track + score
            logger.info("Extracting local audio segment for tracking and sync...")
            duration_secs = req.end_time - req.start_time
            segment_audio = os.path.join(tmpdir, "segment_audio.aac")
            # Extract high-quality audio once
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    vurl,
                    "-ss",
                    str(effective_start),
                    "-t",
                    str(duration_secs),
                    "-vn",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    segment_audio,
                    "-loglevel",
                    "panic",
                ],
                check=True,
                timeout=_FFMPEG_LONG_TIMEOUT_S,
            )

            logger.info(
                "Running tracking/extraction with crop_mode=%s...",
                req.crop_mode,
            )
            try:
                tracks, scores, audio, pyf, pya, scene_bounds = self.get_tracks_and_scores(
                    vurl,
                    effective_start,
                    duration_secs,
                    tmpdir,
                    fps=fps,
                    audio_url=segment_audio,
                )
                logger.info(
                    "Face tracking done in %.1fs, found %d tracks",
                    time.time() - t0,
                    len(tracks),
                )

                # 4. Render vertical
                crop_mode = req.crop_mode
                reported_crop_mode = crop_mode
                if crop_mode == "auto":
                    reported_crop_mode = self.classify_layout(
                        tracks,
                        scores,
                        video_info.get("width", 1920),
                        video_info.get("height", 1080),
                    )
                    logger.info("Auto-detected layout (reported): %s", reported_crop_mode)

                orig_name = f"orig_{uuid.uuid4()}.mp4"
                local_orig = os.path.join(tmpdir, orig_name)

                t1 = time.time()
                logger.info("Rendering vertical video at %s fps...", fps)
                frame_layout, quality_metrics = self.render_vertical(
                    tracks,
                    scores,
                    pyf,
                    pya,
                    local_orig,
                    duration=duration_secs,
                    fps=fps,
                    crop_mode=crop_mode,
                    scene_bounds=scene_bounds,
                    video_path=vurl,
                    start_time_in_video=effective_start,
                    audio_wav_path=audio,
                )

                if not os.path.exists(local_orig) or os.path.getsize(local_orig) == 0:
                    raise RenderError(f"Render failed: output video file not found or empty at {local_orig}")
            except Exception as reframer_err:
                logger.warning(
                    "reframe_video AI tracking/rendering failed (%s). Falling back to letterbox mode...",
                    reframer_err,
                    exc_info=True,
                )
                orig_name = f"orig_{uuid.uuid4()}.mp4"
                local_orig = os.path.join(tmpdir, orig_name)
                crop_mode = "letterbox"
                reported_crop_mode = "letterbox"
                pya = os.path.join(tmpdir, "pyavi")
                os.makedirs(pya, exist_ok=True)
                frame_layout, quality_metrics = self.render_vertical(
                    [],
                    [],
                    None,
                    pya,
                    local_orig,
                    duration=duration_secs,
                    fps=fps,
                    crop_mode="letterbox",
                    scene_bounds=[(0, max(1, int(round(duration_secs * fps))))],
                    video_path=vurl,
                    start_time_in_video=effective_start,
                )

            # Annotate layout inside the transcript!
            if req.transcript:
                req.transcript = annotate_transcript_layout(
                    req.transcript, frame_layout, crop_mode, fps
                )


            # 5. Mux original audio back in + compress (ffmpegcv writes
            #    near-lossless by default, so we re-encode here to bring the
            #    intermediate file down to a reasonable size).
            #    NOTE: The reframer output (originalVideoUrl) is the source of
            #    truth for ALL future renders — both preview burns and HD exports.
            #    It MUST always be full 1080x1920 quality, regardless of the
            #    request's quality parameter.  The preview quality reduction
            #    (540p, higher CRF) is handled by the caption burner, not here.
            synced_output = local_orig.replace(".mp4", "_synced.mp4")
            mux_audio_video(
                video_path=local_orig,
                audio_path=segment_audio,
                output_path=synced_output,
                fps=fps,
                use_nvenc=self.use_nvenc,
            )
            os.replace(synced_output, local_orig)

            orig_size = os.path.getsize(local_orig)
            logger.info(
                "Vertical render done in %.1fs, size=%s bytes",
                time.time() - t1,
                f"{orig_size:,}",
            )

            # 6. Upload to R2 in parallel with local caption burn if transcript exists
            import concurrent.futures

            orig_url = None
            preview_video_url = None
            thumbnail_url = None

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                # Start R2 upload of the original video in the background
                logger.info(
                    "Uploading original to R2 in background: reframes/%s", orig_name
                )
                future_upload_orig = executor.submit(
                    upload_to_r2, local_orig, f"reframes/{orig_name}"
                )

                # If transcript is provided, burn captions in parallel
                future_burn = None
                if req.transcript and req.styling:
                    logger.info("Burning captions directly on GPU instance...")
                    from burner import burn_captions_local

                    local_preview = os.path.join(tmpdir, f"preview_{uuid.uuid4()}.mp4")
                    future_burn = executor.submit(
                        burn_captions_local,
                        local_video=local_orig,
                        local_output=local_preview,
                        transcript=req.transcript,
                        styling=req.styling,
                        show_watermark=req.show_watermark,
                        crop_mode=crop_mode,
                        quality=req.quality or "preview",
                        tmpdir=tmpdir,
                    )

                # Wait for the original upload to complete
                try:
                    orig_url = future_upload_orig.result()
                    logger.info("Original uploaded successfully: %s", orig_url)
                except Exception as e:
                    logger.error("Failed to upload original video: %s", e)
                    raise

                # Wait for the caption burn to complete (if started)
                if future_burn:
                    try:
                        preview_video_url, thumbnail_url = future_burn.result()
                        logger.info(
                            "Direct caption burn complete: %s, thumb: %s",
                            preview_video_url,
                            thumbnail_url,
                        )
                    except Exception as e:
                        logger.error(
                            "Failed to burn captions directly on GPU: %s",
                            e,
                            exc_info=True,
                        )
                        # Do not raise here; allow fallback to separate caption burner

            if hasattr(pyf, "_mmap") and pyf._mmap is not None:
                try:
                    pyf._mmap.close()
                except Exception:
                    pass

            logger.info("=== REFRAME COMPLETE ===")
            logger.info("original_video_url: %s", orig_url)
            return {
                "success": True,
                "original_video_url": orig_url,
                "preview_video_url": preview_video_url,
                "thumbnail_url": thumbnail_url,
                "caption_video_url": None,
                "crop_mode": reported_crop_mode,
                "source_width": actual_w,
                "source_height": actual_h,
                "quality_metrics": quality_metrics,
                "transcript": req.transcript,
            }

    # ─────────────────────────────────────────────────────────────────
    #  Batch reframe endpoint — process all clips from ONE source decode
    # ─────────────────────────────────────────────────────────────────
    @modal.fastapi_endpoint(method="POST")
    def batch_reframe(self, req: BatchReframeRequest):
        """Process multiple clips from a single source video.

        Cluster-based optimization: groups nearby clips (within 5s) into
        clusters, runs face tracking once per cluster, then slices per-clip.
        This avoids tracking huge unused gaps between distant clips.
        """
        if not isinstance(req, BatchReframeRequest):
            req = BatchReframeRequest(**req) if isinstance(req, dict) else req

        import numpy as np
        from scipy import signal

        vurl = validate_url(req.video_url, label="video_url")
        logger.info("=== BATCH REFRAME REQUEST === (%d clips)", len(req.clips))

        results = []

        with tempfile.TemporaryDirectory() as tmpdir:
            is_preview = req.quality == "preview"

            # 1. Download from YouTube if needed (ONCE for all clips)
            segment_offset = 0.0
            global_start = min(c.start_time for c in req.clips)
            global_end = max(c.end_time for c in req.clips)

            if is_youtube_url(vurl):
                logger.info(
                    "Downloading YouTube video ONCE for %d clips...", len(req.clips)
                )
                vurl, segment_offset = download_youtube_video(
                    vurl,
                    tmpdir,
                    start_time=global_start,
                    end_time=global_end,
                    max_height=1080,
                    skip_probe=is_preview,
                )
                logger.info(
                    "YouTube download complete (segment_offset=%.1fs)", segment_offset
                )
            elif vurl.startswith("http://") or vurl.startswith("https://"):
                logger.info("Downloading remote video from %s...", vurl[:100])
                local_video = os.path.join(tmpdir, "input_video.mp4")
                try:
                    import requests
                    with requests.get(vurl, stream=True, timeout=300) as r:
                        r.raise_for_status()
                        with open(local_video, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                    vurl = local_video
                except Exception as e:
                    raise DownloadError(f"Failed to download video: {e}") from e

            # 2. Probe video info ONCE
            video_info = self.get_video_info(vurl)
            fps = video_info["fps"]
            actual_w = video_info.get("width", 1280)
            actual_h = video_info.get("height", 720)
            logger.info("Source: %sx%s @ %.1f fps", actual_w, actual_h, fps)

            # 2.5 Download pre-computed analysis.json if provided
            precomputed_analysis = None
            if getattr(req, "analysis_url", None):
                try:
                    import requests
                    logger.info("Fetching pre-computed analysis.json from %s...", req.analysis_url)
                    resp = requests.get(req.analysis_url, timeout=30)
                    if resp.status_code == 200:
                        precomputed_analysis = resp.json()
                        logger.info("Loaded pre-computed analysis with %d tracks", len(precomputed_analysis.get("tracks", [])))
                except Exception as err:
                    logger.warning("Failed to fetch pre-computed analysis.json: %s", err)

            # 3. Build clusters of nearby clips (merge if gap < 5s)
            CLUSTER_GAP_S = 5.0
            sorted_clips = sorted(req.clips, key=lambda c: c.start_time)
            clusters: list[list] = []  # each cluster is a list of clip requests
            for clip in sorted_clips:
                if (
                    clusters
                    and (clip.start_time - max(c.end_time for c in clusters[-1]))
                    < CLUSTER_GAP_S
                ):
                    clusters[-1].append(clip)
                else:
                    clusters.append([clip])

            total_tracked = sum(
                max(c.end_time for c in cl) - min(c.start_time for c in cl)
                for cl in clusters
            )
            full_span = global_end - global_start
            logger.info(
                "Clustered %d clips into %d clusters (tracking %.1fs / %.1fs span = %.0f%% savings)",
                len(req.clips),
                len(clusters),
                total_tracked,
                full_span,
                (1 - total_tracked / max(full_span, 0.1)) * 100,
            )

            # 4. Process each cluster: track once per cluster, then slice per clip
            # 4. Process each cluster in parallel: track once per cluster, then slice/render per clip
            def process_cluster(cluster_idx, cluster_clips):
                cluster_start = min(c.start_time for c in cluster_clips)
                cluster_end = max(c.end_time for c in cluster_clips)
                cluster_duration = cluster_end - cluster_start

                effective_cluster_start = cluster_start - segment_offset
                effective_cluster_end = cluster_end - segment_offset

                logger.info(
                    "=== Cluster %d/%d: %.1fs-%.1fs (%.1fs, %d clips) ===",
                    cluster_idx + 1,
                    len(clusters),
                    cluster_start,
                    cluster_end,
                    cluster_duration,
                    len(cluster_clips),
                )

                # Create isolated work directory per cluster
                cluster_workdir = os.path.join(tmpdir, f"cluster_{cluster_idx}")
                os.makedirs(cluster_workdir, exist_ok=True)

                # Extract audio for this cluster's range
                cluster_audio = os.path.join(cluster_workdir, "cluster_audio.aac")
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-ss",
                        str(effective_cluster_start),
                        "-t",
                        str(cluster_duration),
                        "-i",
                        vurl,
                        "-vn",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "192k",
                        cluster_audio,
                        "-loglevel",
                        "panic",
                    ],
                    check=True,
                    timeout=_FFMPEG_LONG_TIMEOUT_S,
                )

                # Run face tracking for this cluster (or reconstruct from pre-computed analysis)
                t0 = time.time()
                cluster_frames = None  # Only assigned in the live-tracking path below
                if precomputed_analysis and "tracks" in precomputed_analysis:
                    logger.info("Reconstructing cluster %d tracks from pre-computed analysis.json (Fast Path)...", cluster_idx + 1)
                    analysis_video_fps = precomputed_analysis.get("video_info", {}).get("fps", fps)

                    # analysis.json may have been produced at a slightly different fps
                    # than what we probe now for this render (yt-dlp metadata fps at
                    # analysis time vs ffprobe on a freshly re-downloaded segment).
                    # Scale frame numbers so they line up with `fps`, used everywhere
                    # else below for frame<->time conversion.
                    scale_factor = (fps / analysis_video_fps) if analysis_video_fps else 1.0
                    if abs(scale_factor - 1.0) > 0.01:
                        logger.warning(
                            "analysis.json fps (%.3f) differs from render fps (%.3f) — "
                            "scaling track frame indices by %.4f",
                            analysis_video_fps, fps, scale_factor,
                        )

                    # Extract analysis video metadata to calculate resolution scale factors
                    v_info = precomputed_analysis.get("video_info", {})
                    analysis_w = float(v_info.get("width") or 0)
                    analysis_h = float(v_info.get("height") or 0)

                    cluster_tracks = []
                    cluster_scores = []
                    for tr in precomputed_analysis.get("tracks", []):
                        raw_frames = np.array(tr["frames"], dtype=float)
                        raw_bboxes = np.array(tr["bboxes"], dtype=float) if tr.get("bboxes") else np.array([])
                        px = np.array(tr["proc_track"]["x"], dtype=float)
                        py = np.array(tr["proc_track"]["y"], dtype=float)
                        ps = np.array(tr["proc_track"]["s"], dtype=float)

                        # Detect if coordinates are normalized [0.0, 1.0] or pixel space
                        max_val = max(np.max(px) if len(px) > 0 else 0.0, np.max(py) if len(py) > 0 else 0.0)
                        is_normalized = (max_val > 0 and max_val <= 1.5)

                        if is_normalized:
                            px_scaled = px * actual_w
                            py_scaled = py * actual_h
                            ps_scaled = ps * actual_h
                            if raw_bboxes.ndim == 2 and raw_bboxes.shape[1] == 4:
                                raw_bboxes[:, [0, 2]] *= actual_w
                                raw_bboxes[:, [1, 3]] *= actual_h
                        elif analysis_w > 0 and analysis_h > 0 and (abs(analysis_w - actual_w) > 1 or abs(analysis_h - actual_h) > 1):
                            scale_x = actual_w / analysis_w
                            scale_y = actual_h / analysis_h
                            px_scaled = px * scale_x
                            py_scaled = py * scale_y
                            ps_scaled = ps * scale_y
                            if raw_bboxes.ndim == 2 and raw_bboxes.shape[1] == 4:
                                raw_bboxes[:, [0, 2]] *= scale_x
                                raw_bboxes[:, [1, 3]] *= scale_y
                        else:
                            px_scaled = px
                            py_scaled = py
                            ps_scaled = ps

                        cluster_tracks.append({
                            "track": {
                                "frame": np.round(raw_frames * scale_factor).astype(int),
                                "bbox": raw_bboxes,
                            },
                            "proc_track": {
                                "x": px_scaled,
                                "y": py_scaled,
                                "s": ps_scaled,
                            },
                        })
                        # Defensive normalization for analysis.json files generated
                        # before the get_tracks_and_scores alignment fix — pad/truncate
                        # scores to match len(raw_frames).
                        raw_scores = np.array(tr["scores"], dtype=float)
                        n = len(raw_frames)
                        if len(raw_scores) != n:
                            if len(raw_scores) == 0:
                                raw_scores = np.zeros(n)
                            elif len(raw_scores) < n:
                                pad_val = raw_scores[-1]
                                raw_scores = np.pad(
                                    raw_scores, (0, n - len(raw_scores)),
                                    mode="constant", constant_values=pad_val,
                                )
                            else:
                                raw_scores = raw_scores[:n]
                        cluster_scores.append(raw_scores)
                    cluster_scene_bounds = [
                        (int(round(sb[0] * scale_factor)), int(round(sb[1] * scale_factor))) 
                        for sb in precomputed_analysis.get("scene_bounds", [])
                    ]
                    pya = os.path.join(cluster_workdir, "pyavi")
                    os.makedirs(pya, exist_ok=True)
                else:
                    (
                        cluster_tracks,
                        cluster_scores,
                        audio,
                        cluster_frames,
                        pya,
                        cluster_scene_bounds,
                    ) = self.get_tracks_and_scores(
                        vurl,
                        effective_cluster_start,
                        cluster_duration,
                        cluster_workdir,
                        fps=fps,
                        audio_url=cluster_audio,
                    )
                logger.info(
                    "Cluster %d tracking ready in %.1fs, %d tracks",
                    cluster_idx + 1,
                    time.time() - t0,
                    len(cluster_tracks),
                )

                cluster_results = []
                deferred_uploads = []

                # Process each clip within this cluster by slicing
                for clip_req in cluster_clips:
                    clip_id = clip_req.clip_id
                    logger.info(
                        "--- Processing clip %s (%.1fs-%.1fs) ---",
                        clip_id,
                        clip_req.start_time,
                        clip_req.end_time,
                    )
                    clip_start_rel = clip_req.start_time - cluster_start
                    clip_end_rel = clip_req.end_time - cluster_start
                    clip_duration = clip_end_rel - clip_start_rel
                    abs_clip_start = clip_req.start_time - segment_offset
                    clip_pretrim = os.path.join(
                        cluster_workdir, f"pretrim_{clip_id}.mp4"
                    )
                    try:

                        # --- Frame-index anchor for slicing cluster_tracks ---
                        # analysis.json tracks are indexed on the ORIGINAL video's
                        # global timeline (see stitch_chunk_tracks in the analyzer),
                        # but live-tracked cluster_tracks come back 0-based from
                        # THIS cluster's own start (get_tracks_and_scores decodes
                        # starting at effective_cluster_start). Mixing these up
                        # silently emptied out tracks for non-first clusters.
                        if precomputed_analysis:
                            track_anchor_start = clip_req.start_time
                            track_anchor_end = clip_req.end_time
                        else:
                            track_anchor_start = clip_start_rel
                            track_anchor_end = clip_end_rel

                        start_frame_global = int(round(track_anchor_start * fps))
                        end_frame_global = int(round(track_anchor_end * fps))
                        clip_frame_count = max(1, end_frame_global - start_frame_global)

                        # --- Seek position for reading actual video frames ---
                        # `vurl` is the locally downloaded file, whose own timeline
                        # starts at `segment_offset` seconds into the ORIGINAL video
                        # (0 for non-YouTube sources, where the whole file is
                        # downloaded). Must always subtract segment_offset here —
                        # mirrors `effective_start` in the single-clip reframe().
                        abs_clip_start = clip_req.start_time - segment_offset

                        if clip_frame_count <= 0:
                            logger.warning("No frames for clip %s", clip_id)
                            cluster_results.append(
                                {
                                    "clip_id": clip_id,
                                    "success": False,
                                    "error": "No frames",
                                }
                            )
                            continue

                        # Slice face tracks for this clip's time range
                        clip_tracks = []
                        clip_scores = []
                        for tidx, tr in enumerate(cluster_tracks):
                            track_frames = tr["track"]["frame"]
                            mask = (track_frames >= start_frame_global) & (
                                track_frames < end_frame_global
                            )
                            if not np.any(mask):
                                continue

                            indices = np.where(mask)[0]
                            if len(indices) > 0:
                                # Ensure frame indices are sorted in ascending order
                                sort_idx = np.argsort(track_frames[indices])
                                indices = indices[sort_idx]
                                # Deduplicate frame indices, keeping the first occurrence
                                _, uniq_idx = np.unique(track_frames[indices], return_index=True)
                                indices = indices[uniq_idx]

                            local_frames = track_frames[indices] - start_frame_global
                            new_track = {
                                "track": {
                                    "frame": local_frames,
                                    "bbox": tr["track"]["bbox"][indices] if isinstance(tr["track"]["bbox"], np.ndarray) and len(tr["track"]["bbox"]) == len(track_frames) else tr["track"]["bbox"],
                                },
                                "proc_track": {
                                    "x": tr["proc_track"]["x"][indices],
                                    "y": tr["proc_track"]["y"][indices],
                                    "s": tr["proc_track"]["s"][indices],
                                },
                            }
                            sc = cluster_scores[tidx]
                            sc_arr = np.array(sc)
                            if len(sc_arr) == len(track_frames):
                                new_scores = sc_arr[indices]
                            elif len(sc_arr) >= len(indices):
                                new_scores = sc_arr[:len(indices)]
                            else:
                                # Fallback pad with zero score
                                new_scores = np.pad(sc_arr, (0, len(indices) - len(sc_arr)), mode='constant')

                            # Pipeline Data Integrity Assertions
                            assert len(new_track["track"]["frame"]) == len(new_track["proc_track"]["x"]), "Track frames and proc_track.x length mismatch"
                            assert len(new_track["proc_track"]["x"]) == len(new_track["proc_track"]["y"]), "proc_track.x and y length mismatch"
                            assert len(new_track["proc_track"]["x"]) == len(new_track["proc_track"]["s"]), "proc_track.x and s length mismatch"
                            assert len(new_scores) == len(new_track["track"]["frame"]), "Scores length does not match track frames length"
                            if len(new_track["track"]["frame"]) > 1:
                                assert np.all(np.diff(new_track["track"]["frame"]) > 0), "Track frame indices must be strictly increasing"

                            clip_tracks.append(new_track)
                            clip_scores.append(new_scores)

                        crop_mode = clip_req.crop_mode
                        reported_crop_mode = crop_mode
                        if crop_mode == "auto":
                            reported_crop_mode = self.classify_layout(
                                clip_tracks,
                                clip_scores,
                                actual_w,
                                actual_h,
                            )
                        logger.info("Clip %s layout (reported): %s", clip_id, reported_crop_mode)

                        # Slice scene bounds for this clip
                        clip_scene_bounds = []
                        for sf, ef in cluster_scene_bounds:
                            adj_sf = max(0, sf - start_frame_global)
                            adj_ef = min(clip_frame_count, ef - start_frame_global)
                            if adj_ef > adj_sf:
                                clip_scene_bounds.append((adj_sf, adj_ef))
                        if not clip_scene_bounds:
                            clip_scene_bounds = [(0, clip_frame_count)]

                        # Pre-trim source to a clip-specific file using ffmpeg's
                        # precise input seeking.  Both video frames and audio are
                        # then extracted from THIS file at position 0, guaranteeing
                        # perfect A/V sync.  The previous approach sought into the
                        # full source independently for video (via ffmpegcv two-pass
                        # seek) and audio (via ffmpeg single-pass seek), and the
                        # two-pass seek landed later due to B-frame reordering and
                        # keyframe alignment, causing video to lag audio.
                        # Pre-trim source to a clip-specific file using ffmpeg's
                        # precise input seeking. Both video frames and audio are
                        # then extracted from THIS file at position 0, guaranteeing
                        # perfect A/V sync.
                        clip_pretrim = os.path.join(
                            cluster_workdir, f"pretrim_{clip_id}.mp4"
                        )
                        # Precise frame-accurate pre-trim (re-encode ultrafast so frame 0 starts EXACTLY at abs_clip_start)
                        pretrim_codec = (
                            ["h264_nvenc", "-preset", "p1"]
                            if self.use_nvenc
                            else ["libx264", "-preset", "ultrafast", "-crf", "18"]
                        )
                        subprocess.run(
                            [
                                "ffmpeg",
                                "-y",
                                "-ss",
                                str(abs_clip_start),
                                "-i",
                                vurl,
                                "-t",
                                str(clip_duration),
                                "-c:v",
                                *pretrim_codec,
                                "-c:a",
                                "aac",
                                "-b:a",
                                "192k",
                                "-avoid_negative_ts",
                                "make_zero",
                                clip_pretrim,
                                "-loglevel",
                                "warning",
                            ],
                            check=True,
                            timeout=_FFMPEG_LONG_TIMEOUT_S,
                        )

                        # Extract WAV for zoom punch audio analysis (lightweight 16kHz mono)
                        clip_wav_for_punch = os.path.join(
                            cluster_workdir, f"punch_audio_{clip_id}.wav"
                        )
                        try:
                            subprocess.run(
                                [
                                    "ffmpeg", "-y",
                                    "-i", clip_pretrim,
                                    "-vn", "-ac", "1", "-ar", "16000",
                                    "-acodec", "pcm_s16le",
                                    clip_wav_for_punch,
                                    "-loglevel", "panic",
                                ],
                                check=True, timeout=_FFMPEG_SHORT_TIMEOUT_S,
                            )
                        except Exception:
                            clip_wav_for_punch = None

                        # Render this clip
                        orig_name = f"orig_{uuid.uuid4()}.mp4"
                        local_orig = os.path.join(tmpdir, orig_name)

                        t1 = time.time()
                        frame_layout, quality_metrics = self.render_vertical(
                            clip_tracks,
                            clip_scores,
                            None,
                            pya,
                            local_orig,
                            duration=clip_duration,
                            fps=fps,
                            crop_mode=reported_crop_mode,
                            scene_bounds=clip_scene_bounds,
                            video_path=clip_pretrim,
                            start_time_in_video=0.0,
                            audio_wav_path=clip_wav_for_punch,
                        )

                        if not os.path.exists(local_orig) or os.path.getsize(local_orig) == 0:
                            raise RenderError(f"Render failed: output video file not found or empty at {local_orig}")

                        if clip_req.transcript:
                            clip_req.transcript = annotate_transcript_layout(
                                clip_req.transcript, frame_layout, crop_mode, fps
                            )

                        # Extract audio from the SAME pre-trimmed file (no seeking) for 100% A/V sync.
                        clip_audio = os.path.join(
                            cluster_workdir, f"clip_audio_{clip_id}.aac"
                        )
                        subprocess.run(
                            [
                                "ffmpeg",
                                "-y",
                                "-i",
                                clip_pretrim,
                                "-vn",
                                "-c:a",
                                "aac",
                                "-b:a",
                                "192k",
                                clip_audio,
                                "-loglevel",
                                "panic",
                            ],
                            check=True,
                            timeout=_FFMPEG_SHORT_TIMEOUT_S,
                        )

                        synced = local_orig.replace(".mp4", "_synced.mp4")
                        mux_audio_video(
                            video_path=local_orig,
                            audio_path=clip_audio,
                            output_path=synced,
                            fps=fps,
                            use_nvenc=self.use_nvenc,
                        )
                        os.replace(synced, local_orig)

                        render_time = time.time() - t1
                        logger.info("Clip %s rendered in %.1fs", clip_id, render_time)

                        deferred_uploads.append(
                            {
                                "clip_id": clip_id,
                                "local_orig": local_orig,
                                "orig_name": orig_name,
                                "clip_req": clip_req,
                                "crop_mode": crop_mode,
                                "reported_crop_mode": reported_crop_mode,
                                "actual_w": actual_w,
                                "actual_h": actual_h,
                                "quality_metrics": quality_metrics,
                            }
                        )
                    except Exception as e:
                        logger.warning(
                            "Clip %s AI reframing failed (%s). Falling back to letterbox mode...",
                            clip_id,
                            e,
                            exc_info=True,
                        )
                        try:
                            if not os.path.exists(clip_pretrim):
                                pretrim_codec = (
                                    ["h264_nvenc", "-preset", "p1"]
                                    if self.use_nvenc
                                    else ["libx264", "-preset", "ultrafast", "-crf", "18"]
                                )
                                subprocess.run(
                                    [
                                        "ffmpeg",
                                        "-y",
                                        "-ss",
                                        str(abs_clip_start),
                                        "-i",
                                        vurl,
                                        "-t",
                                        str(clip_duration),
                                        "-c:v",
                                        *pretrim_codec,
                                        "-c:a",
                                        "aac",
                                        "-b:a",
                                        "192k",
                                        "-avoid_negative_ts",
                                        "make_zero",
                                        clip_pretrim,
                                        "-loglevel",
                                        "warning",
                                    ],
                                    check=True,
                                    timeout=_FFMPEG_LONG_TIMEOUT_S,
                                )

                            orig_name = f"orig_{uuid.uuid4()}.mp4"
                            local_orig = os.path.join(tmpdir, orig_name)

                            t1 = time.time()
                            reported_crop_mode = "letterbox"
                            frame_layout, quality_metrics = self.render_vertical(
                                [],
                                [],
                                None,
                                pya,
                                local_orig,
                                duration=clip_duration,
                                fps=fps,
                                crop_mode="letterbox",
                                scene_bounds=[(0, max(1, int(round(clip_duration * fps))))],
                                video_path=clip_pretrim,
                                start_time_in_video=0.0,
                            )

                            if not os.path.exists(local_orig) or os.path.getsize(local_orig) == 0:
                                raise RenderError(f"Render failed: fallback video file not found or empty at {local_orig}")

                            if clip_req.transcript:
                                clip_req.transcript = annotate_transcript_layout(
                                    clip_req.transcript, frame_layout, "letterbox", fps
                                )

                            clip_audio = os.path.join(
                                cluster_workdir, f"clip_audio_{clip_id}.aac"
                            )
                            if not os.path.exists(clip_audio):
                                subprocess.run(
                                    [
                                        "ffmpeg",
                                        "-y",
                                        "-i",
                                        clip_pretrim,
                                        "-vn",
                                        "-c:a",
                                        "aac",
                                        "-b:a",
                                        "192k",
                                        clip_audio,
                                        "-loglevel",
                                        "panic",
                                    ],
                                    check=True,
                                    timeout=_FFMPEG_SHORT_TIMEOUT_S,
                                )

                            synced = local_orig.replace(".mp4", "_synced.mp4")
                            mux_audio_video(
                                video_path=local_orig,
                                audio_path=clip_audio,
                                output_path=synced,
                                fps=fps,
                                use_nvenc=self.use_nvenc,
                            )
                            os.replace(synced, local_orig)

                            render_time = time.time() - t1
                            logger.info("Clip %s fallback letterbox rendered in %.1fs", clip_id, render_time)

                            deferred_uploads.append(
                                {
                                    "clip_id": clip_id,
                                    "local_orig": local_orig,
                                    "orig_name": orig_name,
                                    "clip_req": clip_req,
                                    "crop_mode": "letterbox",
                                    "reported_crop_mode": "letterbox",
                                    "actual_w": actual_w,
                                    "actual_h": actual_h,
                                    "quality_metrics": quality_metrics,
                                }
                            )
                        except Exception as fallback_err:
                            logger.error(
                                "Fallback letterbox rendering also failed for clip %s: %s", clip_id, fallback_err, exc_info=True
                            )
                            cluster_results.append(
                                {
                                    "clip_id": clip_id,
                                    "success": False,
                                    "error": f"Reframing failed ({e}) and fallback failed ({fallback_err})",
                                }
                            )

                # Free cluster memory after all clips in this cluster are processed
                if cluster_frames is not None and hasattr(cluster_frames, "_mmap") and cluster_frames._mmap is not None:
                    try:
                        cluster_frames._mmap.close()
                    except Exception:
                        pass
                del cluster_tracks, cluster_scores, cluster_frames, cluster_scene_bounds
                # Clean up cluster work directory to free disk
                import shutil

                shutil.rmtree(cluster_workdir, ignore_errors=True)

                return cluster_results, deferred_uploads

            import concurrent.futures

            results = []
            all_deferred = []
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(4, len(clusters))
            ) as executor:
                futures = {
                    executor.submit(process_cluster, idx, cl): idx
                    for idx, cl in enumerate(clusters)
                }
                for fut in concurrent.futures.as_completed(futures):
                    cluster_idx = futures[fut]
                    try:
                        cluster_res, cluster_deferred = fut.result()
                        results.extend(cluster_res)
                        all_deferred.extend(cluster_deferred)
                        logger.info(
                            "Cluster %d/%d render complete", cluster_idx + 1, len(clusters)
                        )
                    except Exception as e:
                        logger.error(
                            "Cluster %d failed: %s",
                            cluster_idx + 1,
                            e,
                            exc_info=True,
                        )

            # 5. Run all uploads and caption burns in parallel (concurrency limited to prevent CPU starvation)
            if all_deferred:
                logger.info("Starting batch upload and caption burn for %d clips...", len(all_deferred))

                def perform_upload_and_burn(task):
                    clip_id = task["clip_id"]
                    local_orig = task["local_orig"]
                    orig_name = task["orig_name"]
                    clip_req = task["clip_req"]
                    crop_mode = task["crop_mode"]
                    reported_crop_mode = task["reported_crop_mode"]
                    actual_w = task["actual_w"]
                    actual_h = task["actual_h"]

                    orig_url = None
                    preview_url = None
                    thumbnail_url = None
                    local_preview = None
                    success = False
                    error_msg = None

                    try:
                        # Upload original and burn captions concurrently for this single clip
                        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                            fut_upload = ex.submit(
                                upload_to_r2, local_orig, f"reframes/{orig_name}"
                            )

                            fut_burn = None
                            if clip_req.transcript and clip_req.styling:
                                from burner import burn_captions_local

                                local_preview = os.path.join(
                                    tmpdir, f"preview_{uuid.uuid4()}.mp4"
                                )
                                fut_burn = ex.submit(
                                    burn_captions_local,
                                    local_video=local_orig,
                                    local_output=local_preview,
                                    transcript=clip_req.transcript,
                                    styling=clip_req.styling,
                                    show_watermark=clip_req.show_watermark,
                                    crop_mode=crop_mode,
                                    quality=req.quality or "preview",
                                    tmpdir=tmpdir,
                                )

                            orig_url = fut_upload.result()
                            if fut_burn:
                                try:
                                    preview_url, thumbnail_url = fut_burn.result()
                                except Exception as e:
                                    logger.error(
                                        "Caption burn failed for %s: %s", clip_id, e
                                    )
                        success = True
                    except Exception as e:
                        logger.error("Failed to upload/burn clip %s: %s", clip_id, e, exc_info=True)
                        error_msg = str(e)
                    finally:
                        # Clean up local files
                        try:
                            os.remove(local_orig)
                        except OSError:
                            pass
                        if local_preview:
                            try:
                                os.remove(local_preview)
                            except OSError:
                                pass

                    if success:
                        return {
                            "clip_id": clip_id,
                            "success": True,
                            "original_video_url": orig_url,
                            "preview_video_url": preview_url,
                            "thumbnail_url": thumbnail_url,
                            "crop_mode": reported_crop_mode,
                            "source_width": actual_w,
                            "source_height": actual_h,
                            "quality_metrics": task.get("quality_metrics"),
                            "transcript": clip_req.transcript,
                        }
                    else:
                        return {
                            "clip_id": clip_id,
                            "success": False,
                            "error": error_msg,
                        }

                with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(all_deferred))) as upload_executor:
                    upload_futures = [
                        upload_executor.submit(perform_upload_and_burn, task)
                        for task in all_deferred
                    ]
                    for fut in concurrent.futures.as_completed(upload_futures):
                        try:
                            clip_res = fut.result()
                            results.append(clip_res)
                        except Exception as e:
                            logger.error("Upload future failed: %s", e, exc_info=True)

        logger.info(
            "=== BATCH REFRAME COMPLETE === (%d/%d succeeded)",
            sum(1 for r in results if r.get("success")),
            len(results),
        )
        return {"success": True, "results": results}

    @modal.fastapi_endpoint(method="POST")
    async def eval_clip(self, file: UploadFile = File(...), label: str = Form("")):
        """
        Eval-only endpoint: runs face tracking + ASD + layout classification
        on an already-trimmed local clip and returns summary stats. Does NOT
        render the final vertical video — this is for building a baseline to
        diff against before/after model swaps (face detector, tracker, etc).

        Send a raw video file (already cut to the segment you want to test)
        as multipart form data under "file", with an optional "label" field.
        """
        import numpy as np

        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = os.path.join(tmpdir, "clip.mp4")
            with open(local_path, "wb") as f:
                f.write(await file.read())

            video_info = self.get_video_info(local_path)
            fps = video_info["fps"]
            duration_secs = video_info.get("duration") or 0.0
            if duration_secs <= 0:
                return {"label": label, "error": "Could not determine clip duration"}

            segment_audio = os.path.join(tmpdir, "segment_audio.aac")
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", local_path,
                    "-vn", "-c:a", "aac", "-b:a", "192k",
                    segment_audio, "-loglevel", "panic",
                ],
                check=True, timeout=_FFMPEG_LONG_TIMEOUT_S,
            )

            t0 = time.time()
            tracks, scores, audio, pyf, pya, scene_bounds = self.get_tracks_and_scores(
                local_path, 0.0, duration_secs, tmpdir,
                fps=fps, audio_url=segment_audio,
            )
            elapsed = time.time() - t0

            layout = self.classify_layout(
                tracks, scores,
                video_info.get("width", 1920), video_info.get("height", 1080),
            )

            track_summaries = []
            for tidx, tr in enumerate(tracks):
                sc = scores[tidx]
                frames = tr["track"]["frame"]
                track_summaries.append({
                    "track_id": tidx,
                    "frame_count": int(len(frames)),
                    "duration_s": round(float(len(frames)) / fps, 2) if fps else None,
                    "max_score": round(float(np.max(sc)), 3) if len(sc) else 0.0,
                    "mean_score": round(float(np.mean(sc)), 3) if len(sc) else 0.0,
                    "mean_size_px": round(float(np.mean(tr["proc_track"]["s"])), 1),
                    "first_frame": int(frames[0]) if len(frames) else None,
                    "last_frame": int(frames[-1]) if len(frames) else None,
                })

            if hasattr(pyf, "_mmap") and pyf._mmap is not None:
                try:
                    pyf._mmap.close()
                except Exception:
                    pass

            return {
                "label": label,
                "fps": fps,
                "duration_s": round(duration_secs, 2),
                "tracking_time_s": round(elapsed, 2),
                "num_tracks": len(tracks),
                "layout_decision": layout,
                "tracks": track_summaries,
        }
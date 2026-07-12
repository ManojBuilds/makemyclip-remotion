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

Bug fix in this refactor: ``face_count_window`` (a deque used to stabilize
the multi-person/letterbox layout decision) was referenced but never
declared in the original ``main.py``, which crashed the render loop with
``NameError`` whenever a third face appeared. It is now properly
initialized at the top of the render loop.
"""

from __future__ import annotations

import glob
import logging
import os
import subprocess
import sys
import tempfile
import time
import uuid

import modal

from config import ai_secret, app, image, youtube_cookies_secret
from errors import DownloadError, InvalidInputError, RenderError, VideoProbeError
from models import ReframeRequest, BatchReframeRequest
from r2_storage import assert_r2_env, upload_to_r2
from utils import StageTimer, is_youtube_url, validate_url
from ytdlp_helper import (
    SEGMENT_DOWNLOAD_PAD_S,
    download_youtube_video,
    remove_bgutil_pot_provider,
)

logger = logging.getLogger("makemyclip.reframer")

# --- Tuning constants for the speaker-locking reframer ---
ACTIVE_SPEAKER_THRESHOLD = 0.5  # ASD score must exceed this to count as "speaking"
DEAD_ZONE_PX = 40  # Prevent faces from touching the edges (reduced to 40px for faster camera response)
SPEAKER_HOLD_SECONDS = 1.5  # hold last speaker through brief pauses
FACE_COUNT_WINDOW_LEN = 11  # frames used to stabilize face-count decision
LETTERBOX_TARGET_HEIGHT_RATIO = 0.68

# A 90s clip seek into a 2hr source can take a while — use a generous limit
# so a stalled ffmpeg doesn't hang the worker. 20 minutes covers the worst
# case observed in production.
_FFMPEG_LONG_TIMEOUT_S = 1200
_FFMPEG_SHORT_TIMEOUT_S = 60


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
            
            if crop_mode in ("split", "course", "letterbox"):
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


@app.cls(
    gpu="L4",
    image=image,
    timeout=900,  # batch reframe may take longer
    secrets=[ai_secret, youtube_cookies_secret],
    max_containers=20,
    min_containers=1,
)
@modal.concurrent(max_inputs=1)
class AIReframe:
    @modal.enter()
    def setup(self):
        # 1. Remove the bgutil PO Token plugin to prevent infinite retry loops
        remove_bgutil_pot_provider()

        # 2. Load the face detector + active-speaker model
        os.chdir("/root/asd")
        sys.path.append("/root/asd")
        from ASD import ASD
        from model.faceDetector.s3fd import S3FD

        self.DET = S3FD(device="cuda")
        self.ASD_MODEL = ASD()
        self.ASD_MODEL.loadParameters("/root/asd/weight/finetuning_TalkSet.model")
        self.ASD_MODEL.eval()
        self.ASD_MODEL.cuda()

        # 3. Probe NVENC once at startup — saves a try/except per render
        self.use_nvenc = self._probe_nvenc()
        logger.info("NVENC available: %s", self.use_nvenc)

        # 4. Validate required env vars upfront so we fail fast on misconfig
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
        import numpy as np

        if not tracks:
            return "letterbox"

        valid_tracks = []
        for tidx, tr in enumerate(tracks):
            sc = scores[tidx]
            max_score = float(np.max(sc)) if len(sc) > 0 else 0.0
            xs = tr["proc_track"]["x"]
            ys = tr["proc_track"]["y"]
            movement = float(np.std(xs) + np.std(ys)) if len(xs) > 0 else 0.0

            sizes = tr["proc_track"]["s"]
            mean_size = float(np.mean(sizes)) if len(sizes) > 0 else 1.0
            rel_movement = movement / mean_size if mean_size > 0 else 0.0

            # Filter out inactive / noise / fake tracks (posters, toys, background objects)
            # 1. Purge tiny tracks (mean size < 50 pixels) which are noise/background elements
            # 2. Purge silent tracks (score < 0.15) that don't show real movement (movement < 15.0 px or rel_movement < 0.12)
            is_valid = True
            if mean_size < 25.0:
                is_valid = False
            elif max_score < 0.12:
                if movement < 5.0 and rel_movement < 0.05:
                    is_valid = False

            if is_valid:
                valid_tracks.append((tidx, tr))

        if not valid_tracks:
            return "letterbox"

        # Filter out short, transient tracks (less than 50% of longest track duration)
        max_duration = max(len(t[1]["proc_track"]["x"]) for t in valid_tracks)
        duration_threshold = 0.50 * max_duration
        valid_tracks = [
            t
            for t in valid_tracks
            if len(t[1]["proc_track"]["x"]) >= duration_threshold
        ]

        if not valid_tracks:
            return "letterbox"

        # Cluster remaining valid tracks horizontally (group same speaker's fragmented tracks)
        columns = []
        for tidx, tr in valid_tracks:
            mu_x = np.mean(tr["proc_track"]["x"]) / width
            placed = False
            for col in columns:
                if abs(col["mean_x"] - mu_x) < 0.15:
                    col["tracks"].append((tidx, tr))
                    col["mean_x"] = np.mean(
                        [
                            np.mean(t[1]["proc_track"]["x"]) / width
                            for t in col["tracks"]
                        ]
                    )
                    placed = True
                    break
            if not placed:
                columns.append({"mean_x": mu_x, "tracks": [(tidx, tr)]})

        num_columns = len(columns)
        logger.info(
            "classify_layout: Found %d valid tracks, clustered into %d columns.",
            len(valid_tracks),
            num_columns,
        )
        for i, col in enumerate(columns):
            logger.info(
                "  Column %d: mean_x=%.2f, track_idxs=%s",
                i,
                col["mean_x"],
                [t[0] for t in col["tracks"]],
            )

        # Check for temporal overlap (exist simultaneously on screen)
        # to distinguish multiple people from fragmented tracks of the same person.
        max_duration = max(len(t[1]["proc_track"]["x"]) for t in valid_tracks)
        overlap_threshold = max(1, min(12, int(0.2 * max_duration)))

        has_temporal_overlap = False
        for i in range(len(valid_tracks)):
            for j in range(i + 1, len(valid_tracks)):
                tr1 = valid_tracks[i][1]
                tr2 = valid_tracks[j][1]

                # Support both mock test objects and real runtime objects
                f1 = (
                    tr1["track"]["frame"]
                    if "track" in tr1
                    else list(range(len(tr1["proc_track"]["x"])))
                )
                f2 = (
                    tr2["track"]["frame"]
                    if "track" in tr2
                    else list(range(len(tr2["proc_track"]["x"])))
                )

                set1 = set(f1)
                set2 = set(f2)
                if len(set1.intersection(set2)) >= overlap_threshold:
                    has_temporal_overlap = True
                    break
            if has_temporal_overlap:
                break

        if num_columns == 1:
            if len(valid_tracks) > 1 and has_temporal_overlap:
                logger.info(
                    "classify_layout decision: reframe (multiple distinct speakers overlapping in time in single column - preferred over letterbox)"
                )
                return "reframe"
            elif len(valid_tracks) > 1:
                logger.info(
                    "classify_layout decision: reframe (multiple tracks in single column, no temporal overlap)"
                )
                return "reframe"

            # Single speaker column: check for corner-mounted webcam (Course presentation layout)
            tidx, tr = columns[0]["tracks"][0]
            avg_face_width_pct = np.mean(tr["proc_track"]["s"]) / width
            mean_x_pct = np.mean(tr["proc_track"]["x"]) / width
            mean_y_pct = np.mean(tr["proc_track"]["y"]) / height

            is_corner = (mean_x_pct < 0.30 or mean_x_pct > 0.70) and (
                mean_y_pct < 0.30 or mean_y_pct > 0.70
            )
            if avg_face_width_pct < 0.20 and is_corner:
                logger.info(
                    "classify_layout decision: course (corner speaker: x=%.2f, y=%.2f, size=%.2f)",
                    mean_x_pct,
                    mean_y_pct,
                    avg_face_width_pct,
                )
                return "course"

            # Check if the face is extremely small in the frame (e.g., wide stage show, standup comedy).
            # Zooming into a face smaller than 4.5% of the video width looks pixelated/blurry and cuts out body context.
            if avg_face_width_pct < 0.022:
                logger.info(
                    "classify_layout decision: letterbox (face width %.2f%% is too small for reframe)",
                    avg_face_width_pct * 100,
                )
                return "letterbox"

            logger.info("classify_layout decision: reframe")
            return "reframe"

        elif num_columns == 2:
            mu_x1 = columns[0]["mean_x"]
            mu_x2 = columns[1]["mean_x"]
            logger.info("classify_layout columns: col0=%.2f, col1=%.2f", mu_x1, mu_x2)

            if not has_temporal_overlap:
                logger.info(
                    "classify_layout decision: reframe (2 columns but no temporal overlap)"
                )
                return "reframe"

            # Check if any column is in a corner (presenter slides, drummer in corner, background reaction)
            def is_corner_col(col):
                for tidx, tr in col["tracks"]:
                    mean_x = np.mean(tr["proc_track"]["x"]) / width
                    mean_y = np.mean(tr["proc_track"]["y"]) / height
                    mean_s = np.mean(tr["proc_track"]["s"]) / width
                    if (
                        (mean_x < 0.30 or mean_x > 0.70)
                        and (mean_y < 0.35 or mean_y > 0.65)
                        and mean_s < 0.15
                    ):
                        return True
                return False

            # Verify both columns have at least one track with speaking activity (max_score >= 0.35)
            def has_speaking_track(col):
                for tidx, tr in col["tracks"]:
                    sc = scores[tidx]
                    if len(sc) > 0 and np.max(sc) >= 0.35:
                        return True
                return False

            is_split_candidate = (mu_x1 < 0.48 and mu_x2 > 0.52) or (
                mu_x2 < 0.48 and mu_x1 > 0.52
            )
            has_corner_face = is_corner_col(columns[0]) or is_corner_col(columns[1])

            # If one of the speakers is centered (e.g. 0.45 <= x <= 0.58), it's a center-anchored stage show
            # with secondary side/corner reactions, not a left/right split podcast.
            has_centered_speaker = (0.45 <= mu_x1 <= 0.58) or (0.45 <= mu_x2 <= 0.58)

            both_columns_speak = has_speaking_track(columns[0]) and has_speaking_track(
                columns[1]
            )

            if (
                is_split_candidate
                and not has_corner_face
                and not has_centered_speaker
                and both_columns_speak
            ):
                logger.info("classify_layout decision: split")
                return "split"
            else:
                # If they overlap in time but are not split screen, prefer reframe (active speaker tracking)
                # over letterbox unless the faces are too small.
                tidx1, tr1 = columns[0]["tracks"][0]
                tidx2, tr2 = columns[1]["tracks"][0]
                avg_face_width_pct1 = np.mean(tr1["proc_track"]["s"]) / width
                avg_face_width_pct2 = np.mean(tr2["proc_track"]["s"]) / width

                if avg_face_width_pct1 < 0.022 or avg_face_width_pct2 < 0.022:
                    logger.info(
                        "classify_layout decision: letterbox (faces are too small for reframe: %.2f%%, %.2f%%)",
                        avg_face_width_pct1 * 100,
                        avg_face_width_pct2 * 100,
                    )
                    return "letterbox"

                logger.info(
                    "classify_layout decision: reframe (2 columns overlapping in time but not split-screen candidate. centered=%s, speaking=%s)",
                    has_centered_speaker,
                    both_columns_speak,
                )
                return "reframe"

        else:
            logger.info("classify_layout decision: letterbox (3+ columns)")
            return "letterbox"

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
        crop_mode: str = "reframe",
        audio_url: str | None = None,
        is_preview: bool = False,
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
            "-ss",
            str(start_time),
            "-t",
            str(duration),
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
            "-ss",
            str(start_time),
            "-i",
            video_url,
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
            "-ss",
            str(start_time),
            "-i",
            video_url,
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
                "-ss",
                str(start_time),
                "-i",
                video_url,
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
            v_out = cv2.VideoWriter(
                crop_file + "t.avi",
                cv2.VideoWriter_fourcc(*"XVID"),
                fps_local,
                (224, 224),
            )
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
            for fidx, frame in enumerate(track["frame"]):
                # Clamp frame index to valid range
                safe_frame = min(int(frame), len(frames_local) - 1)
                bs, cs = dets["s"][fidx], 0.40
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
                    # Face crop is empty (bs near-zero from median filter) — write gray placeholder
                    v_out.write(np.full((224, 224, 3), 110, dtype=np.uint8))
                else:
                    v_out.write(cv2.resize(face, (224, 224)))
            v_out.release()

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
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    crop_file + "t.avi",
                    "-i",
                    crop_file + ".wav",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "copy",
                    crop_file + ".avi",
                    "-loglevel",
                    "panic",
                ],
                timeout=_FFMPEG_SHORT_TIMEOUT_S,
            )
            return {"track": track, "proc_track": dets}

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

        # 5. Detect faces per frame (IN-MEMORY, no disk reads)
        #    PERF: Skip every 4th frame universally — faces barely move between
        #    consecutive 25fps frames. Combined with in-memory frames this
        #    cuts detection time by ~75%.
        _DETECT_SKIP = 4  # process every Nth frame (was 2 for non-preview)
        detected_faces = []
        _prev_frame_faces = []
        for fidx in range(total_frames):
            if fidx % _DETECT_SKIP != 0:
                # Reuse previous detections with updated frame index
                detected_faces.append(
                    [
                        {"frame": fidx, "bbox": list(f["bbox"]), "conf": f["conf"]}
                        for f in _prev_frame_faces
                    ]
                )
                continue

            img = frames_mem[fidx]
            h, w = img.shape[:2]
            if h > 640:
                scale = 640 / h
                img_detect = cv2.resize(img, (int(w * scale), 640))
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
            _prev_frame_faces = [
                {"frame": fidx, "bbox": b[:-1].tolist(), "conf": b[-1]} for b in res
            ]
            detected_faces.append(_prev_frame_faces)

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
            with ThreadPoolExecutor(max_workers=4) as ex:
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
                if len(aud) == 0:
                    all_scores.append(np.zeros(track_frame_count))
                    continue

                af = python_speech_features.mfcc(
                    aud, 16000, numcep=13, winlen=0.025, winstep=0.010
                )

                vc = cv2.VideoCapture(os.path.join(pycrop_path, "%05d.avi" % idx))
                vf = []
                while vc.isOpened():
                    ret, fr = vc.read()
                    if not ret:
                        break
                    vf.append(
                        cv2.resize(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), (224, 224))[
                            56:168, 56:168
                        ]
                    )
                vc.release()
                vf = np.array(vf)

                # Free disk: each track produces ~50MB of intermediates.
                for ext in ("t.avi", ".avi", ".wav"):
                    f_path = os.path.join(pycrop_path, "%05d%s" % (idx, ext))
                    try:
                        os.remove(f_path)
                    except OSError:
                        pass

                if len(vf) == 0:
                    all_scores.append(np.zeros(track_frame_count))
                    continue

                audio_steps = af.shape[0] // 4 * 4
                video_steps = int(vf.shape[0] / fps * 100) // 4 * 4

                n_audio_steps = min(audio_steps, video_steps)
                n_video_frames = int(n_audio_steps / 100.0 * fps)

                af = af[:n_audio_steps, :]
                vf = vf[:n_video_frames, :, :]

                if n_audio_steps == 0 or n_video_frames == 0:
                    all_scores.append(np.zeros(track_frame_count))
                    continue

                length = n_audio_steps / 100.0

                with torch.no_grad():
                    inA_full = torch.FloatTensor(af).unsqueeze(0).cuda()
                    inV_full = torch.FloatTensor(vf).unsqueeze(0).cuda()
                    eA_full = self.ASD_MODEL.model.forward_audio_frontend(inA_full)
                    eV_full = self.ASD_MODEL.model.forward_visual_frontend(inV_full)

                tr_scores = []
                for dur in range(1, 7):
                    batch = int(math.ceil(length / dur))
                    scs = []
                    for i in range(batch):
                        a_start = i * dur * 25
                        a_end = (i + 1) * dur * 25
                        v_start = int(round(i * dur * fps))
                        v_end = int(round((i + 1) * dur * fps))

                        eA = eA_full[:, a_start:a_end, :]
                        eV = eV_full[:, v_start:v_end, :]

                        if eA.shape[1] == 0 or eV.shape[1] == 0:
                            continue

                        min_steps = min(eA.shape[1], eV.shape[1])
                        eA = eA[:, :min_steps, :]
                        eV = eV[:, :min_steps, :]

                        with torch.no_grad():
                            out = self.ASD_MODEL.model.forward_audio_visual_backend(
                                eA, eV
                            )
                            scs.extend(self.ASD_MODEL.lossAV.forward(out, labels=None))

                    if scs:
                        tr_scores.append(scs)

                if tr_scores:
                    min_len = min(len(s) for s in tr_scores)
                    all_scores.append(
                        np.round(
                            np.mean([s[:min_len] for s in tr_scores], axis=0), 1
                        ).astype(float)
                    )
                else:
                    all_scores.append(np.zeros(track_frame_count))

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
            # Inject -ss before input and -t after input
            cap.ffmpeg_cmd = cap.ffmpeg_cmd.replace(
                f' -i "{filename}"',
                f' -ss {ss_val} -i "{filename}"{t_str}'
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
        for tidx, tr in enumerate(tracks):
            sc = scores[tidx]

            # --- FAKE FACE FILTER ---
            # Posters, statues, and background extras who never speak will have near-zero ASD scores.
            # Real speakers will have a track max score > 0.5. Even listening guests will move slightly.
            track_max_score = float(np.max(sc)) if len(sc) > 0 else 0.0
            xs = tr["proc_track"]["x"]
            ys = tr["proc_track"]["y"]
            std_x = float(np.std(xs)) if len(xs) > 0 else 0.0
            std_y = float(np.std(ys)) if len(ys) > 0 else 0.0
            movement = std_x + std_y

            sizes = tr["proc_track"]["s"]
            mean_size = float(np.mean(sizes)) if len(sizes) > 0 else 1.0
            rel_movement = movement / mean_size if mean_size > 0 else 0.0

            logger.info(
                "Track %d evaluation: max_score=%.3f, movement=%.3f, rel_movement=%.3f, mean_size=%.3f",
                tidx,
                track_max_score,
                movement,
                rel_movement,
                mean_size,
            )

            # Aggressively filter out fake faces (posters, skulls, t-shirts, toys)
            # 1. Purge tiny tracks (mean size < 50 pixels) which are noise/background elements
            # 2. Purge silent tracks (score < 0.15) that don't show real movement (movement < 15.0 px or rel_movement < 0.12)
            is_fake = False
            if mean_size < 25.0:
                is_fake = True
            elif track_max_score < 0.12:
                if movement < 5.0 and rel_movement < 0.05:
                    is_fake = True

            if is_fake:
                logger.info(
                    "Purged fake face track %d (score %.2f, move %.2f, rel_move %.3f, size %.1f)",
                    tidx,
                    track_max_score,
                    movement,
                    rel_movement,
                    mean_size,
                )
                continue

            for fidx, f in enumerate(tr["track"]["frame"]):
                if f >= max_frames:
                    continue
                # Level 100: Responsive 7-frame speech window (0.28s total) to avoid laggy cuts/zooms.
                score_window = sc[max(fidx - 7, 0) : min(fidx + 7, len(sc))]
                avg = float(np.mean(score_window)) if len(score_window) > 0 else 0
                faces[f].append(
                    {
                        "score": avg,
                        "x": tr["proc_track"]["x"][fidx],
                        "y": tr["proc_track"]["y"][fidx],
                        "s": tr["proc_track"]["s"][fidx],
                        "tidx": tidx,
                    }
                )

        if duration is not None:
            logger.info(
                "Limiting frames to %d (duration=%.2fs at %.2ffps)",
                max_frames,
                duration,
                fps,
            )

        sorted_by_len = sorted(
            tracks, key=lambda t: len(t["track"]["frame"]), reverse=True
        )
        has_speaker = len(sorted_by_len) >= 1
        full_x_solo = None
        if has_speaker:
            full_x_solo = self.get_smooth_x_for_track(sorted_by_len[0], len(frames_mem))
            logger.info("Solo speaker locking enabled (%d tracks)", len(tracks))

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
        held_speaker_x = None
        held_speaker_y = None
        held_speaker_s = None
        held_speaker_zoom = 0.115
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

        # --- course layout state ---
        current_cx_course = None
        current_cy_course = None
        current_s_course = None
        current_target_cx_course = None
        current_target_cy_course = None
        current_target_s_course = None

        # Hysteresis to prevent conversational whiplash. Level 100: Snappier 0.8s minimum cut lock.
        MIN_CUT_FRAMES = int(fps * 0.8)
        frames_on_current_speaker = 0

        # Smoothness tuning
        # Lower value = slower, smoother pan. Snappy tracking: 0.06
        SMOOTHING_ALPHA = 0.06

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
        if crop_mode in ("split", "course", "letterbox"):
            mapped = "split" if crop_mode == "split" else ("course" if crop_mode == "course" else "letterbox")
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
                    scene_crop = self.classify_layout(scene_tr, scene_sc, source_w, source_h)
                    
                    if scene_crop == "reframe":
                        mapped = "single"
                    elif scene_crop == "split":
                        mapped = "split"
                    elif scene_crop == "course":
                        mapped = "course"
                    else:
                        mapped = "letterbox"
                else:
                    # crop_mode is "reframe"
                    has_faces = any(len(faces[f]) > 0 for f in range(sf, ef))
                    if not has_faces:
                        mapped = "letterbox"
                    else:
                        two_face_frames = sum(1 for f in range(sf, ef) if len(faces[f]) >= 2)
                        if (two_face_frames / scene_len) > 0.30:
                            mapped = "split"
                        else:
                            mapped = "single"
                
                for f in range(sf, ef):
                    frame_layout[f] = mapped

        _letterbox_shadow = None
        _letterbox_mask = None

        def _make_blurred_bg(img):
            # Dynamic blurred background for premium letterboxing
            bg_scale = 1920 / img.shape[0]
            bg_res = cv2.resize(
                img,
                (int(img.shape[1] * bg_scale), 1920),
                interpolation=cv2.INTER_LINEAR,
            )
            mid_x = bg_res.shape[1] // 2
            bg = bg_res[:, max(0, mid_x - 540) : mid_x + 540]
            if bg.shape[1] < 1080:
                bg = cv2.copyMakeBorder(
                    bg, 0, 0, 0, 1080 - bg.shape[1], cv2.BORDER_REPLICATE
                )
            # Downsample → blur → upsample is much faster than a massive kernel
            small = cv2.resize(bg, (270, 480), interpolation=cv2.INTER_LINEAR)
            # Problem 2: Blur is too strong. Reduced kernel size to retain more context.
            blurred_small = cv2.GaussianBlur(small, (15, 15), 0)
            return cv2.resize(
                blurred_small, (1080, 1920), interpolation=cv2.INTER_LINEAR
            )

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

                scale = 1920 / img.shape[0]

                # Strict Mode Enforcement
                current_layout = frame_layout[fidx]
                use_multi_face_letterbox = current_layout == "letterbox"
                use_course_layout = current_layout == "course"

                # Perfect Layout Snap based on Scene Boundaries
                use_split_screen = current_layout == "split"

                # --- Look-ahead Interjection Filter ---
                # If the current "best" speaker is different from the last one,
                # verify they continue speaking for at least 10 frames before switching.
                # This prevents the camera from bouncing for a "Yeah" or "Right".
                look_ahead_frames = 12
                potential_best = None
                if faces[fidx]:
                    potential_best = max(faces[fidx], key=lambda x: x["score"])

                is_interjection = False
                if (
                    potential_best
                    and current_track_id is not None
                    and potential_best["tidx"] != current_track_id
                ):
                    # New speaker detected — check future frames
                    active_count = 0
                    for i in range(1, look_ahead_frames + 1):
                        future_idx = fidx + i
                        if future_idx >= max_frames:
                            break
                        # If this speaker appears in future frames with high score
                        future_faces = faces[future_idx]
                        if any(
                            f["tidx"] == potential_best["tidx"]
                            and f["score"] > ACTIVE_SPEAKER_THRESHOLD
                            for f in future_faces
                        ):
                            active_count += 1

                    if active_count < (look_ahead_frames // 2):
                        is_interjection = True

                # Sticky-speaker selection: prefer staying on the current track unless
                # it goes clearly silent, to prevent cross-talk bouncing.
                if faces[fidx] and not is_interjection:
                    if current_track_id is not None:
                        same_track = [
                            f for f in faces[fidx] if f["tidx"] == current_track_id
                        ]
                        # Level 100: Interruption Override
                        # If the other speaker interrupts loudly (> 0.75 score) and the current speaker is silent (< 0.4 score),
                        # override the minimum cut frames lock and switch immediately.
                        is_interruption_overriding = (
                            potential_best
                            and same_track
                            and potential_best["score"] > 0.75
                            and same_track[0]["score"] < 0.4
                        )
                        # Hold current speaker if we haven't spent enough frames on them yet
                        if (
                            same_track
                            and (
                                same_track[0]["score"] > ACTIVE_SPEAKER_THRESHOLD * 0.7
                                or frames_on_current_speaker < MIN_CUT_FRAMES
                            )
                            and not is_interruption_overriding
                        ):
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

                    # Level 100 zoom lock
                    if best.get("score", 0) > 0.75:
                        held_speaker_zoom = 0.145
                    else:
                        held_speaker_zoom = 0.115

                    frames_since_active = 0
                    target_cx = int(held_speaker_x * scale)
                elif held_speaker_x is not None:
                    # Hold the last active speaker indefinitely during pauses.
                    # This prevents the camera from awkwardly cutting to the empty center of the room.
                    frames_since_active += 1
                    frames_on_current_speaker += 1
                    target_cx = int(held_speaker_x * scale)

                    # Level 100 zoom decay after 0.5s of silence
                    if frames_since_active > 12:
                        held_speaker_zoom = 0.115
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

                    # If no speaker is actively tracked, hold the camera on the last known position
                    if target_cx is None:
                        if current_cx is not None:
                            target_cx = current_target_cx
                        else:
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
                    vout.write(bg)

                elif use_course_layout:
                    bg = np.zeros((1920, 1080, 3), dtype=np.uint8)
                    # 1. Scale and fit the main slide area on the top half.
                    scale_top = 1080.0 / img.shape[1]
                    if img.shape[0] * scale_top > 960:
                        scale_top = 960.0 / img.shape[0]
                    top_w = int(img.shape[1] * scale_top)
                    top_h = int(img.shape[0] * scale_top)

                    res_top = cv2.resize(img, (top_w, top_h), interpolation=cv2.INTER_AREA)
                    start_x_top = (1080 - top_w) // 2
                    start_y_top = (960 - top_h) // 2
                    bg[
                        start_y_top : start_y_top + top_h, start_x_top : start_x_top + top_w
                    ] = res_top

                    # 2. Render the face-tracked close-up of the presenter in the bottom half.
                    target_cx_course = None
                    target_cy_course = None
                    target_s_course = None

                    if best is not None:
                        target_cx_course = best["x"]
                        target_cy_course = best["y"]
                        target_s_course = best["s"]
                    elif fidx < len(faces) and len(faces[fidx]) > 0:
                        # Fallback to the largest face if no active speaker face is tracked
                        largest_face = max(faces[fidx], key=lambda x: x.get("s", 0))
                        target_cx_course = largest_face["x"]
                        target_cy_course = largest_face["y"]
                        target_s_course = largest_face["s"]

                    if target_cx_course is not None:
                        if current_cx_course is None:
                            current_cx_course = float(target_cx_course)
                            current_cy_course = float(target_cy_course)
                            current_s_course = float(target_s_course)
                            current_target_cx_course = float(target_cx_course)
                            current_target_cy_course = float(target_cy_course)
                            current_target_s_course = float(target_s_course)
                        else:
                            # 15px dead-zone on position shifts
                            COURSE_DEAD_ZONE = 15.0
                            if (
                                abs(target_cx_course - current_target_cx_course)
                                > COURSE_DEAD_ZONE
                            ):
                                current_target_cx_course = float(target_cx_course)
                            if (
                                abs(target_cy_course - current_target_cy_course)
                                > COURSE_DEAD_ZONE
                            ):
                                current_target_cy_course = float(target_cy_course)

                            # 10% dead-zone on scale shifts
                            if abs(target_s_course - current_target_s_course) > (
                                current_target_s_course * 0.10
                            ):
                                current_target_s_course = float(target_s_course)

                            # Slow smoothing: tripod feel. Snappy course pan: 0.12
                            COURSE_ALPHA = 0.12
                            current_cx_course += (
                                current_target_cx_course - current_cx_course
                            ) * COURSE_ALPHA
                            current_cy_course += (
                                current_target_cy_course - current_cy_course
                            ) * COURSE_ALPHA
                            current_s_course += (
                                current_target_s_course - current_s_course
                            ) * COURSE_ALPHA
                    else:
                        # Fallback to absolute center of video if no faces exist in the video segment at all
                        if current_cx_course is None:
                            current_cx_course = img.shape[1] / 2.0
                            current_cy_course = img.shape[0] / 2.0
                            current_s_course = img.shape[1] * 0.15  # assume 15% face width
                            current_target_cx_course = img.shape[1] / 2.0
                            current_target_cy_course = img.shape[0] / 2.0
                            current_target_s_course = img.shape[1] * 0.15

                    # We target a 20% face-to-frame ratio in a 1080x960 layout.
                    # Face size in crop should scale to 960 * 0.20 = 192px.
                    target_face_h = 960.0 * 0.20
                    scale_bottom = target_face_h / current_s_course

                    # Calculate corresponding crop size in original image space
                    crop_w = 1080.0 / scale_bottom
                    crop_h = 960.0 / scale_bottom

                    # Clamp crop sizes to image boundaries
                    crop_w = min(crop_w, img.shape[1])
                    crop_h = min(crop_h, img.shape[0])

                    # Keep exactly 1080:960 aspect ratio
                    if crop_w * 960.0 > crop_h * 1080.0:
                        crop_w = crop_h * (1080.0 / 960.0)
                    else:
                        crop_h = crop_w * (960.0 / 1080.0)

                    # Centered coordinates
                    x1 = current_cx_course - crop_w / 2.0
                    y1 = current_cy_course - crop_h / 2.0

                    # Clamp bounding box
                    x1 = max(0.0, min(x1, img.shape[1] - crop_w))
                    y1 = max(0.0, min(y1, img.shape[0] - crop_h))
                    x2 = x1 + crop_w
                    y2 = y1 + crop_h

                    # Crop and resize
                    crop_bottom = img[int(y1) : int(y2), int(x1) : int(x2)]
                    res_bottom = cv2.resize(
                        crop_bottom, (1080, 960), interpolation=cv2.INTER_AREA
                    )

                    # Paste in bottom half
                    bg[960:1920, 0:1080] = res_bottom

                    # Draw a clean 4px black divider line at y = 960
                    cv2.line(bg, (0, 960), (1080, 960), (0, 0, 0), 4)

                    vout.write(bg)

                elif use_split_screen:
                    # --- Vizard-style: independent face-focused crop per person ---
                    face_top = None
                    face_bottom = None

                    if fidx < len(faces) and len(faces[fidx]) >= 2:
                        largest_faces = sorted(
                            faces[fidx], key=lambda x: x.get("s", 0), reverse=True
                        )[:2]
                        # Left person → top half, right person → bottom half
                        sorted_lr = sorted(largest_faces, key=lambda x: x["x"])
                        face_top = sorted_lr[0]
                        face_bottom = sorted_lr[1]
                    elif fidx < len(faces) and len(faces[fidx]) == 1:
                        f = faces[fidx][0]
                        if f["x"] < img.shape[1] / 2.0:
                            face_top = f
                        else:
                            face_bottom = f

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

                    # We iterate over top (left speaker) and bottom (right speaker) slots
                    for is_top, y_start in [(True, 0), (False, 960)]:
                        if is_top:
                            sub_img = img[:, 0 : img_w // 2]
                            cx = split_cx_top
                            cy = split_cy_top
                            s = split_s_top
                            cx_offset = 0.0
                        else:
                            sub_img = img[:, img_w // 2 : img_w]
                            cx = split_cx_bottom
                            cy = split_cy_bottom
                            s = split_s_bottom
                            cx_offset = img_w / 2.0

                        sub_h, sub_w = sub_img.shape[:2]

                        # Fallback to center of the half-frame if face tracking is not available
                        if cx is None or s is None:
                            cx_rel = sub_w / 2.0
                            cy_rel = sub_h / 2.0
                            s = sub_w * 0.15
                        else:
                            cx_rel = cx - cx_offset
                            cy_rel = cy

                        # Ensure coordinates are within sub-image boundaries
                        cx_rel = max(0.0, min(cx_rel, float(sub_w)))
                        cy_rel = max(0.0, min(cy_rel, float(sub_h)))

                        # Determine crop size (target 1080:960 aspect ratio = 1.125)
                        # Face fills ~36% of 960px half (s=half-size, full=2s)
                        person_scale = (960.0 * 0.18) / max(s, 1.0)

                        desired_crop_w = 1080.0 / person_scale
                        desired_crop_h = 960.0 / person_scale

                        # Clamp crop size to the maximum allowed crop box inside the sub-image
                        crop_w = min(desired_crop_w, float(sub_w))
                        crop_h = crop_w / 1.125

                        # Position the crop box centering on face coordinates
                        x1 = cx_rel - crop_w / 2.0
                        y1 = cy_rel - crop_h * 0.38  # Face at 38% from top (rule of thirds)

                        # Clamp crop box coordinates to stay fully inside the sub-image
                        x1 = max(0.0, min(x1, sub_w - crop_w))
                        y1 = max(0.0, min(y1, sub_h - crop_h))

                        x2 = x1 + crop_w
                        y2 = y1 + crop_h

                        crop = sub_img[int(y1) : int(y2), int(x1) : int(x2)]
                        if crop.shape[0] > 0 and crop.shape[1] > 0:
                            resized = cv2.resize(
                                crop, (1080, 960), interpolation=cv2.INTER_AREA
                            )
                            final_frame[y_start : y_start + 960, 0:1080] = resized

                    vout.write(final_frame)
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
                        target_s = (
                            current_s_reframe
                            if current_s_reframe is not None
                            else virtual_w * 0.08
                        )
                    else:
                        target_cy = (
                            (held_speaker_y * scale)
                            if held_speaker_y is not None
                            else virtual_h / 2.0
                        )
                        target_s = (
                            (held_speaker_s * scale)
                            if held_speaker_s is not None
                            else virtual_w * 0.08
                        )

                    # Level 100: Scene cut hard reset (snap camera)
                    is_scene_start = fidx in scene_starts

                    # Initialize or hard cut on speaker switch or scene boundary (prevents panning animation across edit cuts)
                    if current_cx is None or speaker_switched or is_scene_start:
                        current_cx = float(target_cx)
                        current_target_cx = float(target_cx)
                        current_cy_reframe = float(target_cy)
                        current_target_cy_reframe = float(target_cy)
                        current_s_reframe = float(target_s)
                        current_target_s_reframe = float(target_s)

                    # Dead-zone on X
                    if target_cx - current_target_cx > DEAD_ZONE_PX:
                        current_target_cx = float(target_cx - DEAD_ZONE_PX)
                    elif current_target_cx - target_cx > DEAD_ZONE_PX:
                        current_target_cx = float(target_cx + DEAD_ZONE_PX)

                    # 15px dead-zone on Y-axis
                    DEAD_ZONE_Y = 15.0
                    if abs(target_cy - current_target_cy_reframe) > DEAD_ZONE_Y:
                        current_target_cy_reframe = float(target_cy)

                    # 10% dead-zone on scale shifts
                    if abs(target_s - current_target_s_reframe) > (
                        current_target_s_reframe * 0.10
                    ):
                        current_target_s_reframe = float(target_s)

                    # Level 1000: Adaptive Easing & Camera Stabilization Lock
                    dist_x = abs(current_target_cx - current_cx)
                    if dist_x < 15.0:
                        # Stabilization lock: completely lock camera to eliminate microscopic drift/jitter
                        adaptive_alpha = 0.0
                    else:
                        # Dynamic easing: slow, smooth corrections for small movements, snappy catch-up for large movements
                        adaptive_alpha = 0.02 + min((dist_x - 15.0) / 200.0, 1.0) * 0.10

                    if adaptive_alpha > 0.0:
                        current_cx += (current_target_cx - current_cx) * adaptive_alpha
                        current_cy_reframe += (
                            current_target_cy_reframe - current_cy_reframe
                        ) * (
                            adaptive_alpha * 0.5
                        )  # Dampen vertical movement by 50% for gimbal-like stability
                        current_s_reframe += (
                            current_target_s_reframe - current_s_reframe
                        ) * (
                            adaptive_alpha * 0.7
                        )  # Dampen scale shifts to avoid constant sizing changes

                    # Premium level 100: AI Reaction Zoom
                    # Locked to held_speaker_zoom to prevent single-frame zoom flickers when face drops
                    face_size_pct = (
                        held_speaker_zoom if held_speaker_zoom is not None else 0.115
                    )

                    person_scale = (1920.0 * face_size_pct) / max(current_s_reframe, 1.0)
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

                    # Face positioned ~33% from the top
                    x1_virtual = current_cx - crop_w / 2.0
                    y1_virtual = current_cy_reframe - crop_h * 0.33

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
                        vout.write(res)
                    else:
                        # Emergency fallback
                        res = cv2.resize(img, None, fx=scale, fy=scale)
                        tx = max(min(res.shape[1] // 2 - 540, res.shape[1] - 1080), 0)
                        vout.write(res[0:1920, tx : tx + 1080])

                    prev_target_cx = float(target_cx)
                else:
                    prev_target_cx = None
                    current_cx = None
                    # Fallback if no target is found but we aren't in split or letterbox
                    # Just render center of the original video
                    res = cv2.resize(img, None, fx=scale, fy=scale)
                    tx = max(min(res.shape[1] // 2 - 540, res.shape[1] - 1080), 0)
                    vout.write(res[0:1920, tx : tx + 1080])

        finally:
            if video_reader is not None:
                try:
                    video_reader.close()
                except Exception:
                    pass

        vout.release()

        import shutil

        return frame_layout

        shutil.move(temp_v, output_path)

    # ─────────────────────────────────────────────────────────────────
    #  Public endpoint
    # ─────────────────────────────────────────────────────────────────
    @modal.fastapi_endpoint(method="POST")
    def reframe(self, req: ReframeRequest):
        from pathlib import Path

        # --- Validate inputs ---
        validate_url(req.video_url, label="video_url")

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
            vurl = req.video_url
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
                seg_start = max(0.0, req.start_time - SEGMENT_DOWNLOAD_PAD_S)
                vurl = download_youtube_video(
                    vurl,
                    tmpdir,
                    start_time=req.start_time,
                    end_time=req.end_time,
                    max_height=720 if is_preview else 1080,
                    skip_probe=is_preview,  # Still skip format probe for preview to save ~4s
                )
                segment_offset = seg_start

                dl_size = os.path.getsize(vurl)
                logger.info(
                    "YouTube video downloaded to: %s (%.1f MB, segment_offset=%.1fs)",
                    vurl,
                    dl_size / (1024 * 1024),
                    segment_offset,
                )

                all_files = list(Path(tmpdir).iterdir())
                logger.info("Files in tmpdir after download (%d):", len(all_files))
                for f in all_files:
                    if f.is_file():
                        logger.info(
                            "  %s (%.1f MB)", f.name, f.stat().st_size / (1024 * 1024)
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
                    "-ss",
                    str(effective_start),
                    "-t",
                    str(duration_secs),
                    "-i",
                    vurl,
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
            tracks, scores, audio, pyf, pya, scene_bounds = self.get_tracks_and_scores(
                vurl,
                effective_start,
                duration_secs,
                tmpdir,
                fps=fps,
                crop_mode=req.crop_mode,
                audio_url=segment_audio,
                is_preview=is_preview,
            )
            logger.info(
                "Face tracking done in %.1fs, found %d tracks",
                time.time() - t0,
                len(tracks),
            )

            # 4. Render vertical
            crop_mode = req.crop_mode
            if crop_mode == "auto":
                crop_mode = self.classify_layout(
                    tracks,
                    scores,
                    video_info.get("width", 1920),
                    video_info.get("height", 1080),
                )
                logger.info("Auto-detected layout: %s", crop_mode)

            orig_name = f"orig_{uuid.uuid4()}.mp4"
            local_orig = os.path.join(tmpdir, orig_name)

            t1 = time.time()
            logger.info("Rendering vertical video at %s fps...", fps)
            frame_layout = self.render_vertical(
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

            # Use NVENC hardware encoder if available (5-10x faster than CPU libx264)
            video_codec = (
                ["h264_nvenc", "-preset", "p4", "-cq", "22"]
                if self.use_nvenc
                else [
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-crf",
                    "22",
                ]
            )

            mux_cmd = [
                "ffmpeg",
                "-y",
                "-i",
                local_orig,
                "-i",
                segment_audio,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                *video_codec,
                "-pix_fmt",
                "yuv420p",
                "-profile:v",
                "high",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                synced_output,
                "-loglevel",
                "panic",
            ]
            mux_result = subprocess.run(
                mux_cmd, capture_output=True, text=True, timeout=_FFMPEG_LONG_TIMEOUT_S
            )
            if mux_result.returncode != 0:
                raise RenderError(f"Audio mux failed: {mux_result.stderr[-500:]}")
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
                "crop_mode": crop_mode,
                "source_width": actual_w,
                "source_height": actual_h,
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

        validate_url(req.video_url, label="video_url")
        logger.info("=== BATCH REFRAME REQUEST === (%d clips)", len(req.clips))

        results = []

        with tempfile.TemporaryDirectory() as tmpdir:
            vurl = req.video_url
            is_preview = req.quality == "preview"

            # 1. Download from YouTube if needed (ONCE for all clips)
            segment_offset = 0.0
            global_start = min(c.start_time for c in req.clips)
            global_end = max(c.end_time for c in req.clips)

            if is_youtube_url(vurl):
                from ytdlp_helper import SEGMENT_DOWNLOAD_PAD_S

                logger.info(
                    "Downloading YouTube video ONCE for %d clips...", len(req.clips)
                )
                seg_start = max(0.0, global_start - SEGMENT_DOWNLOAD_PAD_S)
                vurl = download_youtube_video(
                    vurl,
                    tmpdir,
                    start_time=global_start,
                    end_time=global_end,
                    max_height=720 if is_preview else 1080,
                    skip_probe=is_preview,
                )
                segment_offset = seg_start
                logger.info(
                    "YouTube download complete (segment_offset=%.1fs)", segment_offset
                )

            # 2. Probe video info ONCE
            video_info = self.get_video_info(vurl)
            fps = video_info["fps"]
            actual_w = video_info.get("width", 1280)
            actual_h = video_info.get("height", 720)
            logger.info("Source: %sx%s @ %.1f fps", actual_w, actual_h, fps)

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

                # Run face tracking for this cluster
                t0 = time.time()
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
                    crop_mode="auto",
                    audio_url=cluster_audio,
                    is_preview=is_preview,
                )
                logger.info(
                    "Cluster %d tracking done in %.1fs, %d tracks",
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
                    try:
                        clip_start_rel = clip_req.start_time - cluster_start
                        clip_end_rel = clip_req.end_time - cluster_start
                        clip_duration = clip_end_rel - clip_start_rel

                        # Slice frames mathematically for this clip
                        start_frame = max(0, int(clip_start_rel * fps))
                        clip_frame_count = int(clip_duration * fps)
                        end_frame = start_frame + clip_frame_count

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
                            mask = (track_frames >= start_frame) & (
                                track_frames < end_frame
                            )
                            if not np.any(mask):
                                continue

                            indices = np.where(mask)[0]
                            new_track = {
                                "track": {
                                    "frame": track_frames[indices] - start_frame,
                                },
                                "proc_track": {
                                    "x": tr["proc_track"]["x"][indices],
                                    "y": tr["proc_track"]["y"][indices],
                                    "s": tr["proc_track"]["s"][indices],
                                },
                            }
                            sc = cluster_scores[tidx]
                            new_scores = (
                                sc[indices]
                                if len(sc) > len(indices)
                                else sc[indices[: len(sc)]]
                            )
                            clip_tracks.append(new_track)
                            clip_scores.append(new_scores)

                        # Classify layout for this clip
                        crop_mode = clip_req.crop_mode
                        if crop_mode == "auto":
                            crop_mode = self.classify_layout(
                                clip_tracks,
                                clip_scores,
                                actual_w,
                                actual_h,
                            )
                        logger.info("Clip %s layout: %s", clip_id, crop_mode)

                        # Slice scene bounds for this clip
                        clip_scene_bounds = []
                        for sf, ef in cluster_scene_bounds:
                            adj_sf = max(0, sf - start_frame)
                            adj_ef = min(clip_frame_count, ef - start_frame)
                            if adj_ef > adj_sf:
                                clip_scene_bounds.append((adj_sf, adj_ef))
                        if not clip_scene_bounds:
                            clip_scene_bounds = [(0, clip_frame_count)]

                        # Render this clip
                        orig_name = f"orig_{uuid.uuid4()}.mp4"
                        local_orig = os.path.join(tmpdir, orig_name)

                        t1 = time.time()
                        frame_layout = self.render_vertical(
                            clip_tracks,
                            clip_scores,
                            None,
                            pya,
                            local_orig,
                            duration=clip_duration,
                            fps=fps,
                            crop_mode=crop_mode,
                            scene_bounds=clip_scene_bounds,
                            video_path=vurl,
                            start_time_in_video=effective_cluster_start + clip_start_rel,
                        )

                        if clip_req.transcript:
                            clip_req.transcript = annotate_transcript_layout(
                                clip_req.transcript, frame_layout, crop_mode, fps
                            )


                        # Extract clip audio and mux
                        clip_audio = os.path.join(
                            cluster_workdir, f"clip_audio_{clip_id}.aac"
                        )
                        subprocess.run(
                            [
                                "ffmpeg",
                                "-y",
                                "-ss",
                                str(clip_start_rel),
                                "-t",
                                str(clip_duration),
                                "-i",
                                cluster_audio,
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
                        video_codec = (
                            ["h264_nvenc", "-preset", "p4", "-cq", "22"]
                            if self.use_nvenc
                            else ["libx264", "-preset", "ultrafast", "-crf", "22"]
                        )
                        subprocess.run(
                            [
                                "ffmpeg",
                                "-y",
                                "-i",
                                local_orig,
                                "-i",
                                clip_audio,
                                "-map",
                                "0:v:0",
                                "-map",
                                "1:a:0",
                                "-c:v",
                                *video_codec,
                                "-pix_fmt",
                                "yuv420p",
                                "-profile:v",
                                "high",
                                "-c:a",
                                "aac",
                                "-b:a",
                                "128k",
                                "-movflags",
                                "+faststart",
                                synced,
                                "-loglevel",
                                "panic",
                            ],
                            check=True,
                            timeout=_FFMPEG_LONG_TIMEOUT_S,
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
                                "actual_w": actual_w,
                                "actual_h": actual_h,
                            }
                        )
                    except Exception as e:
                        logger.error(
                            "Failed to process clip %s: %s", clip_id, e, exc_info=True
                        )
                        cluster_results.append(
                            {
                                "clip_id": clip_id,
                                "success": False,
                                "error": str(e),
                            }
                        )

                # Free cluster memory after all clips in this cluster are processed
                if (
                    hasattr(cluster_frames, "_mmap")
                    and cluster_frames._mmap is not None
                ):
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
                            "crop_mode": crop_mode,
                            "source_width": actual_w,
                            "source_height": actual_h,
                            "transcript": clip_req.transcript,
                        }
                    else:
                        return {
                            "clip_id": clip_id,
                            "success": False,
                            "error": error_msg,
                        }

                # Limit concurrency to min(6, len(all_deferred)) to balance upload bandwidth and CPU during burns
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

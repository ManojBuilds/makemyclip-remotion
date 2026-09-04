"""Full-Video Analysis Modal Service.

Runs face detection (5fps), face tracking, active speaker detection (TalkNet),
and scene detection across an entire video in 10-minute parallel chunks.
Saves a structured `analysis.json` to R2 that serves as the reusable source
of truth for all future rendering tasks.
"""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import subprocess
import tempfile
import time
import uuid

import modal
import numpy as np

from config import RECOMMENDED_GPU, ai_secret, app, image, youtube_cookies_secret
from models import AnalyzeVideoRequest, AnalyzeVideoResponse
from r2_storage import upload_to_r2
from utils import StageTimer, is_youtube_url, validate_url
from ytdlp_helper import download_youtube_video

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import torch
except ImportError:
    torch = None

logger = logging.getLogger("makemyclip.analyzer")

TARGET_ANALYZER_GPUS = 8       # Cap single video analysis to 8 GPUs max (leaves 2 free out of 10 GPU quota)
MIN_CHUNK_DURATION_S = 120.0   # 2 minutes minimum per chunk
MAX_CHUNK_DURATION_S = 600.0   # 10 minutes maximum per chunk
DETECT_SKIP_FRAMES = 5         # 5fps detection keyframing at 25fps source


def calculate_optimal_chunk_duration(duration_secs: float, target_gpus: int = TARGET_ANALYZER_GPUS) -> tuple[float, int]:
    """Calculate optimal chunk duration and chunk count targeting up to target_gpus concurrently."""
    if duration_secs <= 0:
        return MIN_CHUNK_DURATION_S, 1
    raw_chunk = duration_secs / target_gpus
    chunk_dur = max(MIN_CHUNK_DURATION_S, min(MAX_CHUNK_DURATION_S, raw_chunk))
    num_chunks = max(1, math.ceil(duration_secs / chunk_dur))
    return chunk_dur, num_chunks


def serialize_tracks_and_scores(
    tracks: list,
    scores: list,
    fps: float,
    width: float | None = None,
    height: float | None = None,
) -> list[dict]:
    """Convert numpy arrays inside tracks and scores into JSON-serializable dictionaries (normalized 0.0-1.0 float space)."""
    serialized = []
    for tidx, tr in enumerate(tracks):
        track_frames = [int(f) for f in tr["track"]["frame"]]
        bboxes = tr["track"]["bbox"].tolist() if isinstance(tr["track"]["bbox"], np.ndarray) else tr["track"]["bbox"]
        proc_x = tr["proc_track"]["x"].tolist() if isinstance(tr["proc_track"]["x"], np.ndarray) else tr["proc_track"]["x"]
        proc_y = tr["proc_track"]["y"].tolist() if isinstance(tr["proc_track"]["y"], np.ndarray) else tr["proc_track"]["y"]
        proc_s = tr["proc_track"]["s"].tolist() if isinstance(tr["proc_track"]["s"], np.ndarray) else tr["proc_track"]["s"]

        if width and height and width > 0 and height > 0:
            norm_proc_x = [round(float(x) / width, 5) for x in proc_x]
            norm_proc_y = [round(float(y) / height, 5) for y in proc_y]
            norm_proc_s = [round(float(s) / height, 5) for s in proc_s]
            norm_bboxes = [
                [
                    round(float(b[0]) / width, 5),
                    round(float(b[1]) / height, 5),
                    round(float(b[2]) / width, 5),
                    round(float(b[3]) / height, 5),
                ]
                for b in bboxes
            ]
        else:
            norm_proc_x = [round(float(x), 3) for x in proc_x]
            norm_proc_y = [round(float(y), 3) for y in proc_y]
            norm_proc_s = [round(float(s), 3) for s in proc_s]
            norm_bboxes = [[round(float(val), 3) for val in b] for b in bboxes]

        sc = scores[tidx]
        if isinstance(sc, np.ndarray):
            sc = sc.tolist()

        serialized.append({
            "track_id": tidx,
            "frames": track_frames,
            "bboxes": norm_bboxes,
            "proc_track": {
                "x": norm_proc_x,
                "y": norm_proc_y,
                "s": norm_proc_s,
            },
            "scores": [round(float(s), 3) for s in sc],
        })
    return serialized


def stitch_chunk_tracks(chunk_results: list[dict], fps: float) -> tuple[list[dict], list[list[float]]]:
    """Stitch track segments from adjacent 10-minute chunks across chunk boundaries."""
    global_tracks = []
    global_scores = []
    next_global_id = 0

    for chunk_idx, chunk_res in enumerate(chunk_results):
        chunk_start_frame = int(chunk_res["start_time"] * fps)
        local_tracks = chunk_res["tracks"]

        for tr in local_tracks:
            # Shift frames to global timeline
            global_frames = [f + chunk_start_frame for f in tr["frames"]]
            x0 = tr["proc_track"]["x"][0]
            y0 = tr["proc_track"]["y"][0]

            best_match_idx = -1
            best_dist = float("inf")

            if global_tracks and chunk_idx > 0:
                # Search candidate tracks ending within 1 second of current track start
                for g_idx, g_tr in enumerate(global_tracks):
                    last_frame = g_tr["track"]["frame"][-1]
                    frame_gap = global_frames[0] - last_frame

                    if 0 <= frame_gap <= int(fps):
                        last_x = g_tr["proc_track"]["x"][-1]
                        last_y = g_tr["proc_track"]["y"][-1]
                        dx = abs(x0 - last_x)
                        dy = abs(y0 - last_y)

                        # Threshold on normalized 0.0-1.0 coordinate space (12% width, 15% height)
                        if dx < 0.12 and dy < 0.15:
                            dist = math.hypot(dx, dy)
                            if dist < best_dist:
                                best_dist = dist
                                best_match_idx = g_idx

            if best_match_idx != -1:
                # Append to best matching existing track
                target_tr = global_tracks[best_match_idx]
                target_tr["track"]["frame"].extend(global_frames)
                target_tr["track"]["bbox"].extend(tr["bboxes"])
                target_tr["proc_track"]["x"].extend(tr["proc_track"]["x"])
                target_tr["proc_track"]["y"].extend(tr["proc_track"]["y"])
                target_tr["proc_track"]["s"].extend(tr["proc_track"]["s"])
                global_scores[best_match_idx].extend(tr["scores"])
            else:
                # Register as a new global track
                global_tracks.append({
                    "track_id": next_global_id,
                    "track": {
                        "frame": global_frames,
                        "bbox": tr["bboxes"],
                    },
                    "proc_track": {
                        "x": tr["proc_track"]["x"],
                        "y": tr["proc_track"]["y"],
                        "s": tr["proc_track"]["s"],
                    },
                })
                global_scores.append(tr["scores"])
                next_global_id += 1

    # --- OpusClip Feature: Persistent Speaker Clustering ---
    # Assign persistent speaker_id (e.g. Speaker 0 = Host, Speaker 1 = Guest) based on mean X position
    columns = []
    for g_tr in global_tracks:
        mean_x = float(np.mean(g_tr["proc_track"]["x"]))
        placed = False
        for col in columns:
            if abs(col["mean_x"] - mean_x) < 0.15:
                col["tracks"].append(g_tr)
                col["mean_x"] = float(np.mean([np.mean(t["proc_track"]["x"]) for t in col["tracks"]]))
                placed = True
                break
        if not placed:
            columns.append({"mean_x": mean_x, "tracks": [g_tr]})

    columns.sort(key=lambda c: c["mean_x"])
    for speaker_id, col in enumerate(columns):
        for g_tr in col["tracks"]:
            g_tr["speaker_id"] = speaker_id

    return global_tracks, global_scores


@app.cls(
    image=image,
    gpu=RECOMMENDED_GPU,
    timeout=1800,
    secrets=[ai_secret, youtube_cookies_secret],
    max_containers=10,
)
class VideoAnalyzer:
    @modal.enter()
    def setup(self):
        """Load S3FD face detector and TalkNet ASD model onto GPU."""
        import sys
        os.chdir("/root/asd")
        if "/root/asd" not in sys.path:
            sys.path.append("/root/asd")

        from ASD import ASD
        from talknce import create_talknce_engine
        from model.faceDetector.s3fd import S3FD

        logger.info("Initializing S3FD Face Detector, TalkNet & TalkNCE ASD models...")
        self.DET = S3FD(device="cuda")
        self.ASD_MODEL = ASD()
        self.ASD_MODEL.loadParameters("/root/asd/weight/finetuning_TalkSet.model")
        self.ASD_MODEL.eval()
        self.ASD_MODEL.cuda()

        self.TALKNCE_MODEL = create_talknce_engine(
            weight_path="/root/asd/weight/finetuning_TalkSet.model",
            device="cuda" if torch.cuda.is_available() else "cpu",
        )

        from reframer import AIReframe
        self.use_nvenc = AIReframe._probe_nvenc()
        logger.info("Analyzer models loaded successfully (NVENC=%s, TalkNCE=Active).", self.use_nvenc)

    @modal.method()
    def analyze_chunk(
        self,
        video_url: str,
        start_time: float,
        duration: float,
        chunk_idx: int,
        total_chunks: int,
        fps: float = 25.0,
        detect_skip: int = 5,
    ) -> dict:
        """Process a single 10-minute chunk at 5fps detection rate."""
        from reframer import AIReframe

        logger.info(
            "=== Processing Analysis Chunk %d/%d (%.1fs - %.1fs) ===",
            chunk_idx + 1,
            total_chunks,
            start_time,
            start_time + duration,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            v_input = video_url
            segment_offset = 0.0
            if is_youtube_url(video_url):
                v_input, segment_offset = download_youtube_video(
                    video_url,
                    tmpdir,
                    start_time=start_time,
                    end_time=start_time + duration,
                    max_height=360,
                    skip_probe=True,
                )
            else:
                # Direct video URL: Download & downscale 360p chunk segment + extract audio
                # in a single FFmpeg pass (saves one full HTTP seek + decode pass)
                local_proxy = os.path.join(tmpdir, f"chunk_{chunk_idx}_360p.mp4")
                chunk_audio = os.path.join(tmpdir, "chunk_audio.aac")
                logger.info(
                    "Fetching 360p proxy + audio for direct URL (%.1fs - %.1fs) in single pass...",
                    start_time,
                    start_time + duration,
                )
                dl_cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start_time),
                    "-i", video_url,
                    "-t", str(duration),
                    "-map", "0:v:0", "-vf", "scale=-2:360",
                    "-c:v", "libx264", "-preset", "ultrafast",
                    local_proxy,
                    "-map", "0:a:0?",
                    "-c:a", "aac", "-b:a", "128k",
                    chunk_audio,
                ]
                res = subprocess.run(dl_cmd, capture_output=True, text=True, timeout=300)
                if res.returncode == 0 and os.path.exists(local_proxy) and os.path.getsize(local_proxy) > 0:
                    v_input = local_proxy
                    segment_offset = start_time
                    logger.info("✅ Direct URL 360p proxy + audio downloaded")
                else:
                    logger.warning("Direct URL combined download failed, falling back to streaming: %s", res.stderr)
                    v_input = video_url
                    segment_offset = 0.0

            reframer = AIReframe()
            # Inject detector and ASD models to reuse warm container state
            reframer.DET = self.DET
            reframer.ASD_MODEL = self.ASD_MODEL
            reframer.TALKNCE_MODEL = getattr(self, "TALKNCE_MODEL", None)
            reframer.use_nvenc = getattr(self, "use_nvenc", False)

            # Probe chunk video dimensions for normalized coordinate calculation
            chunk_info = reframer.get_video_info(v_input)
            chunk_w = float(chunk_info.get("width", 640))
            chunk_h = float(chunk_info.get("height", 360))

            eff_start = start_time - segment_offset

            # Extract chunk audio (unless already extracted in combined download above)
            if not is_youtube_url(video_url) and os.path.exists(os.path.join(tmpdir, "chunk_audio.aac")) and os.path.getsize(os.path.join(tmpdir, "chunk_audio.aac")) > 0:
                chunk_audio = os.path.join(tmpdir, "chunk_audio.aac")
                logger.info("Using audio from combined download pass")
            else:
                chunk_audio = os.path.join(tmpdir, "chunk_audio.aac")
                ffmpeg_cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(eff_start),
                    "-i", v_input,
                    "-t", str(duration),
                    "-vn", "-c:a", "aac", "-b:a", "192k",
                    chunk_audio,
                ]
                res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=300)
                if res.returncode != 0:
                    logger.warning("FFmpeg chunk audio extraction failed (video may be muted). Generating silent dummy audio: %s", res.stderr)
                    silent_cmd = [
                        "ffmpeg", "-y",
                        "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
                        "-t", str(duration),
                        "-c:a", "aac", "-b:a", "128k",
                        chunk_audio,
                    ]
                    subprocess.run(silent_cmd, capture_output=True, text=True, timeout=60)

            # Perform face tracking + TalkNet ASD on chunk
            tracks, scores, _, _, _, scene_bounds = reframer.get_tracks_and_scores(
                video_url=v_input,
                start_time=eff_start,
                duration=duration,
                work_dir=tmpdir,
                fps=fps,
                audio_url=chunk_audio,
                detect_skip=detect_skip,
            )

            serialized_tracks = serialize_tracks_and_scores(tracks, scores, fps, width=chunk_w, height=chunk_h)

            return {
                "chunk_idx": chunk_idx,
                "start_time": start_time,
                "duration": duration,
                "tracks": serialized_tracks,
                "scene_bounds": scene_bounds,
            }

    @modal.method()
    def run_full_analysis(self, req_dict: dict) -> dict:
        """Internal heavy worker: runs full video analysis across parallel GPU chunks."""
        vurl = validate_url(req_dict["video_url"], label="video_url")
        project_id = req_dict["project_id"]
        req_duration = req_dict.get("duration")
        req_start_time = req_dict.get("start_time")
        req_end_time = req_dict.get("end_time")
        detect_skip = req_dict.get("detect_skip", DETECT_SKIP_FRAMES)
        req_chunk_duration = req_dict.get("chunk_duration", 600.0)

        logger.info("=== RUNNING FULL VIDEO ANALYSIS ===")
        logger.info("project_id: %s, start_time: %s, end_time: %s, duration: %s", project_id, req_start_time, req_end_time, req_duration)

        with tempfile.TemporaryDirectory() as tmpdir:
            fps = 25.0

            if is_youtube_url(vurl):
                from ytdlp_helper import get_youtube_info
                info_dict = get_youtube_info(vurl)
                full_duration = info_dict.get("duration") or (req_duration or 300.0)
                fps = info_dict.get("fps") or 25.0
                width = info_dict.get("width") or 1280
                height = info_dict.get("height") or 720
            else:
                from reframer import AIReframe
                reframer = AIReframe()
                info = reframer.get_video_info(vurl)
                fps = info.get("fps", 25.0)
                width = info.get("width", 1920)
                height = info.get("height", 1080)
                full_duration = info.get("duration") or (req_duration or 300.0)

            # Check if start_time / end_time range is specified
            start_sec = req_start_time if req_start_time is not None else 0.0
            if req_end_time is not None:
                end_sec = min(req_end_time, full_duration)
            elif req_duration is not None:
                end_sec = min(start_sec + req_duration, full_duration)
            else:
                end_sec = full_duration

            duration_secs = max(1.0, end_sec - start_sec)

            # Dynamically calculate chunk parameters targeting up to 8 GPUs
            if req_chunk_duration and req_chunk_duration != 600.0:
                chunk_duration = req_chunk_duration
                num_chunks = max(1, math.ceil(duration_secs / chunk_duration))
            else:
                chunk_duration, num_chunks = calculate_optimal_chunk_duration(duration_secs)

            logger.info(
                "Segment selected: start=%.1fs, end=%.1fs (duration=%.1fs), chunk_duration=%.1fs, num_chunks=%d",
                start_sec, end_sec, duration_secs, chunk_duration, num_chunks
            )

            chunk_tasks = []
            for idx in range(num_chunks):
                c_start = start_sec + idx * chunk_duration
                c_dur = min(chunk_duration, end_sec - c_start)
                chunk_tasks.append((vurl, c_start, c_dur, idx, num_chunks, fps, detect_skip))

            logger.info("Launching %d parallel chunk jobs via starmap (up to 8 GPUs)...", num_chunks)
            t0 = time.time()
            chunk_results = list(self.analyze_chunk.starmap(chunk_tasks))
            elapsed_tracking = time.time() - t0
            logger.info("All %d chunk tracking jobs finished in %.1fs!", num_chunks, elapsed_tracking)

            # Sort chunks by start time
            chunk_results.sort(key=lambda c: c["chunk_idx"])

            # Stitch tracks across chunk boundaries
            global_tracks, global_scores = stitch_chunk_tracks(chunk_results, fps)

            # Extract global scene boundaries and classify layout per-scene (OpusClip style)
            from layout_classifier import classify_layout
            global_scene_bounds = []
            scene_layouts = []

            # Pre-convert track data to numpy once (avoids N_scenes × N_tracks redundant conversions)
            _track_frames = [np.array(g_tr["track"]["frame"]) for g_tr in global_tracks]
            _track_proc_x = [np.array(g_tr["proc_track"]["x"]) for g_tr in global_tracks]
            _track_proc_y = [np.array(g_tr["proc_track"]["y"]) for g_tr in global_tracks]
            _track_proc_s = [np.array(g_tr["proc_track"]["s"]) for g_tr in global_tracks]
            _track_scores = [np.array(g_sc) for g_sc in global_scores]

            for c_res in chunk_results:
                offset_frame = int(c_res["start_time"] * fps)
                for sf, ef in c_res["scene_bounds"]:
                    global_sf = sf + offset_frame
                    global_ef = ef + offset_frame
                    global_scene_bounds.append((global_sf, global_ef))

                    scene_tracks = []
                    scene_scores = []
                    for frames, px, py, ps, sc in zip(
                        _track_frames, _track_proc_x, _track_proc_y, _track_proc_s, _track_scores
                    ):
                        mask = (frames >= global_sf) & (frames <= global_ef)
                        if np.any(mask):
                            scene_tracks.append({
                                "track": {"frame": frames[mask]},
                                "proc_track": {
                                    "x": px[mask],
                                    "y": py[mask],
                                    "s": ps[mask],
                                },
                            })
                            scene_scores.append(sc[mask])

                    scene_layout = classify_layout(scene_tracks, scene_scores, int(width), int(height))
                    scene_layouts.append({
                        "start_frame": global_sf,
                        "end_frame": global_ef,
                        "recommended_layout": scene_layout,
                    })

            # Extract track positions for spatial layout detection
            face_positions = []
            for px, py, ps in zip(_track_proc_x, _track_proc_y, _track_proc_s):
                if len(px) > 0:
                    mean_x = float(np.mean(px))
                    mean_y = float(np.mean(py))
                    mean_s = float(np.mean(ps))
                    norm_x = mean_x / float(width) if mean_x > 1.0 else mean_x
                    norm_y = mean_y / float(height) if mean_y > 1.0 else mean_y
                    norm_s = mean_s / float(height) if mean_s > 1.0 else mean_s
                    face_positions.append({"x": norm_x, "y": norm_y, "s": norm_s})

            # Run global heuristic content classification
            from content_classifier import classify_content
            content_classification = classify_content(
                video_path=vurl,
                width=int(width),
                height=int(height),
                fps=float(fps),
                duration=float(duration_secs),
                start_time=float(start_sec),
                known_face_count=len(global_tracks),
                face_positions=face_positions,
            )
            logger.info(
                "Global content classification: type=%s, confidence=%.2f, recommended_crop_mode=%s",
                content_classification.content_type,
                content_classification.confidence,
                content_classification.recommended_crop_mode,
            )

            if content_classification.recommended_crop_mode in ("screencast", "presentation", "gaming", "panel"):
                for sl in scene_layouts:
                    if sl["recommended_layout"] == "reframe":
                        sl["recommended_layout"] = content_classification.recommended_crop_mode

            # Build comprehensive analysis object
            analysis_data = {
                "version": "1.1",
                "project_id": project_id,
                "video_info": {
                    "width": width,
                    "height": height,
                    "fps": fps,
                    "duration_s": round(duration_secs, 2),
                    "total_frames": int(duration_secs * fps),
                },
                "content_classification": {
                    "content_type": content_classification.content_type,
                    "confidence": content_classification.confidence,
                    "recommended_crop_mode": content_classification.recommended_crop_mode,
                    "skip_face_tracking": content_classification.skip_face_tracking,
                },
                "tracking_summary": {
                    "detect_skip": detect_skip,
                    "target_fps": 5.0,
                    "num_tracks": len(global_tracks),
                    "tracking_time_s": round(elapsed_tracking, 2),
                    "asd_engine": "TalkNCE",
                },
                "scene_bounds": global_scene_bounds,
                "scene_layouts": scene_layouts,
                "tracks": serialize_tracks_and_scores(global_tracks, global_scores, fps),
            }
            # Save and upload analysis.json to R2
            local_analysis_file = os.path.join(tmpdir, f"analysis_{project_id}.json")
            with open(local_analysis_file, "w") as f:
                json.dump(analysis_data, f)

            r2_key = f"analysis/{project_id}.json"
            analysis_url = upload_to_r2(local_analysis_file, r2_key)

            logger.info("✅ Analysis complete! Saved to R2: %s", analysis_url)

            return {
                "success": True,
                "project_id": project_id,
                "analysis_url": analysis_url,
                "total_frames": int(duration_secs * fps),
                "num_tracks": len(global_tracks),
                "duration_secs": round(duration_secs, 2),
            }

    @modal.fastapi_endpoint(method="POST")
    def submit(self, req: AnalyzeVideoRequest):
        """Asynchronous submission endpoint: spawns video analysis job on GPU and returns call_id immediately."""
        vurl = validate_url(req.video_url, label="video_url")
        logger.info("=== VIDEO ANALYSIS SUBMIT (ASYNC) ===")
        logger.info("project_id: %s, duration: %s", req.project_id, req.duration)

        payload = req.model_dump()
        payload["video_url"] = vurl
        call = self.run_full_analysis.spawn(payload)
        logger.info("Spawned analysis job call_id=%s for project_id=%s", call.object_id, req.project_id)

        return {
            "success": True,
            "call_id": call.object_id,
            "project_id": req.project_id,
            "status": "processing",
        }

    @modal.fastapi_endpoint(method="GET")
    def status(self, call_id: str, project_id: str = ""):
        """Non-blocking status poll endpoint: checks FunctionCall status or R2 artifact."""
        from modal.functions import FunctionCall
        import urllib.request

        if not call_id:
            return {"status": "error", "error": "call_id query parameter is required"}

        # 1. Check FunctionCall status
        try:
            call = FunctionCall.from_id(call_id)
            try:
                res = call.get(timeout=0)
                return {
                    "status": "completed",
                    "success": True,
                    "call_id": call_id,
                    "project_id": project_id,
                    "analysis_url": res.get("analysis_url") if isinstance(res, dict) else None,
                    "result": res,
                }
            except TimeoutError:
                pass
        except Exception as exc:
            logger.warning("Error polling FunctionCall %s: %s", call_id, exc)
            return {
                "status": "error",
                "success": False,
                "call_id": call_id,
                "project_id": project_id,
                "error": str(exc),
            }

        # 2. Safety fallback: check if analysis_{project_id}.json already exists in R2
        if project_id and os.environ.get("R2_PUBLIC_URL"):
            r2_url = f"{os.environ['R2_PUBLIC_URL']}/analysis/{project_id}.json"
            try:
                req = urllib.request.Request(r2_url, method="HEAD")
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if resp.status == 200:
                        return {
                            "status": "completed",
                            "success": True,
                            "call_id": call_id,
                            "project_id": project_id,
                            "analysis_url": r2_url,
                        }
            except Exception:
                pass

        return {
            "status": "processing",
            "call_id": call_id,
            "project_id": project_id,
        }

    @modal.fastapi_endpoint(method="POST")
    def analyze(self, req: AnalyzeVideoRequest):
        """Unified analysis endpoint: runs asynchronously if async_mode=True, else synchronously."""
        if getattr(req, "async_mode", False):
            return self.submit(req)
        return self.run_full_analysis(req.model_dump())

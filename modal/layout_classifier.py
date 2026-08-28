"""Layout Classifier for AI Reframer.

Analyzes detected face tracks, ASD speaker scores, and stage geometry to determine
the optimal layout mode:
- "reframe": Single speaker pan-and-zoom vertical crop
- "split": Dynamic 2-speaker split-screen layout
- "letterbox": Blurred background letterbox card
"""

from __future__ import annotations

import logging
import numpy as np

logger = logging.getLogger("makemyclip.layout_classifier")


def is_valid_face_track(tr, sc, frame_height: float = 2160.0) -> tuple[bool, float, float, float, float]:
    """Evaluate if a face track is valid/real (not background noise or fake face).

    Returns tuple: (is_valid, mean_score, max_score, mean_size_px, dur_frames)
    """
    proc_x = np.array(tr["proc_track"]["x"], dtype=float)
    proc_y = np.array(tr["proc_track"]["y"], dtype=float)
    proc_s = np.array(tr["proc_track"]["s"], dtype=float)
    dur = len(proc_x)

    if dur < 4:
        return False, 0.0, 0.0, 0.0, float(dur)

    scores = np.array(sc[:dur]) if len(sc) >= dur else np.pad(sc, (0, max(0, dur - len(sc))))
    mean_sc = float(np.mean(scores)) if len(scores) > 0 else 0.0
    max_sc = float(np.max(scores)) if len(scores) > 0 else 0.0
    mean_s = float(np.mean(proc_s)) if len(proc_s) > 0 else 0.0

    # Face size check: handle both normalized (0.0-1.0) and pixel scale
    s_norm = mean_s / frame_height if mean_s > 1.0 else mean_s
    if s_norm < 0.005:  # Ignore tiny artifacts <0.5% of height
        return False, mean_sc, max_sc, mean_s, float(dur)

    # Face variance check: motionless poster check (only reject if variance is essentially 0 AND ASD score is near 0)
    var_x = float(np.var(proc_x))
    var_y = float(np.var(proc_y))
    if var_x < 1e-7 and var_y < 1e-7 and max_sc < 0.05:
        return False, mean_sc, max_sc, mean_s, float(dur)

    return True, mean_sc, max_sc, mean_s, float(dur)


def classify_layout(tracks: list, scores: list, width: int, height: int) -> str:
    """Analyze face tracks and determine the optimal layout mode globally."""
    if not tracks:
        return "letterbox"

    valid_tracks = []
    total_max_frame = 0
    for tidx, tr in enumerate(tracks):
        sc = scores[tidx] if tidx < len(scores) else []
        is_valid, _, _, mean_s, dur = is_valid_face_track(tr, sc, frame_height=float(height))
        if is_valid:
            valid_tracks.append((tidx, tr))
            frames = tr.get("track", {}).get("frame", []) if isinstance(tr.get("track"), dict) else tr.get("proc_track", {}).get("frame", [])
            if len(frames) > 0:
                total_max_frame = max(total_max_frame, int(np.max(frames)))

    if not valid_tracks:
        return "letterbox"

    # Check for Corner Facecam (Gaming / Screencast with streamer overlay)
    # A corner facecam is a small face (<= 25% frame height) located near the corners (x < 30% or x > 70%, and y < 35% or y > 65%)
    for tidx, tr in valid_tracks:
        mean_x = float(np.mean(tr["proc_track"]["x"]))
        mean_y = float(np.mean(tr["proc_track"]["y"]))
        mean_s = float(np.mean(tr["proc_track"]["s"]))
        norm_x = mean_x / float(width) if mean_x > 1.0 else mean_x
        norm_y = mean_y / float(height) if mean_y > 1.0 else mean_y
        norm_s = mean_s / float(height) if mean_s > 1.0 else mean_s

        if norm_s <= 0.25 and (norm_x < 0.30 or norm_x > 0.70) and (norm_y < 0.35 or norm_y > 0.65):
            logger.info("Classified layout as GAMING (detected corner facecam streamer overlay at x=%.2f, y=%.2f, s=%.2f)", norm_x, norm_y, norm_s)
            return "gaming"

    # Build a per-frame mapping of simultaneous face X positions
    frame_faces: dict[int, list[float]] = {}
    for tidx, tr in valid_tracks:
        frames = tr.get("track", {}).get("frame", []) if isinstance(tr.get("track"), dict) else tr.get("proc_track", {}).get("frame", [])
        xs = tr.get("proc_track", {}).get("x", [])
        f_list = frames.tolist() if hasattr(frames, "tolist") else list(frames)
        x_list = xs.tolist() if hasattr(xs, "tolist") else list(xs)
        for f_val, x_val in zip(f_list, x_list):
            f_int = int(f_val)
            norm_x = float(x_val) / float(width) if float(x_val) > 1.0 else float(x_val)
            frame_faces.setdefault(f_int, []).append(norm_x)

    # For a genuine 2-speaker split screen (e.g. podcast / interview):
    # 1. We must have >= 2 distinct simultaneous face tracks separated by >= 25% screen width.
    # 2. Both tracks must have valid human face motion and size.
    # 3. There must be active speech/dialogue across the tracks (not just background audience or lighting glare).
    simultaneous_distant_frames = 0
    for f_int, x_coords in frame_faces.items():
        if len(x_coords) >= 2:
            # Check if any pair is separated by at least 25% of the screen width
            has_distant_pair = False
            for i in range(len(x_coords)):
                for j in range(i + 1, len(x_coords)):
                    if abs(x_coords[i] - x_coords[j]) >= 0.25:
                        has_distant_pair = True
                        break
                if has_distant_pair:
                    break
            if has_distant_pair:
                simultaneous_distant_frames += 1

    # Check if there are at least two distinct tracks with speaking/active scores
    active_tracks_count = 0
    for tidx, tr in valid_tracks:
        sc = scores[tidx] if tidx < len(scores) else []
        if len(sc) > 0 and float(np.max(sc)) > 0.15:
            active_tracks_count += 1

    min_required_split_frames = max(45, int(total_max_frame * 0.40)) if total_max_frame > 0 else 45
    logger.info(
        "Layout evaluation: %d frames with >=2 distant simultaneous faces (required=%d, active_speaking_tracks=%d)",
        simultaneous_distant_frames,
        min_required_split_frames,
        active_tracks_count,
    )

    # Only choose SPLIT if we have >= 2 active speaking people who co-occur across the screen
    if simultaneous_distant_frames >= min_required_split_frames and active_tracks_count >= 2:
        logger.info("Classified layout as SPLIT (two simultaneous active speakers)")
        return "split"

    logger.info("Classified layout as REFRAME (single solo speaker / stage performer)")
    return "reframe"


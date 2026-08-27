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
    for tidx, tr in enumerate(tracks):
        sc = scores[tidx] if tidx < len(scores) else []
        is_valid, _, _, _, _ = is_valid_face_track(tr, sc, frame_height=float(height))
        if is_valid:
            valid_tracks.append((tidx, tr))

    if not valid_tracks:
        return "letterbox"

    # Cluster tracks horizontally into columns (speakers)
    columns = []
    for tidx, tr in valid_tracks:
        x_arr = np.array(tr["proc_track"]["x"], dtype=float)
        mu_x = float(np.mean(x_arr))
        if mu_x > 1.0:
            mu_x /= float(width)
        placed = False
        for col in columns:
            if abs(col["mean_x"] - mu_x) < 0.15:
                col["tracks"].append((tidx, tr))
                placed = True
                break
        if not placed:
            columns.append({"mean_x": mu_x, "tracks": [(tidx, tr)]})

    # If 2 or more distinct columns exist with temporal overlap, use split screen
    if len(columns) >= 2:
        overlap_threshold = 15
        for i in range(len(columns)):
            for j in range(i + 1, len(columns)):
                f1 = set()
                for _, tr in columns[i]["tracks"]:
                    frames = tr["track"]["frame"] if isinstance(tr["track"], dict) and "frame" in tr["track"] else tr.get("proc_track", {}).get("frame", [])
                    f1.update(frames.tolist() if hasattr(frames, "tolist") else frames)
                f2 = set()
                for _, tr in columns[j]["tracks"]:
                    frames = tr["track"]["frame"] if isinstance(tr["track"], dict) and "frame" in tr["track"] else tr.get("proc_track", {}).get("frame", [])
                    f2.update(frames.tolist() if hasattr(frames, "tolist") else frames)

                if len(f1.intersection(f2)) >= overlap_threshold:
                    return "split"

    # Default for single speaker or non-overlapping speakers: Single vertical reframe
    return "reframe"


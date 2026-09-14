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
    """Analyze face tracks and determine the optimal layout mode for a scene or video."""
    if not tracks:
        return "letterbox"

    valid_tracks = []
    prominent_tracks = []
    total_max_frame = 0

    for tidx, tr in enumerate(tracks):
        sc = scores[tidx] if tidx < len(scores) else []
        is_valid, mean_sc, max_sc, mean_s, dur = is_valid_face_track(tr, sc, frame_height=float(height))
        if is_valid:
            valid_tracks.append((tidx, tr))
            frames = tr.get("track", {}).get("frame", []) if isinstance(tr.get("track"), dict) else tr.get("proc_track", {}).get("frame", [])
            xs = tr.get("proc_track", {}).get("x", [])
            mean_x = float(np.mean(xs)) if len(xs) > 0 else 0.5 * width
            norm_x = mean_x / float(width) if mean_x > 1.0 else mean_x
            norm_s = mean_s / float(height) if mean_s > 1.0 else mean_s

            # Genuine speaker must be sufficiently prominent (>=5% height) and within active frame area
            if norm_s >= 0.05 and 0.05 <= norm_x <= 0.95:
                prominent_tracks.append((tidx, tr))
                if len(frames) > 0:
                    dur_frames = int(np.max(frames) - np.min(frames) + 1)
                    total_max_frame = max(total_max_frame, dur_frames)

    if not valid_tracks:
        return "letterbox"

    eval_tracks = prominent_tracks if prominent_tracks else valid_tracks

    # Filter out secondary tracks that are mirror reflections or background passersby
    # A track is a reflection/background if its face size is tiny compared to the primary speaker (<42%)
    # and it does not have strong independent speech activity (max_sc < 0.15).
    if len(eval_tracks) >= 2:
        max_size = max(
            is_valid_face_track(tr, scores[tidx] if tidx < len(scores) else [], frame_height=float(height))[3]
            for tidx, tr in eval_tracks
        )
        filtered_eval_tracks = []
        for tidx, tr in eval_tracks:
            sc = scores[tidx] if tidx < len(scores) else []
            _, mean_sc, max_sc, mean_s, dur = is_valid_face_track(tr, sc, frame_height=float(height))
            size_ratio = mean_s / max_size if max_size > 0 else 1.0
            if size_ratio < 0.42 and max_sc < 0.15:
                logger.info(
                    "Rejected track %d as mirror reflection or background face (size_ratio=%.2f, max_sc=%.2f)",
                    tidx, size_ratio, max_sc,
                )
                continue
            filtered_eval_tracks.append((tidx, tr))
        if filtered_eval_tracks:
            eval_tracks = filtered_eval_tracks

    # Check for dominant primary speaker first (e.g. standard talking head, podcast host, presentation)
    has_dominant_speaker = False
    for tidx, tr in eval_tracks:
        sc = scores[tidx] if tidx < len(scores) else []
        _, mean_sc, max_sc, mean_s, dur = is_valid_face_track(tr, sc, frame_height=float(height))
        mean_x = float(np.mean(tr["proc_track"]["x"]))
        mean_y = float(np.mean(tr["proc_track"]["y"]))
        norm_x = mean_x / float(width) if mean_x > 1.0 else mean_x
        norm_y = mean_y / float(height) if mean_y > 1.0 else mean_y
        norm_s = mean_s / float(height) if mean_s > 1.0 else mean_s

        # A dominant center speaker is positioned towards the center region (not tucked into an outer corner)
        is_corner = (norm_x < 0.25 or norm_x > 0.75) and (norm_y < 0.30 or norm_y > 0.70) and norm_s <= 0.28
        if not is_corner and (norm_s >= 0.18 or (0.22 <= norm_x <= 0.78 and norm_s >= 0.12)) and (max_sc > 0.10 or dur > 30):
            has_dominant_speaker = True
            break

    # Identify tracks with active speech activity in this segment/scene
    speaking_tracks = []
    for tidx, tr in eval_tracks:
        sc = scores[tidx] if tidx < len(scores) else []
        _, mean_sc, max_sc, _, _ = is_valid_face_track(tr, sc, frame_height=float(height))
        # An active speaking track must have genuine speech confidence from TalkNet ASD
        if max_sc >= 0.60 or mean_sc >= 0.40:
            speaking_tracks.append((tidx, tr))

    # Build a per-frame mapping of simultaneous face X positions
    frame_faces: dict[int, list[float]] = {}
    for tidx, tr in eval_tracks:
        frames = tr.get("track", {}).get("frame", []) if isinstance(tr.get("track"), dict) else tr.get("proc_track", {}).get("frame", [])
        xs = tr.get("proc_track", {}).get("x", [])
        f_list = frames.tolist() if hasattr(frames, "tolist") else list(frames)
        x_list = xs.tolist() if hasattr(xs, "tolist") else list(xs)
        for f_val, x_val in zip(f_list, x_list):
            f_int = int(f_val)
            norm_x = float(x_val) / float(width) if float(x_val) > 1.0 else float(x_val)
            frame_faces.setdefault(f_int, []).append(norm_x)

    simultaneous_distant_frames = 0
    simultaneous_panel_frames = 0

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

        if len(x_coords) >= 3:
            distinct = []
            for x in x_coords:
                if not any(abs(x - dx) < 0.18 for dx in distinct):
                    distinct.append(x)
            if len(distinct) >= 3:
                simultaneous_panel_frames += 1

    min_required_split_frames = min(45, max(15, int(total_max_frame * 0.35))) if total_max_frame > 0 else 15

    logger.info(
        "Layout evaluation: %d distant 2-face frames, %d 3-face frames (required=%d, prominent_tracks=%d, speaking_tracks=%d)",
        simultaneous_distant_frames,
        simultaneous_panel_frames,
        min_required_split_frames,
        len(eval_tracks),
        len(speaking_tracks),
    )

    # 3+ person panel: requires 3+ simultaneous speakers across screen
    if simultaneous_panel_frames >= min_required_split_frames and len(eval_tracks) >= 3 and len(speaking_tracks) >= 2:
        logger.info("Classified layout as PANEL (3+ simultaneous speakers across screen)")
        return "panel"

    # 2-person split screen: ONLY if both people are actively speaking/conversing in this segment.
    # If only 1 speaker is talking, reframe to that active speaker!
    if simultaneous_distant_frames >= min_required_split_frames and len(eval_tracks) >= 2 and len(speaking_tracks) >= 2:
        logger.info("Classified layout as SPLIT (two simultaneous active dialogue speakers)")
        return "split"

    logger.info("Classified layout as REFRAME (single active speaker / solo crop)")
    return "reframe"

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
    """Analyze face tracks and determine the optimal layout mode for a scene or video.
    
    Returns:
    - "letterbox": B-roll footage, screen cutaway, landscape, or scene with no active speaking faces.
    - "split": Multi-speaker dialogue scene (>=2 active talking speakers).
    - "screencast": Screencast / gaming / presentation with corner facecam overlay.
    - "reframe": Solo active talking speaker.
    """
    if not tracks:
        return "letterbox"

    valid_tracks = []
    total_max_frame = 0
    for tidx, tr in enumerate(tracks):
        sc = scores[tidx] if tidx < len(scores) else []
        is_valid, mean_sc, max_sc, mean_s, dur = is_valid_face_track(tr, sc, frame_height=float(height))
        if is_valid:
            valid_tracks.append((tidx, tr, mean_sc, max_sc, mean_s, dur))
            frames = tr.get("track", {}).get("frame", []) if isinstance(tr.get("track"), dict) else tr.get("proc_track", {}).get("frame", [])
            if len(frames) > 0:
                total_max_frame = max(total_max_frame, int(np.max(frames)))

    if not valid_tracks:
        return "letterbox"

    # Distinguish B-roll vs Speaker:
    # A true speaker scene must have at least one face with active speech (ASD max_score >= 0.15 or mean_score >= 0.05).
    # If all faces in the scene are silent (stock video, silent actors, b-roll people, posters), treat as B-roll (letterbox).
    speaking_tracks = [vt for vt in valid_tracks if vt[3] >= 0.15 or vt[2] >= 0.05]
    if not speaking_tracks:
        logger.info("Classified layout as LETTERBOX (B-roll / cutaway detected: faces present but silent)")
        return "letterbox"

    # Check for dominant primary speaker first (e.g. standard talking head, podcast host, presentation)
    has_dominant_speaker = False
    for tidx, tr, mean_sc, max_sc, mean_s, dur in speaking_tracks:
        mean_x = float(np.mean(tr["proc_track"]["x"]))
        mean_y = float(np.mean(tr["proc_track"]["y"]))
        norm_x = mean_x / float(width) if mean_x > 1.0 else mean_x
        norm_y = mean_y / float(height) if mean_y > 1.0 else mean_y
        norm_s = mean_s / float(height) if mean_s > 1.0 else mean_s

        # A dominant center speaker is positioned towards the center region (not tucked into an outer corner)
        is_corner = (norm_x < 0.25 or norm_x > 0.75) and (norm_y < 0.30 or norm_y > 0.70) and norm_s <= 0.28
        if not is_corner and (norm_s >= 0.18 or (0.22 <= norm_x <= 0.78 and norm_s >= 0.12)):
            has_dominant_speaker = True
            break

    # Check for Corner Facecam (Screencast / Gaming with streamer/presenter overlay)
    if not has_dominant_speaker:
        for tidx, tr, mean_sc, max_sc, mean_s, dur in speaking_tracks:
            mean_x = float(np.mean(tr["proc_track"]["x"]))
            mean_y = float(np.mean(tr["proc_track"]["y"]))
            norm_x = mean_x / float(width) if mean_x > 1.0 else mean_x
            norm_y = mean_y / float(height) if mean_y > 1.0 else mean_y
            norm_s = mean_s / float(height) if mean_s > 1.0 else mean_s

            if (
                norm_s <= 0.28
                and (norm_x < 0.30 or norm_x > 0.70)
                and (norm_y < 0.35 or norm_y > 0.65)
                and dur >= max(15, int(total_max_frame * 0.15))
            ):
                logger.info(
                    "Classified layout as SCREENCAST (detected active corner facecam overlay at x=%.2f, y=%.2f, s=%.2f, max_sc=%.2f)",
                    norm_x, norm_y, norm_s, max_sc,
                )
                return "screencast"

    # Build a per-frame mapping of simultaneous face X positions
    frame_faces: dict[int, list[float]] = {}
    for tidx, tr, _, _, _, _ in valid_tracks:
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
    # 3. There must be >= 2 active speaking tracks.
    simultaneous_distant_frames = 0
    for f_int, x_coords in frame_faces.items():
        if len(x_coords) >= 2:
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

    active_tracks_count = len(speaking_tracks)
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


"""Content Classifier for AI Reframer.

Lightweight heuristic analysis (<500ms on CPU) to categorize video content type:
- TALKING_HEAD: Standard 1-2 person podcast/interview (use face reframe / split)
- SCREENCAST: Software tutorials, coding, screen recordings (smart zoom letterbox)
- PRESENTATION: Slide presentations with or without corner face-cam
- PANEL: 3+ speakers roundtable/discussion
- GAMING: Fast gameplay action, HUDs, corner face-cam
- VERTICAL_NATIVE: Already 9:16 vertical video
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
import os
import subprocess
from typing import List, Optional, Tuple

try:
    import cv2
except ImportError:
    cv2 = None
import numpy as np

logger = logging.getLogger("makemyclip.content_classifier")


class ContentType(str, Enum):
    TALKING_HEAD = "talking_head"
    SCREENCAST = "screencast"
    PRESENTATION = "presentation"
    PANEL = "panel"
    GAMING = "gaming"
    VERTICAL_NATIVE = "vertical_native"


@dataclass
class ContentClassification:
    content_type: ContentType
    confidence: float
    recommended_crop_mode: str
    skip_face_tracking: bool
    metadata: dict


def sample_video_frames(
    video_path: str,
    start_time: float = 0.0,
    duration: float = 10.0,
    num_samples: int = 5,
    target_height: int = 360,
) -> List[np.ndarray]:
    """Sample evenly spaced frames downscaled for fast heuristic analysis."""
    frames = []
    if not os.path.exists(video_path):
        return frames

    try:
        # Sample frames with ffmpeg fps filter
        step = max(0.5, duration / max(num_samples, 1))
        for i in range(num_samples):
            t = start_time + i * step
            cmd = [
                "ffmpeg",
                "-ss", str(t),
                "-i", video_path,
                "-vframes", "1",
                "-vf", f"scale=-2:{target_height}",
                "-f", "image2pipe",
                "-pix_fmt", "bgr24",
                "-vcodec", "rawvideo",
                "-loglevel", "panic",
                "-",
            ]
            res = subprocess.run(cmd, capture_output=True, timeout=10)
            if res.returncode == 0 and len(res.stdout) > 0:
                # Deduce width from byte length: w * target_height * 3 = len
                w = len(res.stdout) // (target_height * 3)
                if w > 0:
                    arr = np.frombuffer(res.stdout[:w * target_height * 3], dtype=np.uint8)
                    frame = arr.reshape((target_height, w, 3))
                    frames.append(frame)
    except Exception as e:
        logger.warning("Failed to sample video frames for classification: %s", e)

    return frames


def detect_screen_edges_and_text(frames: List[np.ndarray]) -> float:
    """Score frame density of sharp UI / code / horizontal lines characteristic of screen recordings."""
    if not frames:
        return 0.0

    scores = []
    for frame in frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Compute horizontal gradients (typical in text, code lines, windows)
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        mag = np.sqrt(sobel_x ** 2 + sobel_y ** 2)
        edge_density = float(np.mean(mag > 50.0))
        scores.append(edge_density)

    return float(np.mean(scores)) if scores else 0.0


def compute_interframe_motion(frames: List[np.ndarray]) -> float:
    """Compute average frame difference (motion energy)."""
    if len(frames) < 2:
        return 0.0

    diffs = []
    for i in range(len(frames) - 1):
        g1 = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(frames[i + 1], cv2.COLOR_BGR2GRAY)
        if g1.shape == g2.shape:
            diff = float(np.mean(np.abs(g1.astype(float) - g2.astype(float))))
            diffs.append(diff)

    return float(np.mean(diffs)) if diffs else 0.0


def classify_content(
    video_path: str,
    width: int,
    height: int,
    fps: float = 25.0,
    duration: float = 60.0,
    start_time: float = 0.0,
    known_face_count: Optional[int] = None,
    face_positions: Optional[List[dict]] = None,
) -> ContentClassification:
    """Classify video content type using lightweight heuristics (<500ms)."""
    # 1. Vertical native check (9:16 or portrait)
    if height > 0 and width > 0:
        aspect = width / float(height)
        if aspect <= 0.65:  # e.g., 9:16 is ~0.5625, 4:5 is 0.8
            return ContentClassification(
                content_type=ContentType.VERTICAL_NATIVE,
                confidence=0.99,
                recommended_crop_mode="passthrough",
                skip_face_tracking=True,
                metadata={"aspect_ratio": aspect},
            )

    # Sample a few frames for visual cues
    sampled = sample_video_frames(
        video_path=video_path,
        start_time=start_time,
        duration=min(duration, 30.0),
        num_samples=4,
    )

    edge_score = detect_screen_edges_and_text(sampled)
    motion_score = compute_interframe_motion(sampled)

    logger.info(
        "Content classifier cues: edge_score=%.4f, motion_score=%.2f, known_face_count=%s",
        edge_score, motion_score, known_face_count
    )

    # 2. Panel discussion check (3+ distinct speakers)
    if known_face_count is not None and known_face_count >= 3:
        return ContentClassification(
            content_type=ContentType.PANEL,
            confidence=0.88,
            recommended_crop_mode="panel",
            skip_face_tracking=False,
            metadata={"num_faces": known_face_count},
        )

    # 3. Screencast / Presentation checks
    # Real screencasts/code editors have dense sharp horizontal text/UI lines (>0.35)
    if edge_score > 0.35:
        # Check if there is a tiny corner face (Presentation / Screencast with webcam)
        has_corner_face = False
        if face_positions:
            for f in face_positions:
                fx = f.get("x", 0.5)
                fy = f.get("y", 0.5)
                fs = f.get("s", 0.1)
                # If face is small (<15% of frame) and located in outer quadrant
                if fs < 0.15 and (fx < 0.25 or fx > 0.75) and (fy < 0.25 or fy > 0.75):
                    has_corner_face = True
                    break

        if has_corner_face:
            return ContentClassification(
                content_type=ContentType.PRESENTATION,
                confidence=0.85,
                recommended_crop_mode="presentation",
                skip_face_tracking=False,
                metadata={"edge_score": edge_score, "has_corner_face": True},
            )

        return ContentClassification(
            content_type=ContentType.SCREENCAST,
            confidence=0.82,
            recommended_crop_mode="screencast",
            skip_face_tracking=(known_face_count == 0),
            metadata={"edge_score": edge_score},
        )

    # 4. Gaming check (high continuous motion + high contrast colors)
    if motion_score > 45.0 and (known_face_count is None or known_face_count <= 1):
        return ContentClassification(
            content_type=ContentType.GAMING,
            confidence=0.75,
            recommended_crop_mode="gaming",
            skip_face_tracking=False,
            metadata={"motion_score": motion_score},
        )

    # 5. Default talking head (allows TalkNet ASD and LayoutClassifier to pick single vs split vs letterbox)
    return ContentClassification(
        content_type=ContentType.TALKING_HEAD,
        confidence=0.90,
        recommended_crop_mode="auto",
        skip_face_tracking=False,
        metadata={"edge_score": edge_score, "motion_score": motion_score},
    )

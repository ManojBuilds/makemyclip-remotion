"""Comprehensive Video Types & Render Strategies Test Suite.

Tests all 7 supported video types:
1. Reframe (Solo Talking Head)
2. Split (2-Speaker Podcast)
3. Screencast (Coding / Software Tutorial)
4. Presentation (Slide Deck + Corner Face PiP)
5. Panel (3+ Speaker Roundtable)
6. Letterbox (Blurred Background Card)
7. Passthrough (9:16 Vertical Native)
"""

import os
import sys
import numpy as np

# Ensure local imports work
sys.path.insert(0, os.path.dirname(__file__))

try:
    import cv2
except ImportError:
    import cv2

from render_strategies import (
    get_strategy,
    ReframeStrategy,
    SplitStrategy,
    ScreencastStrategy,
    PresentationStrategy,
    PanelStrategy,
    LetterboxStrategy,
    PassthroughStrategy,
)
from content_classifier import classify_content, ContentType


def create_test_frame(w=1920, h=1080, pattern="normal"):
    """Create synthetic test frames with distinct visual patterns."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    
    if pattern == "screencast":
        # Simulate code editor with horizontal syntax lines and dark background
        img[:] = (30, 30, 30)
        # Add text-like horizontal lines (editor window)
        for y in range(80, h - 80, 24):
            line_len = int(w * (0.3 + 0.4 * np.sin(y)))
            cv2.line(img, (100, y), (100 + line_len, y), (180, 200, 220), 3)
            # Add some keywords
            cv2.rectangle(img, (100, y - 2), (160, y + 2), (80, 160, 255), -1)
    elif pattern == "presentation":
        # Simulate slide presentation: white card with header + bullet points
        img[:] = (40, 40, 40)
        cv2.rectangle(img, (120, 80), (w - 120, h - 80), (245, 245, 245), -1)
        cv2.putText(img, "Slide Title: AI Video Generation", (160, 160), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (20, 20, 20), 3)
        for i in range(4):
            cv2.circle(img, (180, 260 + i * 80), 8, (0, 120, 255), -1)
            cv2.line(img, (220, 260 + i * 80), (w - 300, 260 + i * 80), (60, 60, 60), 4)
    elif pattern == "vertical":
        # 9:16 vertical image
        img = np.zeros((1920, 1080, 3), dtype=np.uint8)
        img[:] = (20, 80, 120)
        cv2.putText(img, "9:16 TikTok / Reel", (200, 960), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
    else:
        # Standard podcast scene background
        img[:] = (35, 30, 45)
        # Draw gradient studio background
        for y in range(h):
            img[y, :] = (int(35 + 20 * (y / h)), 30, int(45 + 30 * (y / h)))

    return img


def run_all_tests():
    print("=================================================================")
    print("🚀 RUNNING MAKE-MY-CLIP VIDEO TYPES & RENDER STRATEGIES TEST SUITE")
    print("=================================================================\n")

    os.makedirs("test_outputs", exist_ok=True)

    # -------------------------------------------------------------
    # 1. Solo Talking Head (Reframe)
    # -------------------------------------------------------------
    print("▶ Testing 1. Solo Talking Head (crop_mode='reframe')...")
    frame = create_test_frame(1920, 1080, "normal")
    # Draw simulated speaker face at center
    cv2.circle(frame, (960, 400), 80, (200, 180, 160), -1)
    faces = [{"x": 960, "y": 400, "s": 160, "score": 0.95}]
    state = {"target_cx": 960, "current_cx": 960}
    strategy = get_strategy("reframe")
    out = strategy.render_frame(frame, 0, faces, state)
    assert out.shape == (1920, 1080, 3), f"Invalid shape {out.shape}"
    cv2.imwrite("test_outputs/1_reframe_solo.jpg", out)
    print("  ✅ ReframeStrategy rendered 1080x1920 output -> test_outputs/1_reframe_solo.jpg")

    # -------------------------------------------------------------
    # 2. 2-Person Podcast (Split)
    # -------------------------------------------------------------
    print("▶ Testing 2. 2-Person Podcast (crop_mode='split')...")
    frame = create_test_frame(1920, 1080, "normal")
    # Left speaker & right speaker
    cv2.circle(frame, (480, 400), 80, (200, 180, 160), -1)
    cv2.circle(frame, (1440, 400), 80, (180, 160, 200), -1)
    faces = [
        {"x": 480, "y": 400, "s": 160, "score": 0.85},   # Left active speaker
        {"x": 1440, "y": 400, "s": 160, "score": 0.20},  # Right listening speaker
    ]
    strategy = get_strategy("split")
    out = strategy.render_frame(frame, 0, faces, {})
    assert out.shape == (1920, 1080, 3), f"Invalid shape {out.shape}"
    cv2.imwrite("test_outputs/2_split_podcast.jpg", out)
    print("  ✅ SplitStrategy rendered 1080x1920 2-panel split -> test_outputs/2_split_podcast.jpg")

    # -------------------------------------------------------------
    # 3. Screencast / Code Tutorial (Screencast)
    # -------------------------------------------------------------
    print("▶ Testing 3. Coding Screencast (crop_mode='screencast')...")
    frame = create_test_frame(1920, 1080, "screencast")
    # Add optional face-cam in top right
    cv2.circle(frame, (1800, 150), 50, (210, 190, 170), -1)
    faces = [{"x": 1800, "y": 150, "s": 80, "score": 0.7}]
    strategy = get_strategy("screencast")
    out = strategy.render_frame(frame, 0, faces, {})
    assert out.shape == (1920, 1080, 3), f"Invalid shape {out.shape}"
    cv2.imwrite("test_outputs/3_screencast.jpg", out)
    print("  ✅ ScreencastStrategy rendered 1080x1920 smart-zoomed card + PiP -> test_outputs/3_screencast.jpg")

    # -------------------------------------------------------------
    # 4. Slide Presentation (Presentation)
    # -------------------------------------------------------------
    print("▶ Testing 4. Slide Presentation (crop_mode='presentation')...")
    frame = create_test_frame(1920, 1080, "presentation")
    cv2.circle(frame, (1780, 180), 55, (220, 190, 160), -1)
    faces = [{"x": 1780, "y": 180, "s": 90, "score": 0.8}]
    strategy = get_strategy("presentation")
    out = strategy.render_frame(frame, 0, faces, {})
    assert out.shape == (1920, 1080, 3), f"Invalid shape {out.shape}"
    cv2.imwrite("test_outputs/4_presentation.jpg", out)
    print("  ✅ PresentationStrategy rendered 1080x1920 slide card + PiP -> test_outputs/4_presentation.jpg")

    # -------------------------------------------------------------
    # 5. Multi-Speaker Roundtable (Panel)
    # -------------------------------------------------------------
    print("▶ Testing 5. 3+ Speaker Panel (crop_mode='panel')...")
    frame = create_test_frame(1920, 1080, "normal")
    cv2.circle(frame, (350, 450), 70, (200, 180, 160), -1)
    cv2.circle(frame, (960, 450), 70, (180, 200, 170), -1)
    cv2.circle(frame, (1570, 450), 70, (170, 180, 210), -1)
    faces = [
        {"x": 350, "y": 450, "s": 140, "score": 0.90},
        {"x": 960, "y": 450, "s": 140, "score": 0.30},
        {"x": 1570, "y": 450, "s": 140, "score": 0.25},
    ]
    strategy = get_strategy("panel")
    out = strategy.render_frame(frame, 0, faces, {})
    assert out.shape == (1920, 1080, 3), f"Invalid shape {out.shape}"
    cv2.imwrite("test_outputs/5_panel_grid.jpg", out)
    print("  ✅ PanelStrategy rendered 1080x1920 2x2 panel grid -> test_outputs/5_panel_grid.jpg")

    # -------------------------------------------------------------
    # 6. Letterbox (Letterbox)
    # -------------------------------------------------------------
    print("▶ Testing 6. Blurred Letterbox Card (crop_mode='letterbox')...")
    frame = create_test_frame(1920, 1080, "normal")
    strategy = get_strategy("letterbox")
    out = strategy.render_frame(frame, 0, [], {})
    assert out.shape == (1920, 1080, 3), f"Invalid shape {out.shape}"
    cv2.imwrite("test_outputs/6_letterbox.jpg", out)
    print("  ✅ LetterboxStrategy rendered 1080x1920 blurred letterbox -> test_outputs/6_letterbox.jpg")

    # -------------------------------------------------------------
    # 7. 9:16 Vertical Native (Passthrough)
    # -------------------------------------------------------------
    print("▶ Testing 7. 9:16 Vertical Native (crop_mode='passthrough')...")
    v_frame = create_test_frame(1080, 1920, "vertical")
    strategy = get_strategy("passthrough")
    out = strategy.render_frame(v_frame, 0, [], {})
    assert out.shape == (1920, 1080, 3), f"Invalid shape {out.shape}"
    cv2.imwrite("test_outputs/7_passthrough.jpg", out)
    print("  ✅ PassthroughStrategy rendered 1080x1920 direct vertical passthrough -> test_outputs/7_passthrough.jpg")

    print("\n=================================================================")
    print("🎉 ALL 7 VIDEO TYPE RENDER STRATEGIES PASSED VALIDATION!")
    print("Generated test image artifacts saved to ./test_outputs/")
    print("=================================================================")


if __name__ == "__main__":
    run_all_tests()

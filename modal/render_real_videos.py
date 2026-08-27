"""Render real test video clips with all strategies to verify full MP4 generation."""

import os
import sys
import subprocess

sys.path.insert(0, os.path.dirname(__file__))

import cv2
import numpy as np

from render_strategies import get_strategy
from content_classifier import classify_content


def render_clip(input_video: str, output_video: str, crop_mode: str, duration_s: float = 6.0, fps: float = 25.0):
    print(f"\n=======================================================")
    print(f"🎬 Processing: {input_video}")
    print(f"🎯 Target Crop Mode: {crop_mode}")
    print(f"=======================================================")

    if not os.path.exists(input_video):
        print(f"❌ Input video not found: {input_video}")
        return False

    cap = cv2.VideoCapture(input_video)
    if not cap.isOpened():
        print(f"❌ Failed to open video: {input_video}")
        return False

    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or fps
    total_frames = int(min(cap.get(cv2.CAP_PROP_FRAME_COUNT), duration_s * src_fps))

    print(f"ℹ️ Input stats: {src_w}x{src_h} @ {src_fps:.1f}fps, rendering {total_frames} frames ({duration_s}s)")

    # Run content classification first
    classification = classify_content(
        video_path=input_video,
        width=src_w,
        height=src_h,
        fps=src_fps,
        duration=duration_s,
    )
    print(f"🤖 AI Content Classifier Detected: {classification.content_type.value} (Confidence: {classification.confidence:.2f}, Recommended: {classification.recommended_crop_mode})")

    strategy = get_strategy(crop_mode, target_w=1080, target_h=1920)
    
    # FFmpeg writer for MP4
    temp_raw = output_video.replace(".mp4", "_raw.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", "1080x1920",
        "-pix_fmt", "bgr24",
        "-r", str(src_fps),
        "-i", "-",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        temp_raw,
        "-loglevel", "panic"
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    state = {}
    fidx = 0
    while fidx < total_frames:
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        # Render frame with strategy
        out_frame = strategy.render_frame(frame, fidx, [], state)
        proc.stdin.write(out_frame.tobytes())
        fidx += 1

    cap.release()
    proc.stdin.close()
    proc.wait()

    # Extract audio and mux
    temp_audio = output_video.replace(".mp4", ".aac")
    subprocess.run([
        "ffmpeg", "-y",
        "-i", input_video,
        "-t", str(duration_s),
        "-vn", "-c:a", "aac",
        temp_audio,
        "-loglevel", "panic"
    ])

    # Mux final
    if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 0:
        subprocess.run([
            "ffmpeg", "-y",
            "-i", temp_raw,
            "-i", temp_audio,
            "-c:v", "copy",
            "-c:a", "copy",
            output_video,
            "-loglevel", "panic"
        ])
        if os.path.exists(temp_raw): os.remove(temp_raw)
        if os.path.exists(temp_audio): os.remove(temp_audio)
    else:
        os.rename(temp_raw, output_video)

    out_size = os.path.getsize(output_video) / (1024 * 1024)
    print(f"✅ Successfully rendered vertical video: {output_video} ({out_size:.2f} MB)")
    return True


def main():
    os.makedirs("real_test_outputs", exist_ok=True)

    test_cases = [
        # (input_path, output_path, crop_mode, description)
        ("vault/solo_talking_head.mp4", "real_test_outputs/1_solo_reframe.mp4", "reframe"),
        ("vault/two_person_podcast.mp4", "real_test_outputs/2_podcast_split.mp4", "split"),
        ("vault/webcam_course_layout.mp4", "real_test_outputs/3_course_screencast.mp4", "screencast"),
        ("downloads/yt_panel.mp4", "real_test_outputs/4_panel_grid.mp4", "panel"),
        ("vault/tv_show.mp4", "real_test_outputs/5_tvshow_letterbox.mp4", "letterbox"),
    ]

    for inp, outp, mode in test_cases:
        if os.path.exists(inp):
            render_clip(inp, outp, mode, duration_s=5.0)
        else:
            print(f"Skipping {inp} (file not found)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess
import json

# Ensure modal folder is in python path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modal"))
)

from ass_builder import generate_ass
from presets import PRESET_STYLES

# 1. Load transcript from podcast_transcript_en.json
transcript_path = "scratch/podcast_transcript_en.json"
if not os.path.exists(transcript_path):
    print(f"❌ Error: Transcript not found at {transcript_path}")
    sys.exit(1)

with open(transcript_path, "r") as f:
    PODCAST_TRANSCRIPT = json.load(f)["words"]

# Premium style designed for podcast captions (similar to Theo Von / high-retention shorts)
THEO_STYLE = {
    "preset": "simple",
    # Font
    "font_family": "Boldonse",
    "font_weight": "900",
    "font_size": 72,
    # Colors
    "font_color": "#FFFFFF",
    "stroke_color": "#000000",
    "stroke_width": 6,
    # Animation
    "animation": "word-pop",
    "shadow": False,
    "italic": False,
    # Position
    "alignment": 2,
    "position_y": 0.55,
    # Caption
    "uppercase": True,
    "max_words": 2,
}


def burn_captions(input_video, output_video, ass_file):
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_video,
        "-vf",
        f"ass='{ass_file}'",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-c:a",
        "copy",
        output_video,
    ]
    print(f"🎬 Running FFmpeg command to burn captions...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ Captions burned successfully! Output saved to: {output_video}")
        return True
    else:
        print("❌ FFmpeg caption burn failed!")
        print(f"Stderr: {result.stderr}")
        return False


def main():
    print("=== STARTING CAPTION BURN FOR PODCAST (THEO VON STYLE) ===")

    input_video = "downloads/result_podcast_reframe.mp4"
    output_video = "downloads/result_podcast_reframe_captioned2.mp4"
    ass_file = os.path.abspath("scratch/podcast_temp.ass")

    if not os.path.exists(input_video):
        print(f"❌ Error: Input video not found at {input_video}")
        return

    print(f"Using input video: {input_video}")
    print("Generating ASS file with custom Theo style...")

    # Generate ASS file using the project's production ass_builder
    try:
        generate_ass(PODCAST_TRANSCRIPT, THEO_STYLE, ass_file, crop_mode="reframe")
        print(f"✅ Generated ASS file at: {ass_file}")
    except Exception as e:
        print(f"❌ Failed to generate ASS file: {e}")
        return

    # Burn captions
    burn_captions(input_video, output_video, ass_file)


if __name__ == "__main__":
    main()

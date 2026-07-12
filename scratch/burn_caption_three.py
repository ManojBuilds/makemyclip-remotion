#!/usr/bin/env python3
import os
import sys
import json
import subprocess

# Ensure modal folder is in python path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modal"))
)

from ass_builder import generate_ass

# Load transcript from course_transcript_en.json
transcript_path = "scratch/course_transcript_en.json"
if not os.path.exists(transcript_path):
    print(f"❌ Error: Transcript not found at {transcript_path}")
    sys.exit(1)

with open(transcript_path, "r") as f:
    COURSE_TRANSCRIPT = json.load(f)["words"]

# Custom premium style designed for clean, educational / course layout
CUSTOM_COURSE_STYLE = {
    "preset": "simple",
    # Font
    "font_family": "Englebert",
    "font_weight": "800",
    "font_size": 52,
    # Colors
    "font_color": "#FFFFFF",
    "stroke_color": "#000000",
    "stroke_width": 1.8,
    # Animation
    "animation": "smooth-fade",
    # Shadow
    "shadow": True,
    "shadow_depth": 1.5,
    "italic": False,
    # KEEP ORIGINAL POSITION
    "alignment": 2,  # Bottom-center anchor
    "position_y": 0.51,
    # Caption style
    "uppercase": False,
    "max_words": 3,
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
    print(f"🎬 Running FFmpeg command to burn course captions...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ Captions burned successfully! Output saved to: {output_video}")
        return True
    else:
        print("❌ FFmpeg caption burn failed!")
        print(f"Stderr: {result.stderr}")
        return False


def main():
    print(
        "=== STARTING CAPTION BURN FOR TEST CASE 3 (COURSE PRESENTATION - CLEAN GLOW) ==="
    )

    input_video = "downloads/result_course_presentation.mp4"
    output_video = "downloads/result_course_presentation_captioned_with_custom_font.mp4"
    ass_file = os.path.abspath("scratch/course_temp.ass")

    if not os.path.exists(input_video):
        print(f"❌ Error: Input video not found at {input_video}")
        return

    print(
        "Generating ASS file with custom premium (simple / smooth-fade) style overrides..."
    )

    try:
        generate_ass(
            COURSE_TRANSCRIPT, CUSTOM_COURSE_STYLE, ass_file, crop_mode="course"
        )
        print(f"✅ Generated ASS file at: {ass_file}")
    except Exception as e:
        print(f"❌ Failed to generate ASS file: {e}")
        return

    burn_captions(input_video, output_video, ass_file)


if __name__ == "__main__":
    main()

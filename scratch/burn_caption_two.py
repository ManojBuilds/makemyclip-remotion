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

# Load transcript from interview_transcript_en.json
transcript_path = "scratch/interview_transcript_en.json"
if not os.path.exists(transcript_path):
    print(f"❌ Error: Transcript not found at {transcript_path}")
    sys.exit(1)

with open(transcript_path, "r") as f:
    INTERVIEW_TRANSCRIPT = json.load(f)["words"]


# Large non-italic Bangers font with black fill and thick white stroke
STICKER_INTERVIEW_STYLE = {
    "preset": "simple",
    "font_family": "Bangers",
    "font_size": 90,  # High value to make it large
    "font_color": "#000000",  # Black text
    "stroke_color": "#FFFFFF",  # White stroke outline
    "stroke_width": 10.0,  # Thick white stroke outline
    "background": False,
    "animation": "none",
    "shadow": False,
    "shadow_depth": 0.0,
    "italic": False,  # No italic slant
    "alignment": 5,  # Center-center
    "position_y": 0.50,  # Split line level
    "uppercase": True,
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
    print(f"🎬 Running FFmpeg command to burn sticker captions...")
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
        "=== STARTING CAPTION BURN FOR TEST CASE 2 (INTERVIEW SPLIT - STICKER STYLE LARGE) ==="
    )

    input_video = "downloads/result_interview_split.mp4"
    output_video = "downloads/result_interview_split_captioned.mp4"
    ass_file = os.path.abspath("scratch/interview_temp.ass")

    if not os.path.exists(input_video):
        print(f"❌ Error: Input video not found at {input_video}")
        return

    print(f"Using input video: {input_video}")
    print("Generating ASS file with sticker style layout overrides...")

    try:
        generate_ass(
            INTERVIEW_TRANSCRIPT, STICKER_INTERVIEW_STYLE, ass_file, crop_mode="split"
        )
        print(f"✅ Generated ASS file at: {ass_file}")
    except Exception as e:
        print(f"❌ Failed to generate ASS file: {e}")
        return

    burn_captions(input_video, output_video, ass_file)


if __name__ == "__main__":
    main()

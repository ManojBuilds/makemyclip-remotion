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


# 1. Install fonts locally so FFmpeg's libass can resolve them
def install_fonts():
    public_fonts_dir = os.path.abspath("public/fonts")
    if not os.path.exists(public_fonts_dir):
        print("⚠️ Warning: public/fonts/ folder not found.")
        return

    user_fonts_dir = os.path.expanduser("~/.local/share/fonts/makemyclip")
    os.makedirs(user_fonts_dir, exist_ok=True)

    installed_new = False
    for filename in os.listdir(public_fonts_dir):
        if filename.lower().endswith((".ttf", ".otf")):
            src = os.path.join(public_fonts_dir, filename)
            dst = os.path.join(user_fonts_dir, filename)
            if not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst):
                print(f"📁 Copying font to system cache: {filename}")
                shutil.copy2(src, dst)
                installed_new = True

    if installed_new:
        print("🔄 Rebuilding font cache (fc-cache -f)...")
        subprocess.run(
            ["fc-cache", "-f"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print("✅ Font cache updated!")
    else:
        print("✅ Fonts are already up-to-date in cache.")


# Load transcript from monologue_transcript_en.json
transcript_path = "scratch/monologue_transcript_en.json"
if not os.path.exists(transcript_path):
    print(f"❌ Error: Transcript not found at {transcript_path}")
    sys.exit(1)

with open(transcript_path, "r") as f:
    MONOLOGUE_TRANSCRIPT = json.load(f)["words"]

# Money Mode (Hormozi) style configuration
HORMOZI_STYLE = {
    # "preset": "hormozi",
    # "font_family": "The Bold Font",
    # "font_size": 64.0,
    # "font_color": "#FFFFFF",
    # "highlight_color": "#FFDC00",  # Yellow
    # "stroke_color": "#000000",
    # "stroke_width": 4.5,
    # "animation": "bounce",
    # "shadow": True,
    # "shadow_depth": 4.0,
    # "uppercase": True,
    # "max_words": 2,
    # "position_y": 0.70
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
    print("=== STARTING CAPTION BURN FOR TEST CASE 1 (MONOLOGUE) ===")

    # Install fonts
    install_fonts()

    input_video = "downloads/result_monologue_reframe.mp4"
    output_video = "downloads/result_monologue_reframe_captioned.mp4"
    ass_file = os.path.abspath("scratch/monologue_temp.ass")

    if not os.path.exists(input_video):
        print(f"❌ Error: Input video not found at {input_video}")
        return

    print(f"Using input video: {input_video}")
    print("Generating ASS file with 'hormozi' preset...")

    # Generate ASS file using the project's production ass_builder
    try:
        generate_ass(MONOLOGUE_TRANSCRIPT, HORMOZI_STYLE, ass_file, crop_mode="reframe")
        print(f"✅ Generated ASS file at: {ass_file}")
    except Exception as e:
        print(f"❌ Failed to generate ASS file: {e}")
        return

    # Burn captions
    burn_captions(input_video, output_video, ass_file)


if __name__ == "__main__":
    main()

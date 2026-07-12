#!/usr/bin/env python3
import os
import sys
import json
import subprocess

# Ensure modal folder is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modal")))

from ass_builder import generate_ass

# Load transcript from panel_transcript_en.json
transcript_path = "scratch/panel_transcript_en.json"
if not os.path.exists(transcript_path):
    print(f"❌ Error: Transcript not found at {transcript_path}")
    sys.exit(1)

with open(transcript_path, "r") as f:
    PANEL_TRANSCRIPT = json.load(f)["words"]


# recommended Viral Pop style using 'beast' routing for word-by-word highlight
RECOMMENDED_PANEL_STYLE = {
    "preset": "beast",          # Use beast preset for word-by-word highlighting
    "font_family": "Bebas Neue",
    "font_size": 48,            # 48 * 1.6 = 76.8px (excellent impact height)
    "font_color": "#FFFFFF",    # white base text
    "stroke_color": "#000000",  # black thin stroke for base words
    "stroke_width": 4.0,        # moderate black outline
    "highlight_color": "#00F0FF", # bright cyan active word highlight
    "background": False,
    "animation": "none",
    "shadow": False,
    "shadow_depth": 0.0,
    "italic": False,
    "alignment": 5,             # Center-center
    "position_y": 0.82,         # Middle of the bottom black bar
    "uppercase": True,          # High-retention uppercase
    "max_words": 3
}

def burn_captions(input_video, output_video, ass_file):
    cmd = [
        "ffmpeg", "-y",
        "-i", input_video,
        "-vf", f"ass='{ass_file}'",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        output_video
    ]
    print(f"🎬 Running FFmpeg command to burn panel captions...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ Captions burned successfully! Output saved to: {output_video}")
        return True
    else:
        print("❌ FFmpeg caption burn failed!")
        print(f"Stderr: {result.stderr}")
        return False

def main():
    print("=== STARTING CAPTION BURN FOR TEST CASE 4 (PANEL LETTERBOX - VIRAL POP WORD-BY-WORD) ===")
    
    input_video = "downloads/result_panel_letterbox.mp4"
    output_video = "downloads/result_panel_letterbox_captioned.mp4"
    ass_file = os.path.abspath("scratch/panel_temp.ass")
    
    if not os.path.exists(input_video):
        print(f"❌ Error: Input video not found at {input_video}")
        return
        
    print(f"Using input video: {input_video}")
    print("Generating ASS file with Viral Pop (Bebas Neue + Cyan highlight) layout overrides...")
    
    try:
        generate_ass(PANEL_TRANSCRIPT, RECOMMENDED_PANEL_STYLE, ass_file, crop_mode="letterbox")
        print(f"✅ Generated ASS file at: {ass_file}")
    except Exception as e:
        print(f"❌ Failed to generate ASS file: {e}")
        return
        
    burn_captions(input_video, output_video, ass_file)

if __name__ == "__main__":
    main()

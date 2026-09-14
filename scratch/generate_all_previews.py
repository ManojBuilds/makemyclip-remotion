import os
import sys
import subprocess

sys.path.insert(0, "./modal")
from presets import PRESET_STYLES
from ass_builder import generate_ass

ARTIFACT_DIR = "/home/manoj/.gemini/antigravity-ide/brain/33caecba-564d-4742-9ccb-3d23e407a89a"
os.makedirs(ARTIFACT_DIR, exist_ok=True)

# 1. Create a 3s dark luxury backdrop (1080x1920) with subtle gradient
BG_VIDEO = "/tmp/preview_backdrop.mp4"
if not os.path.exists(BG_VIDEO):
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=#0B0F17:s=1080x1920:d=3:r=30",
        "-vf", "drawbox=x=0:y=0:w=1080:h=1920:color=#1E293B@0.15:t=fill",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        BG_VIDEO
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

PRESETS_TO_PREVIEW = [
    ("hormozi", [
        {"word": "GET", "start": 0.0, "end": 0.3},
        {"word": "MORE", "start": 0.3, "end": 0.8},
        {"word": "CLICKS", "start": 0.8, "end": 1.4},
    ]),
    ("growth", [
        {"word": "SCALE", "start": 0.0, "end": 0.3},
        {"word": "REVENUE", "start": 0.3, "end": 0.8},
        {"word": "FAST", "start": 0.8, "end": 1.4},
    ]),
    ("coral", [
        {"word": "STOP", "start": 0.0, "end": 0.3},
        {"word": "DOING", "start": 0.3, "end": 0.8},
        {"word": "THIS", "start": 0.8, "end": 1.4},
    ]),
    ("sticker", [
        {"word": "REAL", "start": 0.0, "end": 0.3},
        {"word": "IMPACT", "start": 0.3, "end": 0.8},
        {"word": "NOW", "start": 0.8, "end": 1.4},
    ]),
    ("minimal", [
        {"word": "the secret", "start": 0.0, "end": 0.3},
        {"word": "to focus", "start": 0.3, "end": 0.8},
        {"word": "daily", "start": 0.8, "end": 1.4},
    ]),
    ("impact", [
        {"word": "WATCH", "start": 0.0, "end": 0.3},
        {"word": "THIS", "start": 0.3, "end": 0.8},
        {"word": "NOW", "start": 0.8, "end": 1.4},
    ]),
    ("creator", [
        {"word": "This changes", "start": 0.0, "end": 0.3},
        {"word": "EVERYTHING", "start": 0.3, "end": 0.8},
        {"word": "forever", "start": 0.8, "end": 1.4},
    ]),
    ("focus", [
        {"word": "The one", "start": 0.0, "end": 0.3},
        {"word": "formula", "start": 0.3, "end": 0.8},
        {"word": "that works", "start": 0.8, "end": 1.4},
    ]),
    ("badge", [
        {"word": "daily", "start": 0.0, "end": 0.3},
        {"word": "breakthrough", "start": 0.3, "end": 0.8},
        {"word": "framework", "start": 0.8, "end": 1.4},
    ]),
    ("neon", [
        {"word": "LEVEL", "start": 0.0, "end": 0.3},
        {"word": "UNLOCKED", "start": 0.3, "end": 0.8},
        {"word": "NOW", "start": 0.8, "end": 1.4},
    ]),
]

for preset_id, words in PRESETS_TO_PREVIEW:
    ass_path = f"/tmp/preview_{preset_id}.ass"
    generate_ass(words, {"preset": preset_id}, ass_path)
    
    # 1. Full 9:16 vertical render
    full_out = os.path.join(ARTIFACT_DIR, f"caption_{preset_id}_full.jpg")
    subprocess.run([
        "ffmpeg", "-y",
        "-i", BG_VIDEO,
        "-vf", f"ass={ass_path}",
        "-ss", "00:00:00.50",
        "-vframes", "1",
        full_out
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 2. Close-up crop focused on the subtitle banner (1080x420 at the subtitle baseline)
    crop_out = os.path.join(ARTIFACT_DIR, f"caption_{preset_id}_crop.jpg")
    subprocess.run([
        "ffmpeg", "-y",
        "-i", full_out,
        "-vf", "crop=1040:360:20:1300",
        crop_out
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print(f"Generated {preset_id}: {crop_out}")

print("All previews generated successfully!")

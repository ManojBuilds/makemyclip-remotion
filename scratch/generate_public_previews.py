#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modal")))
from ass_builder import generate_ass
from presets import PRESET_STYLES

PREVIEWS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "public", "previews"))
os.makedirs(PREVIEWS_DIR, exist_ok=True)

SOURCE_IMG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modal", "source_image.jpg"))
TMP_DIR = "/tmp/preview_render_tmp"
os.makedirs(TMP_DIR, exist_ok=True)

# 1. Create a 3s canvas video from source_image.jpg (720x1280, 30fps)
CANVAS_VIDEO = os.path.join(TMP_DIR, "source_canvas_720p.mp4")

print(f"🎬 Creating base canvas video from {SOURCE_IMG}...")
cmd_base = [
    "ffmpeg", "-y",
    "-loop", "1",
    "-i", SOURCE_IMG,
    "-f", "lavfi",
    "-i", "anullsrc=r=44100:cl=mono",
    "-t", "3.0",
    "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280",
    "-c:v", "libx264",
    "-preset", "fast",
    "-crf", "22",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac",
    CANVAS_VIDEO
]
subprocess.run(cmd_base, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
print("✅ Base canvas video created successfully.")

PRESETS_DATA = [
    ("hormozi", ["I", "have", "to", "be", "involved"]),
    ("impact", ["STOP", "SCROLLING", "NOW"]),
    ("growth", ["SCALE", "REVENUE", "FAST"]),
    ("coral", ["STOP", "DOING", "THIS"]),
    ("minimal", ["the secret", "to focus", "daily"]),
    ("sticker", ["REAL", "IMPACT", "NOW"]),
    ("creator", ["This changes", "EVERYTHING", ""]),
    ("cinema", ["the story of", "freedom", ""]),
    ("focus", ["The one", "formula", "that works"]),
    ("badge", ["my", "top", "three", "ideas"]),
    ("neon", ["LEVEL", "UNLOCKED", "NOW"]),
    ("luxury", ["The Art of", "Mastery", ""]),
    ("podcast", ["when I heard", "that question", ""]),
    ("bobby", ["never", "laughed at", "anybody"]),
    ("tom", ["THE", "ROOM", "AS IF"]),
    ("casey", ["I WANTED", "TO EXPLAIN", ""]),
    ("fred", ["Every", "time", "he's writing"]),
    ("sara", ["Because", "it's", "really the"]),
    ("billy", ["when someone", "doesn't", "want"]),
    ("unbox", ["CREATE", "PRESSURE", "THAT"]),
    ("aliabdlal", ["productive", "deep", "work"]),
]

if len(sys.argv) > 1:
    targets = set(sys.argv[1:])
    PRESETS_DATA = [p for p in PRESETS_DATA if p[0] in targets]

FONTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fonts"))

for preset_name, raw_words in PRESETS_DATA:
    words = [w for w in raw_words if w.strip()]
    
    transcript = [
        {
            "words": [
                {
                    "word": w,
                    "start": i * 0.70,
                    "end": (i + 1) * 0.70,
                    "speaker": "speaker_1",
                }
                for i, w in enumerate(words)
            ]
        }
    ]
    
    ass_path = os.path.join(TMP_DIR, f"{preset_name}.ass")
    generate_ass(transcript, {"preset": preset_name}, ass_path, crop_mode="reframe")
    
    out_webm = os.path.join(PREVIEWS_DIR, f"caption_{preset_name}.webm")
    out_mp4 = os.path.join(PREVIEWS_DIR, f"caption_{preset_name}.mp4")
    out_jpg = os.path.join(PREVIEWS_DIR, f"caption_{preset_name}.jpg")
    out_full_jpg = os.path.join(PREVIEWS_DIR, f"caption_{preset_name}_full.jpg")
    out_centered_jpg = os.path.join(PREVIEWS_DIR, f"caption_{preset_name}_centered.jpg")
    
    print(f"\n🔥 Burning preset [{preset_name}] to .webm and .mp4...")
    
    # 1. Burn WebM (VP9 + Opus)
    burn_cmd = [
        "ffmpeg", "-y",
        "-i", CANVAS_VIDEO,
        "-vf", f"ass={ass_path}:fontsdir={FONTS_DIR}",
        "-c:v", "libvpx-vp9",
        "-crf", "30",
        "-b:v", "0",
        "-deadline", "good",
        "-cpu-used", "4",
        "-c:a", "libopus",
        "-b:a", "96k",
        out_webm
    ]
    subprocess.run(burn_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # 1b. Burn MP4 (H.264 + AAC) for maximum compatibility
    mp4_cmd = [
        "ffmpeg", "-y",
        "-i", CANVAS_VIDEO,
        "-vf", f"ass={ass_path}:fontsdir={FONTS_DIR}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "96k",
        out_mp4
    ]
    subprocess.run(mp4_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    # 2. Extract snapshot JPG at active highlight
    snap_t = "1.75" if preset_name == "hormozi" else ("1.55" if preset_name == "badge" else "0.95")
    snap_cmd = [
        "ffmpeg", "-y",
        "-ss", snap_t,
        "-i", out_webm,
        "-frames:v", "1",
        "-update", "1",
        out_jpg
    ]
    subprocess.run(snap_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    # Full jpg copy
    shutil.copyfile(out_jpg, out_full_jpg)
    
    # Billy is near the top (y=0.18 -> y ≈ 230px), others near middle-bottom (y=0.65 -> y ≈ 830px)
    crop_y = 150 if preset_name == "billy" else 700
    crop_cmd = [
        "ffmpeg", "-y",
        "-ss", snap_t,
        "-i", out_webm,
        "-vf", f"crop=720:300:0:{crop_y}",
        "-frames:v", "1",
        "-update", "1",
        out_centered_jpg
    ]
    subprocess.run(crop_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # Also produce _v2 copies for cache busting
    for ext in [".webm", ".mp4", ".jpg"]:
        src_f = os.path.join(PREVIEWS_DIR, f"caption_{preset_name}{ext}")
        dst_v2 = os.path.join(PREVIEWS_DIR, f"caption_{preset_name}_v2{ext}")
        if os.path.exists(src_f):
            shutil.copyfile(src_f, dst_v2)
    
    print(f"   ✅ Saved: {out_webm} ({os.path.getsize(out_webm) / 1024:.1f} KB)")
    print(f"   ✅ Saved: {out_mp4} ({os.path.getsize(out_mp4) / 1024:.1f} KB)")
    print(f"   ✅ Poster snapshot: {out_jpg}")

print("\n🎉 ALL 21 PRESETS GENERATED IN .webm FORMAT SUCCESSFULLY IN public/previews!")

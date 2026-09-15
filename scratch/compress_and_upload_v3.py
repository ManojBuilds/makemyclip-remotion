#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modal")))
from r2_storage import upload_to_r2

load_dotenv()

if os.getenv("R2_BUCKET_NAME"):
    os.environ["R2_BUCKET_NAME"] = os.getenv("R2_BUCKET_NAME").strip('"').strip("'")
if not os.getenv("R2_ENDPOINT_URL") and os.getenv("R2_ACCOUNT_ID"):
    os.environ["R2_ENDPOINT_URL"] = f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com"

PREVIEWS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "public", "previews"))

def compress_webm(input_mp4, output_webm):
    print(f"📦 Compressing WebM: {input_mp4} -> {output_webm}...")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_mp4,
        "-vf", "scale=-2:640",
        "-c:v", "libvpx-vp9",
        "-crf", "32",
        "-b:v", "0",
        "-deadline", "good",
        "-cpu-used", "4",
        "-an",
        output_webm
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    size_kb = os.path.getsize(output_webm) / 1024.0
    print(f"   ✅ WebM size: {size_kb:.1f} KB")

def compress_mp4(input_mp4, output_mp4):
    print(f"📦 Compressing MP4: {input_mp4} -> {output_mp4}...")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_mp4,
        "-vf", "scale=-2:640",
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "28",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-an",
        output_mp4
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    size_kb = os.path.getsize(output_mp4) / 1024.0
    print(f"   ✅ MP4 size: {size_kb:.1f} KB")

def main():
    presets = ["sara", "unbox"]
    uploaded = {}
    
    for p in presets:
        src_mp4 = os.path.join(PREVIEWS_DIR, f"caption_{p}.mp4")
        src_jpg = os.path.join(PREVIEWS_DIR, f"caption_{p}.jpg")
        
        v3_webm = os.path.join(PREVIEWS_DIR, f"caption_{p}_v3.webm")
        v3_mp4 = os.path.join(PREVIEWS_DIR, f"caption_{p}_v3.mp4")
        v3_jpg = os.path.join(PREVIEWS_DIR, f"caption_{p}_v3.jpg")
        
        # 1. Compress
        compress_webm(src_mp4, v3_webm)
        compress_mp4(src_mp4, v3_mp4)
        if os.path.exists(src_jpg):
            shutil.copyfile(src_jpg, v3_jpg)
            
        # 2. Upload to R2
        for ext, local_path in [(".webm", v3_webm), (".mp4", v3_mp4), (".jpg", v3_jpg)]:
            if os.path.exists(local_path):
                key = f"previews/caption_{p}_v3{ext}"
                print(f"📤 Uploading {local_path} -> {key}...")
                url = upload_to_r2(local_path, key)
                print(f"   🚀 URL: {url}")
                uploaded[f"{p}{ext}"] = url
                
    print("\n🎉 All v3 assets compressed and uploaded successfully!")
    for k, v in uploaded.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import os
import sys
import subprocess
import json
from dotenv import load_dotenv

# Add modal directory to python path to import r2_storage
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modal")))
from r2_storage import upload_to_r2

load_dotenv()

# Clean bucket name configuration
if os.getenv("R2_BUCKET_NAME"):
    os.environ["R2_BUCKET_NAME"] = os.getenv("R2_BUCKET_NAME").strip('"').strip("'")
if not os.getenv("R2_ENDPOINT_URL") and os.getenv("R2_ACCOUNT_ID"):
    os.environ["R2_ENDPOINT_URL"] = f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com"

PRESETS = ["cinema", "creator", "focus", "impact", "neon"]
INPUT_DIR = "test_outputs"
OUTPUT_DIR = "scratch/optimized_captions"

def optimize_mp4(input_path, output_path):
    print(f"⚡ Optimizing MP4: {input_path} -> {output_path}...")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", "scale=-2:480",
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "30",
        "-movflags", "+faststart",
        "-an",
        output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    size_kb = os.path.getsize(output_path) / 1024.0
    print(f"   ✅ Optimized MP4 size: {size_kb:.1f} KB")

def convert_to_webp(input_path, output_path):
    print(f"🖼️ Converting to WebP: {input_path} -> {output_path}...")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vcodec", "libwebp",
        "-filter_complex", "[0:v] fps=15,scale=360:-1:flags=lanczos[v]",
        "-map", "[v]",
        "-loop", "0",
        "-qscale", "65",
        "-preset", "default",
        "-an",
        output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    size_kb = os.path.getsize(output_path) / 1024.0
    print(f"   ✅ WebP size: {size_kb:.1f} KB")

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("=== STARTING CAPTION PREVIEW OPTIMIZATION & UPLOAD ===")
    
    results = {}
    
    for preset in PRESETS:
        input_mp4 = os.path.join(INPUT_DIR, f"{preset}.mp4")
        if not os.path.exists(input_mp4):
            print(f"⚠️ Warning: {input_mp4} does not exist. Skipping.")
            continue
            
        opt_mp4 = os.path.join(OUTPUT_DIR, f"{preset}_opt.mp4")
        opt_webp = os.path.join(OUTPUT_DIR, f"{preset}.webp")
        
        # 1. Optimize MP4
        optimize_mp4(input_mp4, opt_mp4)
        
        # 2. Convert to WebP
        convert_to_webp(input_mp4, opt_webp)
        
        # 3. Upload MP4
        mp4_key = f"previews/black_template_{preset}.mp4"
        print(f"📤 Uploading MP4 to R2 key: {mp4_key}...")
        mp4_url = upload_to_r2(opt_mp4, mp4_key)
        print(f"   URL: {mp4_url}")
        
        # 4. Upload WebP
        webp_key = f"previews/black_template_{preset}.webp"
        print(f"📤 Uploading WebP to R2 key: {webp_key}...")
        webp_url = upload_to_r2(opt_webp, webp_key)
        print(f"   URL: {webp_url}")
        
        results[preset] = {
            "mp4_url": mp4_url,
            "webp_url": webp_url,
            "mp4_size_kb": f"{os.path.getsize(opt_mp4)/1024:.1f} KB",
            "webp_size_kb": f"{os.path.getsize(opt_webp)/1024:.1f} KB",
        }
        
    print("\n🎉 ALL ASSETS CONVERTED, OPTIMIZED, AND UPLOADED SUCCESSFULLY!\n")
    print(json.dumps(results, indent=2))
    
    print("\nTypeScript PREVIEW_IMAGES config snippet:\n")
    print("export const PREVIEW_IMAGES: Record<string, string> = {")
    for preset, data in results.items():
        print(f'  {preset}: "{data["webp_url"]}",')
    print("}")

if __name__ == "__main__":
    main()

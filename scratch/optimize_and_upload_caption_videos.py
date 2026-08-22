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

# Default to CLI arguments if provided, else "badge"
target = sys.argv[1:] if len(sys.argv) > 1 else ["badge"]
PRESETS = target
INPUT_DIR = "modal/test_outputs"
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
        
    print("\n🎉 CONVERTED, OPTIMIZED, AND UPLOADED SUCCESSFULLY!\n")
    print(json.dumps(results, indent=2))
    
    # Update lib/config.ts
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lib", "config.ts"))
    if os.path.exists(config_path) and results:
        print(f"\n📝 Updating {config_path}...")
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()

        import re
        for preset, data in results.items():
            # Update or insert in PREVIEW_IMAGES
            if f"{preset}:" in content:
                content = re.sub(
                    rf'({preset}:\s*")[^"]*(")',
                    rf'\g<1>{data["webp_url"]}\g<2>',
                    content,
                )
            else:
                content = re.sub(
                    r'(export const PREVIEW_IMAGES:\s*Record<string,\s*string>\s*=\s*\{)',
                    rf'\g<1>\n  {preset}: "{data["webp_url"]}",',
                    content,
                )

            # Update or insert in PREVIEW_VIDEOS
            if f"{preset}:" in content:
                content = re.sub(
                    rf'({preset}:\s*")[^"]*(")',
                    rf'\g<1>{data["mp4_url"]}\g<2>',
                    content,
                )
            else:
                content = re.sub(
                    r'(export const PREVIEW_VIDEOS:\s*Record<string,\s*string>\s*=\s*\{)',
                    rf'\g<1>\n  {preset}: "{data["mp4_url"]}",',
                    content,
                )

        with open(config_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("✅ lib/config.ts successfully updated!")

if __name__ == "__main__":
    main()

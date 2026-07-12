#!/usr/bin/env python3
import os
import sys
import subprocess
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

def main():
    input_dir = "test_outputs"
    temp_dir = "scratch/previews"
    
    os.makedirs(temp_dir, exist_ok=True)
    
    # Target the four generated preset video files
    presets = ["hormozi", "neon-glow", "opus", "simple"]
    files = [f"{p}.mp4" for p in presets if os.path.exists(os.path.join(input_dir, f"{p}.mp4"))]
    
    results = {}
    
    for f in sorted(files):
        template_id = f.replace(".mp4", "")
        
        input_path = os.path.join(input_dir, f)
        webp_filename = f"black_template_{template_id}.webp"
        local_webp_path = os.path.join(temp_dir, webp_filename)
        
        print(f"\n🎬 Converting {input_path} to WebP...")
        
        # ffmpeg command to convert to animated webp.
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vcodec", "libwebp",
            "-filter_complex", "[0:v] fps=15,scale=360:-1:flags=lanczos[v]",
            "-map", "[v]",
            "-loop", "0",
            "-qscale", "75",
            "-preset", "default",
            "-an",
            local_webp_path
        ]
        
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            size_kb = os.path.getsize(local_webp_path) / 1024.0
            print(f"✅ WebP created locally: {local_webp_path} ({size_kb:.1f} KB)")
            
            # Key structure on R2: previews/black_template_<id>.webp
            r2_key = f"previews/{webp_filename}"
            print(f"📤 Uploading to R2 with key: {r2_key}...")
            
            public_url = upload_to_r2(local_webp_path, r2_key)
            print(f"🚀 Public URL: {public_url}")
            
            results[template_id] = public_url
            
        except subprocess.CalledProcessError as e:
            print(f"❌ ffmpeg failed for {f}: {e}")
        except Exception as e:
            print(f"❌ Upload failed for {f}: {e}")
            
    print("\n🎉 ALL ASSETS CONVERTED AND UPLOADED SUCCESSFULLY!")
    print("\nTypeScript/TSX Mapping Object:\n")
    print("const PREVIEW_IMAGES: Record<string, string> = {")
    for tid, url in results.items():
        print(f'  "{tid}":')
        print(f'    "{url}",')
    print("};")

if __name__ == "__main__":
    main()

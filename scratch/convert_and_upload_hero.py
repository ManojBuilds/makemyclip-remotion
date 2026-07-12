#!/usr/bin/env python3
import os
import sys
import subprocess
from dotenv import load_dotenv

# Add modal directory to python path to import r2_storage
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modal")))
from r2_storage import upload_to_r2, get_r2_client

load_dotenv()

# Clean bucket name configuration
if os.getenv("R2_BUCKET_NAME"):
    os.environ["R2_BUCKET_NAME"] = os.getenv("R2_BUCKET_NAME").strip('"').strip("'")
if not os.getenv("R2_ENDPOINT_URL") and os.getenv("R2_ACCOUNT_ID"):
    os.environ["R2_ENDPOINT_URL"] = f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com"

HERO_CLIPS = [
    {
        "name": "hero_interview_preview",
        "key": "hero_interview_preview.mp4",
    },
    {
        "name": "hero_course_preview",
        "key": "hero_course_preview.mp4",
    },
    {
        "name": "hero_panel_preview",
        "key": "hero_panel_preview.mp4",
    },
    {
        "name": "hero_podcast_preview",
        "key": "hero_podcast_preview.mp4",
    },
    {
        "name": "hero_ufc_preview",
        "key": "hero_ufc_preview.mp4",
    },
]

def main():
    temp_dir = "scratch/hero_temp"
    os.makedirs(temp_dir, exist_ok=True)
    
    s3 = get_r2_client()
    bucket_name = os.environ.get("R2_BUCKET_NAME", "makemyclip")
    
    results = {}
    
    for clip in HERO_CLIPS:
        name = clip["name"]
        key = clip["key"]
        
        local_mp4_path = os.path.join(temp_dir, f"{name}.mp4")
        local_webp_path = os.path.join(temp_dir, f"{name}.webp")
        
        print(f"\n📥 Downloading {key} from R2 bucket {bucket_name}...")
        try:
            s3.download_file(bucket_name, key, local_mp4_path)
            print(f"✅ Downloaded to {local_mp4_path}")
        except Exception as e:
            print(f"❌ Failed to download {key} from R2: {e}")
            continue
            
        print(f"🎬 Converting {local_mp4_path} to WebP...")
        
        # ffmpeg command to convert to animated webp.
        cmd = [
            "ffmpeg", "-y",
            "-i", local_mp4_path,
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
            
            # Upload to a separate folder: hero_previews/
            r2_key = f"hero_previews/{name}.webp"
            print(f"📤 Uploading to R2 with key: {r2_key}...")
            
            public_url = upload_to_r2(local_webp_path, r2_key)
            print(f"🚀 Public URL: {public_url}")
            
            results[name] = public_url
            
        except subprocess.CalledProcessError as e:
            print(f"❌ ffmpeg failed for {name}: {e}")
        except Exception as e:
            print(f"❌ Upload failed for {name}: {e}")
            
    print("\n🎉 ALL HERO ASSETS CONVERTED AND UPLOADED SUCCESSFULLY!")
    print("\nMapping Object:\n")
    for key, url in results.items():
        print(f'"{key}": "{url}",')

if __name__ == "__main__":
    main()

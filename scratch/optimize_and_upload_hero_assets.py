#!/usr/bin/env python3
import os
import sys
import subprocess
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modal")))
from r2_storage import upload_to_r2

load_dotenv()

# Clean bucket name configuration
if os.getenv("R2_BUCKET_NAME"):
    os.environ["R2_BUCKET_NAME"] = os.getenv("R2_BUCKET_NAME").strip('"').strip("'")
if not os.getenv("R2_ENDPOINT_URL") and os.getenv("R2_ACCOUNT_ID"):
    os.environ["R2_ENDPOINT_URL"] = f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com"

VIDEOS = {
    "course": {
        "video": "downloads/result_course_presentation_captioned.mp4",
        "optimized_video": "downloads/hero_course_preview.mp4",
        "poster": "downloads/poster_course.jpg",
        "video_key": "hero_course_preview.mp4",
        "poster_key": "hero_course_poster.jpg"
    },
    "podcast": {
        "video": "downloads/result_podcast_reframe_captioned.mp4",
        "optimized_video": "downloads/hero_podcast_preview.mp4",
        "poster": "downloads/poster_podcast.jpg",
        "video_key": "hero_podcast_preview.mp4",
        "poster_key": "hero_podcast_poster.jpg"
    },
    "ufc": {
        "video": "downloads/the_most_epic_ufc_promo_ever__qcu0r (2).mp4",
        "optimized_video": "downloads/hero_ufc_preview.mp4",
        "poster": "downloads/poster_ufc.jpg",
        "video_key": "hero_ufc_preview.mp4",
        "poster_key": "hero_ufc_poster.jpg"
    }
}

def optimize_video(input_path, output_path):
    print(f"⚡ Optimizing {input_path} to {output_path} (480p, no audio, low bitrate)...")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", "scale=-2:480",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "28",
        "-movflags", "+faststart",
        "-an",
        output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    size_kb = os.path.getsize(output_path) / 1024.0
    print(f"✅ Optimized! Size: {size_kb:.1f} KB")

def extract_poster(video_path, poster_path):
    print(f"🖼️ Extracting thumbnail at 1s from {video_path} to {poster_path}...")
    cmd = [
        "ffmpeg", "-y",
        "-ss", "00:00:01",
        "-i", video_path,
        "-vframes", "1",
        "-qscale:v", "2",
        poster_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print(f"✅ Extracted: {poster_path}")

def main():
    print("=== STARTING HERO PREVIEW OPTIMIZATION & UPLOAD ===")
    
    results = {}
    
    for name, paths in VIDEOS.items():
        if not os.path.exists(paths["video"]):
            print(f"❌ Error: Video {paths['video']} does not exist.")
            continue
            
        # 1. Optimize video
        optimize_video(paths["video"], paths["optimized_video"])
        
        # 2. Extract poster
        extract_poster(paths["video"], paths["poster"])
        
        # 3. Upload optimized video
        print(f"📤 Uploading optimized video to R2 as {paths['video_key']}...")
        video_url = upload_to_r2(paths["optimized_video"], paths["video_key"])
        print(f"✅ Video URL: {video_url}")
        
        # 4. Upload poster
        print(f"📤 Uploading poster to R2 as {paths['poster_key']}...")
        poster_url = upload_to_r2(paths["poster"], paths["poster_key"])
        print(f"✅ Poster URL: {poster_url}")
        
        results[name] = {
            "video_url": video_url,
            "poster_url": poster_url
        }
        
    print("\n🎉 ALL OPTIMIZED ASSETS UPLOADED SUCCESSFULLY!")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    import json
    main()

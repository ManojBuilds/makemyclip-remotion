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
    "monologue": {
        "video": "downloads/result_monologue_reframe_captioned.mp4",
        "poster": "downloads/poster_monologue.jpg",
        "video_key": "hero_monologue_captioned.mp4",
        "poster_key": "hero_monologue_poster.jpg"
    },
    "interview": {
        "video": "downloads/result_interview_split_captioned.mp4",
        "poster": "downloads/poster_interview.jpg",
        "video_key": "hero_interview_captioned.mp4",
        "poster_key": "hero_interview_poster.jpg"
    },
    "course": {
        "video": "downloads/result_course_presentation_captioned.mp4",
        "poster": "downloads/poster_course.jpg",
        "video_key": "hero_course_captioned.mp4",
        "poster_key": "hero_course_poster.jpg"
    },
    "panel": {
        "video": "downloads/result_panel_letterbox_captioned.mp4",
        "poster": "downloads/poster_panel.jpg",
        "video_key": "hero_panel_captioned.mp4",
        "poster_key": "hero_panel_poster.jpg"
    }
}

def extract_poster(video_path, poster_path):
    print(f"🖼️ Extracting first frame from {video_path} to {poster_path}...")
    cmd = [
        "ffmpeg", "-y",
        "-ss", "00:00:00",
        "-i", video_path,
        "-vframes", "1",
        "-qscale:v", "2",
        poster_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print(f"✅ Extracted: {poster_path}")

def main():
    print("=== STARTING HERO ASSET PREPARATION & UPLOAD ===")
    
    results = {}
    
    for name, paths in VIDEOS.items():
        if not os.path.exists(paths["video"]):
            print(f"❌ Error: Video {paths['video']} does not exist. Run the captioning scripts first.")
            continue
            
        # 1. Extract first frame as poster
        extract_poster(paths["video"], paths["poster"])
        
        # 2. Upload video
        print(f"📤 Uploading video {paths['video']} as {paths['video_key']}...")
        video_url = upload_to_r2(paths["video"], paths["video_key"])
        print(f"✅ Video URL: {video_url}")
        
        # 3. Upload poster
        print(f"📤 Uploading poster {paths['poster']} as {paths['poster_key']}...")
        poster_url = upload_to_r2(paths["poster"], paths["poster_key"])
        print(f"✅ Poster URL: {poster_url}")
        
        results[name] = {
            "video_url": video_url,
            "poster_url": poster_url
        }
        
    print("\n🎉 ALL ASSETS UPLOADED SUCCESSFULLY!")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    import json
    main()

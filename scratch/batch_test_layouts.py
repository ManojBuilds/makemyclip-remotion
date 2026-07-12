#!/usr/bin/env python3
import os
import sys
import requests
from dotenv import load_dotenv

# Add modal directory to python path for R2 upload helper
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modal")))

from r2_storage import upload_to_r2

load_dotenv()

MODAL_ENDPOINT = "https://ms8460149--makemyclip-ai-rendering-aireframe-reframe.modal.run"

# Ensure bucket name configuration is clean
if os.getenv("R2_BUCKET_NAME"):
    os.environ["R2_BUCKET_NAME"] = os.getenv("R2_BUCKET_NAME").strip('"').strip("'")
if not os.getenv("R2_ENDPOINT_URL") and os.getenv("R2_ACCOUNT_ID"):
    os.environ["R2_ENDPOINT_URL"] = f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com"

# The 4 test cases mapped to the local downloaded filenames and expected layouts
TESTS = [
    {
        "name": "Single Speaker Monologue",
        "local_path": "downloads/yt_monologue.mp4",
        "r2_key": "test_yt_monologue.mp4",
        "expected_layout": "reframe",
        "start_time": 0.0,
        "end_time": 10.0,
        "filename": "result_monologue_reframe.mp4"
    },
    {
        "name": "Remote Interview (Split-Screen)",
        "local_path": "downloads/yt_interview.mp4",
        "r2_key": "test_yt_interview.mp4",
        "expected_layout": "split",
        "start_time": 0.0,
        "end_time": 10.0,
        "filename": "result_interview_split.mp4"
    },
    {
        "name": "Course Presentation (Screen Share + Webcam)",
        "local_path": "downloads/yt_course.mp4",
        "r2_key": "test_yt_course.mp4",
        "expected_layout": "course",
        "start_time": 0.0,
        "end_time": 10.0,
        "filename": "result_course_presentation.mp4"
    },
    {
        "name": "News Panel / Debate (Multi-speaker)",
        "local_path": "downloads/yt_panel.mp4",
        "r2_key": "test_yt_panel.mp4",
        "expected_layout": "letterbox",
        "start_time": 0.0,
        "end_time": 10.0,
        "filename": "result_panel_letterbox.mp4"
    }
]

print("=== STARTING BATCH YOUTUBE LAYOUT TESTS (crop_mode='auto') ===")

missing_files = []
for t in TESTS:
    if not os.path.exists(t["local_path"]):
        missing_files.append(t["local_path"])

if missing_files:
    print("\n❌ Error: The following required files are missing. Please download them first:")
    for f in missing_files:
        print(f"  - {f}")
    print("\nSee your terminal conversation for the exact yt-dlp commands to download them.")
    sys.exit(1)

for t in TESTS:
    print(f"\n🚀 Processing: {t['name']}")
    
    # 1. Upload the raw landscape clip to R2
    print(f"Uploading {t['local_path']} to Cloudflare R2...")
    try:
        public_url = upload_to_r2(t["local_path"], t["r2_key"])
        print(f"✅ R2 Upload complete: {public_url}")
    except Exception as e:
        print(f"❌ R2 Upload failed: {e}")
        continue
    
    # 2. Invoke the Modal AIReframe endpoint with crop_mode="auto"
    payload = {
        "video_url": public_url,
        "start_time": t["start_time"],
        "end_time": t["end_time"],
        "fps": 25,
        "styling": None,
        "transcript": None,
        "show_watermark": False,
        "crop_mode": "auto",
    }
    
    print(f"Calling Modal endpoint: {MODAL_ENDPOINT}...")
    try:
        response = requests.post(MODAL_ENDPOINT, json=payload, timeout=600)
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        continue

    if response.status_code != 200:
        print(f"❌ HTTP Error {response.status_code}: {response.text}")
        continue

    res = response.json()
    if not res.get("success"):
        print(f"❌ Modal processing failed: {res}")
        continue

    detected_layout = res.get("crop_mode")
    output_video_url = res.get("original_video_url")
    
    print(f"🎉 Success!")
    print(f"  - Expected Layout: {t['expected_layout']}")
    print(f"  - Detected Layout: {detected_layout}")
    
    # Verify matches expectation
    if detected_layout == t["expected_layout"]:
        print("  - Status: ✅ MATCHED")
    else:
        print("  - Status: ⚠️ MISMATCHED")
        
    print(f"Downloading vertical video to downloads/{t['filename']}...")
    video_res = requests.get(output_video_url, stream=True)
    out_path = os.path.join("downloads", t["filename"])
    with open(out_path, "wb") as f:
        for chunk in video_res.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    print(f"💾 Saved vertical output to: {out_path}")

print("\n=== BATCH TESTS COMPLETED ===")

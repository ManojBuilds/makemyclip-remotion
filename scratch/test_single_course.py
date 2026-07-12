#!/usr/bin/env python3
import os
import sys
import requests
from dotenv import load_dotenv

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modal"))
)


load_dotenv()

MODAL_ENDPOINT = (
    "https://ms8460149--makemyclip-ai-rendering-aireframe-reframe.modal.run"
)


t = {
    "name": "Course Presentation (Screen Share + Webcam)",
    "local_path": "downloads/yt_course.mp4",
    "r2_key": "test_yt_course.mp4",
    "expected_layout": "course",
    "start_time": 0.0,
    "end_time": 10.0,
    "filename": "result_course_presentation.mp4",
}

print(f"\n🚀 Processing: {t['name']}")
public_url = "https://pub-dab84dec13074258806f788a00943c46.r2.dev/test_yt_course.mp4"


payload = {
    "video_url": public_url,
    "start_time": t["start_time"],
    "end_time": t["end_time"],
    "fps": 25,
    "styling": None,
    "transcript": None,
    "show_watermark": False,
    "crop_mode": "course",
}

print(f"Calling Modal endpoint: {MODAL_ENDPOINT}...")
response = requests.post(MODAL_ENDPOINT, json=payload, timeout=600)

if response.status_code != 200:
    print(f"❌ HTTP Error {response.status_code}: {response.text}")
    sys.exit(1)

res = response.json()
if not res.get("success"):
    print(f"❌ Modal processing failed: {res}")
    sys.exit(1)

detected_layout = res.get("crop_mode")
output_video_url = res.get("original_video_url")

print(f"🎉 Success!")
print(f"  - Expected Layout: {t['expected_layout']}")
print(f"  - Detected Layout: {detected_layout}")

if detected_layout == t["expected_layout"]:
    print("  - Status: ✅ MATCHED")
else:
    print("  - Status: ⚠️ MISMATCHED")

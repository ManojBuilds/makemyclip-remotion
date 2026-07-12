#!/usr/bin/env python3
import os
import sys
import requests
from dotenv import load_dotenv

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modal"))
)
from r2_storage import upload_to_r2

load_dotenv()

MODAL_ENDPOINT = (
    "https://ms8460149--makemyclip-ai-rendering-aireframe-reframe.modal.run"
)

if os.getenv("R2_BUCKET_NAME"):
    os.environ["R2_BUCKET_NAME"] = os.getenv("R2_BUCKET_NAME").strip('"').strip("'")
if not os.getenv("R2_ENDPOINT_URL") and os.getenv("R2_ACCOUNT_ID"):
    os.environ["R2_ENDPOINT_URL"] = (
        f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com"
    )

t = {
    "name": "Kill Tony 20s Cut",
    "local_path": "downloads/kill_tony.mp4",
    "r2_key": "test_kill_tony_20s.mp4",
    "expected_layout": "letterbox",
    "start_time": 0.0,
    "end_time": 20.0,
    "filename": "result_kill_tony_letterbox.mp4",
}

print(f"\n🚀 Processing: {t['name']}")
print(f"Uploading {t['local_path']} to Cloudflare R2...")
public_url = upload_to_r2(t["local_path"], t["r2_key"])
print(f"✅ R2 Upload complete: {public_url}")

payload = {
    "video_url": public_url,
    "start_time": t["start_time"],
    "end_time": t["end_time"],
    "fps": 25,
    "styling": None,
    "transcript": None,
    "show_watermark": False,
    "crop_mode": "letterbox",
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
print(f"  - Detected Layout: {detected_layout}")

# Download the video
print(f"Downloading vertical video to downloads/{t['filename']}...")
video_res = requests.get(output_video_url, stream=True)
out_path = os.path.join("downloads", t["filename"])
with open(out_path, "wb") as f:
    for chunk in video_res.iter_content(chunk_size=8192):
        if chunk:
            f.write(chunk)
print(f"💾 Saved vertical output to: {out_path}")

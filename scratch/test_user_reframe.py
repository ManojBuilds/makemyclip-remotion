#!/usr/bin/env python3
import os
import sys
import requests
from dotenv import load_dotenv

# Load local environment variables from workspace root
load_dotenv()

MODAL_ENDPOINT = os.getenv(
    "MODAL_REFRAME_ENDPOINT",
    "https://ms8460149--makemyclip-ai-rendering-aireframe-reframe.modal.run",
)

youtube_url = "https://www.youtube.com/watch?v=__fmDj0ZJ1Q"
output_local_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "downloads",
    "lamborghini_cake_reframed.mp4",
)

# Ensure downloads directory exists
os.makedirs(os.path.dirname(output_local_path), exist_ok=True)

print("--- MakeMyClip AI Reframe Direct Youtube Tester ---")
print(f"YouTube Video URL: {youtube_url}")
print(f"Target local output path: {output_local_path}")
print(f"Modal endpoint: {MODAL_ENDPOINT}")

# Call Modal AI Reframe Endpoint
payload = {
    "video_url": youtube_url,
    "start_time": 194.0,
    "end_time": 204.0,
    "fps": 25,
    "styling": None,
    "transcript": None,
    "show_watermark": True,
    "crop_mode": "auto",  # Force single-speaker tracking layout to test direct cuts
}

print(f"Sending reframe request to Modal endpoint...")
print(f"Payload: {payload}")

try:
    response = requests.post(MODAL_ENDPOINT, json=payload, timeout=600)
except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)

if response.status_code != 200:
    print(f"❌ Error calling Modal! Status code: {response.status_code}")
    print(response.text)
    sys.exit(1)

result = response.json()
print("\n--- Modal Response ---")
print(result)

if not result.get("success"):
    print("❌ Reframe failed according to Modal response.")
    sys.exit(1)

reframed_url = result.get("original_video_url")
detected_layout = result.get("crop_mode")
source_w = result.get("source_width")
source_h = result.get("source_height")
print(f"\n🎉 Success! Detected Layout: {detected_layout}")
print(f"Downloaded Source Video Quality: {source_w}x{source_h}")
print(f"Reframed Video URL: {reframed_url}")

# Download reframed video
print(f"Downloading reframed vertical video from {reframed_url}...")
r = requests.get(reframed_url, stream=True)
with open(output_local_path, "wb") as f:
    for chunk in r.iter_content(chunk_size=8192):
        if chunk:
            f.write(chunk)

print(f"💾 Saved reframed vertical video to: {output_local_path}")

import os
import requests
import time
from dotenv import load_dotenv

# Load local environment variables
load_dotenv()

MODAL_ENDPOINT = "https://ms8460149--makemyclip-ai-rendering-aireframe-reframe.modal.run"

video_name = "input_5s"
public_url = "https://www.youtube.com/watch?v=M-ZH3psUbfU"

downloads_dir = os.path.join(os.path.dirname(__file__), "..", "downloads")
os.makedirs(downloads_dir, exist_ok=True)

output_local_path = os.path.join(downloads_dir, f"{video_name}_output.mp4")

print(f"--- MakeMyClip AI Reframe Tester for {video_name} ---")
print(f"URL: {public_url}")

payload = {
    "video_url": public_url,
    "start_time": 335.47,
    "end_time": 387.241,
    "fps": 25,
    "styling": None,
    "transcript": None,
    "show_watermark": False,
    "crop_mode": "reframe",
}

start_time = time.time()
try:
    response = requests.post(MODAL_ENDPOINT, json=payload, timeout=600)
except Exception as e:
    print(f"[{video_name}] Connection failed: {e}")
    exit(1)

duration = time.time() - start_time
if response.status_code != 200:
    print(f"[{video_name}] Error calling Modal! Status code: {response.status_code}")
    print(response.text)
    exit(1)

result = response.json()
if not result.get("success"):
    print(f"[{video_name}] Reframe failed according to Modal response: {result}")
    exit(1)

reframed_url = result.get("original_video_url")
print(f"[{video_name}] Reframed Video URL: {reframed_url}")
print(f"[{video_name}] Downloading reframed video to {output_local_path} (Took {duration:.2f}s)...")

try:
    r = requests.get(reframed_url, stream=True)
    with open(output_local_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    print(f"[{video_name}] Success! Saved to: {output_local_path}")
except Exception as e:
    print(f"[{video_name}] Failed to download output file: {e}")

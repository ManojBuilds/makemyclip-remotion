import os
import requests
from dotenv import load_dotenv

# Load local environment variables
load_dotenv()

MODAL_ENDPOINT = os.getenv(
    "MODAL_REFRAME_ENDPOINT",
    "https://ms8460149--makemyclip-ai-rendering-aireframe-reframe.modal.run",
)
# public_url = "https://pub-dab84dec13074258806f788a00943c46.r2.dev/trimmed_video.webm"
public_url = (
    "https://pub-dab84dec13074258806f788a00943c46.r2.dev/clip2.mp4"  # letterbox
)
output_local_path = (
    "/home/manoj-kumar/Developer/makemyclip-remotion/downloads/letterbox_output.mp4"
)

print("--- MakeMyClip AI Reframe Direct Tester ---")
print(f"Using video URL: {public_url}")

# Call Modal AI Reframe Endpoint
payload = {
    "video_url": public_url,
    "start_time": 0.0,
    "end_time": 10.0,
    "fps": 25,
    "styling": None,
    "transcript": None,
    "show_watermark": False,
    "crop_mode": "letterbox",
}

print(f"Sending reframe request to Modal endpoint: {MODAL_ENDPOINT}...")
print(f"Payload: {payload}")

try:
    response = requests.post(MODAL_ENDPOINT, json=payload, timeout=600)
except Exception as e:
    print(f"Connection failed: {e}")
    exit(1)

if response.status_code != 200:
    print(f"Error calling Modal! Status code: {response.status_code}")
    print(response.text)
    exit(1)

result = response.json()
print("Modal Response:")
print(result)

if not result.get("success"):
    print("Reframe failed according to Modal response.")
    exit(1)

reframed_url = result.get("original_video_url")
print(f"Reframed Video URL: {reframed_url}")

# Download reframed video
print(f"Downloading reframed vertical video from {reframed_url}...")
r = requests.get(reframed_url, stream=True)
with open(output_local_path, "wb") as f:
    for chunk in r.iter_content(chunk_size=8192):
        if chunk:
            f.write(chunk)

print(f"Success! Reframed vertical video saved to: {output_local_path}")

import os
import requests
import json
import sys

# Parse .env file manually
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(env_path):
    print(f"Loading environment from {env_path}...")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

# Construct R2_ENDPOINT_URL from R2_ACCOUNT_ID if not present
if not os.getenv("R2_ENDPOINT_URL") and os.getenv("R2_ACCOUNT_ID"):
    os.environ["R2_ENDPOINT_URL"] = f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com"

# Clean up R2_BUCKET_NAME quotes if they exist in env
if os.getenv("R2_BUCKET_NAME"):
    os.environ["R2_BUCKET_NAME"] = os.getenv("R2_BUCKET_NAME").strip('"').strip("'")

# Ensure modal directory is in python path to use R2 uploader
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modal")))
from r2_storage import upload_to_r2

video_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "downloads", "kill_tony.mp4"))
if not os.path.exists(video_path):
    print(f"Error: Video file not found at {video_path}")
    sys.exit(1)

print("Uploading video to R2...")
public_url = upload_to_r2(video_path, "test/kill_tony.mp4")
print(f"Public video URL: {public_url}")

endpoint = os.environ.get("MODAL_REFRAME_ENDPOINT")
print(f"Calling endpoint: {endpoint}")

payload = {
    "video_url": public_url,
    "start_time": 0.0,
    "end_time": 20.0,
    "crop_mode": "auto"
}

response = requests.post(endpoint, json=payload)
print(f"Response Status Code: {response.status_code}")
try:
    result = response.json()
    print("Response JSON:")
    print(json.dumps(result, indent=2))
except Exception as e:
    print(f"Failed to parse JSON response: {e}")
    print(response.text)

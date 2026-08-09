import json
import time
import requests

ANALYZER_ENDPOINT = "https://ms8460149--makemyclip-ai-rendering-videoanalyzer-analyze.modal.run"
YT_VIDEO_URL = "https://www.youtube.com/watch?v=xEjGn_V7KnU"

payload = {
    "video_url": YT_VIDEO_URL,
    "project_id": "test_yt_user_5s",
    "duration": 5.0,
    "detect_skip": 5
}

print(f"--> Sending VideoAnalyzer POST request for YouTube URL...")
print(f"URL: {YT_VIDEO_URL}")

t0 = time.time()
try:
    resp = requests.post(ANALYZER_ENDPOINT, json=payload, timeout=300)
    elapsed = time.time() - t0
    print(f"\n<-- Response Received in {elapsed:.2f}s (Status {resp.status_code}):")
    print(json.dumps(resp.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")

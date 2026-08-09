import json
import time
import requests

ANALYZER_ENDPOINT = "https://ms8460149--makemyclip-ai-rendering-videoanalyzer-analyze.modal.run"
VIDEO_URL = "https://pub-dab84dec13074258806f788a00943c46.r2.dev/test/input_5s.webm"

payload = {
    "video_url": VIDEO_URL,
    "project_id": "test_input5s_norm",
    "duration": 5.0,
    "detect_skip": 5
}

print(f"--> Sending VideoAnalyzer POST request to {ANALYZER_ENDPOINT}...")
print(f"Payload: {json.dumps(payload, indent=2)}")

t0 = time.time()
try:
    resp = requests.post(ANALYZER_ENDPOINT, json=payload, timeout=300)
    elapsed = time.time() - t0
    print(f"\n<-- Response Received in {elapsed:.2f}s (Status {resp.status_code}):")
    print(json.dumps(resp.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")

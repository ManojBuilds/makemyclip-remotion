import json
import time
import requests

ANALYZER_ENDPOINT = "https://ms8460149--makemyclip-ai-rendering-videoanalyzer-analyze.modal.run"
VIDEO_URL = "https://www.youtube.com/watch?v=nYOzBYN8K9k"
START_TIME = 2588.0
END_TIME = 2598.0
PROJECT_ID = f"test_clip_{int(START_TIME)}_{int(END_TIME)}"

payload = {
    "video_url": VIDEO_URL,
    "project_id": PROJECT_ID,
    "start_time": START_TIME,
    "end_time": END_TIME,
    "detect_skip": 5,
}

print(f"--> Sending VideoAnalyzer request for {START_TIME}s - {END_TIME}s (10s duration)...")
print(f"Payload: {json.dumps(payload, indent=2)}")

t0 = time.time()
try:
    resp = requests.post(ANALYZER_ENDPOINT, json=payload, timeout=600)
    elapsed = time.time() - t0
    print(f"\n<-- Response Received in {elapsed:.2f}s (Status {resp.status_code}):")
    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.text}")
        exit(1)
    result = resp.json()
    print(json.dumps(result, indent=2))

    analysis_url = result.get("analysis_url")
    if analysis_url:
        print(f"\n✅ Analysis URL generated: {analysis_url}")
        print(f"You can now use this analysis_url in modal/test_batch_reframe.py or scratch/test_reframe.py!")
except Exception as e:
    print(f"Error: {e}")

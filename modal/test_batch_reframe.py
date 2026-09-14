import requests
import json

url = "https://ms8460149--makemyclip-ai-rendering-aireframe-batch-reframe.modal.run"
payload = {
    "video_url": "https://www.youtube.com/watch?v=nYOzBYN8K9k",
    "analysis_url": "https://pub-dab84dec13074258806f788a00943c46.r2.dev/analysis/test_clip_2588_2598.json",
    "quality": "export",
    "clips": [
        {
            "clip_id": "test_clip_1",
            "start_time": 2588.0,
            "end_time": 2598.0,
            "crop_mode": "auto"
        }
    ]
}

print(f"Sending request to {url}...")
print(f"Payload: {json.dumps(payload, indent=2)}")
response = requests.post(url, json=payload, headers={"Authorization": "Bearer TEST_TOKEN"})
print(f"Status Code: {response.status_code}")
try:
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(response.text)

import json
import time
import requests

BATCH_REFRAME_ENDPOINT = "https://ms8460149--makemyclip-ai-rendering-aireframe-batch-reframe.modal.run"
ANALYSIS_URL = "https://pub-dab84dec13074258806f788a00943c46.r2.dev/analysis/l9rls6tri7dvi1biti5967ds.json"
VIDEO_URL = "https://www.youtube.com/watch?v=M-ZH3psUbfU"

payload = {
    "video_url": VIDEO_URL,
    "analysis_url": ANALYSIS_URL,
    "clips": [
        {
            "clip_id": "yt_clip_01",
            "start_time": 335.47,
            "end_time": 387.241,
            "crop_mode": "reframe",
            "transcript": [
                {"text": "test caption", "start": 0.0, "end": 3.0, "words": [
                    {"word": "test", "start": 0.0, "end": 1.0},
                    {"word": "caption", "start": 1.0, "end": 3.0},
                ]}
            ],
            "styling": {
                "preset": "default"
            }
        }
    ]
}

print(f"--> Sending Batch Reframe POST request to {BATCH_REFRAME_ENDPOINT}...")
print(f"Payload: {json.dumps(payload, indent=2)}")

t0 = time.time()
try:
    resp = requests.post(BATCH_REFRAME_ENDPOINT, json=payload, timeout=300)
    elapsed = time.time() - t0
    data = resp.json()
    print(f"\n<-- Response Received in {elapsed:.2f}s (Status {resp.status_code}):")
    print(json.dumps(data, indent=2))

    # Download the preview video if available
    if data.get("success") and data.get("results"):
        for r in data["results"]:
            preview = r.get("preview_video_url")
            original = r.get("original_video_url")
            url = preview or original
            label = "preview" if preview else "original"
            if url:
                print(f"\nDownloading {label} video: {url}")
                vid = requests.get(url, timeout=120)
                fname = f"scratch/batch_{label}_{r['clip_id']}.mp4"
                with open(fname, "wb") as f:
                    f.write(vid.content)
                print(f"Saved to {fname} ({len(vid.content) / 1024 / 1024:.1f} MB)")
except Exception as e:
    print(f"Error: {e}")


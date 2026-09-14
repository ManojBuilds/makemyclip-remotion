#!/usr/bin/env python3
import json
import os
import sys
import time
import requests

TRANSCRIBE_ENDPOINT = "https://ms8460149--makemyclip-ai-rendering-audiotranscriber-transcribe.modal.run"
VIDEO_URL = "https://www.youtube.com/watch?v=M-ZH3psUbfU"

print(f"Submitting transcription to Modal:")
print(f"URL: {VIDEO_URL}")
print(f"Endpoint: {TRANSCRIBE_ENDPOINT}")

payload = {
    "video_url": VIDEO_URL,
    "transcribe_language": "auto",
    "translate_language": "none",
}

start_time = time.time()
try:
    print("Sending POST request (timeout 900s)...")
    resp = requests.post(TRANSCRIBE_ENDPOINT, json=payload, timeout=900)
    elapsed = time.time() - start_time
    print(f"Response received in {elapsed:.1f}s, status: {resp.status_code}")

    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.text}")
        sys.exit(1)

    data = resp.json()
    out_file = os.path.join(os.path.dirname(__file__), "youtube_M-ZH3psUbfU_response_v2.json")
    with open(out_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n✅ Successfully saved full JSON response to: {out_file}")


    # Basic stats
    print("\n--- TRANSCRIPTION SUMMARY ---")
    print(f"Success: {data.get('success')}")
    full_text = data.get("fullText", "")
    print(f"Full Text Length: {len(full_text)} chars")
    print(f"Total Words: {len(data.get('words', []))}")
    print(f"Paragraphs: {len(data.get('paragraphs', []))}")
    print(f"Sentiments: {len(data.get('sentiments', []))}")
    print(f"Chapters: {len(data.get('chapters', []))}")
    print(f"Highlights: {len(data.get('highlights', []))}")
    
    clips = data.get("viralClips", [])
    print(f"Viral Clips Found: {len(clips)}")

except Exception as e:
    print(f"Execution failed: {e}")
    sys.exit(1)

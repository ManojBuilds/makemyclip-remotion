#!/usr/bin/env python3
import os
import sys
import json
import requests
from dotenv import load_dotenv

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modal"))
)
from r2_storage import upload_to_r2

load_dotenv()

# Clean bucket name configuration
if os.getenv("R2_BUCKET_NAME"):
    os.environ["R2_BUCKET_NAME"] = os.getenv("R2_BUCKET_NAME").strip('"').strip("'")
if not os.getenv("R2_ENDPOINT_URL") and os.getenv("R2_ACCOUNT_ID"):
    os.environ["R2_ENDPOINT_URL"] = (
        f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com"
    )

youtube_url = "https://www.youtube.com/watch?v=AHO55g343xc"
TRANSCRIBE_ENDPOINT = os.getenv(
    "MODAL_TRANSCRIBE_ENDPOINT",
    "https://ms8460149--makemyclip-ai-rendering-audiotranscriber-transcribe.modal.run",
)

print(f"Calling Transcriber Endpoint on Modal directly with YouTube URL:")
print(f"URL: {youtube_url}")
print(f"Endpoint: {TRANSCRIBE_ENDPOINT}")

payload = {
    "video_url": youtube_url,
    "transcribe_language": "auto",
    "translate_language": "none", # Translate is none to get the native transcript
}

try:
    response = requests.post(TRANSCRIBE_ENDPOINT, json=payload, timeout=600)
    if response.status_code != 200:
        print(f"❌ HTTP Error {response.status_code}: {response.text}")
        sys.exit(1)

    res = response.json()
    if not res.get("success"):
        print(f"❌ Transcription failed: {res}")
        sys.exit(1)

    print("\n🎉 Transcription Success!")
    print(f"Full Text Preview:\n\"{res.get('fullText')[:500]}...\"")

    # Save the transcription JSON
    json_path = os.path.join(os.path.dirname(__file__), "podcast_transcript_en.json")
    with open(json_path, "w") as f:
        json.dump(res, f, indent=2)
    print(f"\n💾 Saved transcript to: {json_path}")

except Exception as e:
    print(f"❌ Connection or processing failed: {e}")
    sys.exit(1)

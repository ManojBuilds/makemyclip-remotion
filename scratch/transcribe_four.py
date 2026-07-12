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

LOCAL_VIDEO = "downloads/result_panel_letterbox.mp4"
R2_KEY = "test_panel_vertical.mp4"
TRANSCRIBE_ENDPOINT = os.getenv(
    "MODAL_TRANSCRIBE_ENDPOINT",
    "https://ms8460149--makemyclip-ai-rendering-audiotranscriber-transcribe.modal.run",
)

if not os.path.exists(LOCAL_VIDEO):
    print(f"❌ Error: Video not found at {LOCAL_VIDEO}")
    sys.exit(1)

print(f"1. Uploading {LOCAL_VIDEO} to Cloudflare R2...")
try:
    public_url = upload_to_r2(LOCAL_VIDEO, R2_KEY)
    print(f"✅ Uploaded successfully. URL: {public_url}")
except Exception as e:
    print(f"❌ Upload failed: {e}")
    sys.exit(1)

print(f"\n2. Calling Transcriber Endpoint on Modal: {TRANSCRIBE_ENDPOINT}...")
payload = {
    "video_url": public_url,
    "transcribe_language": "en",
    "translate_language": "none",
}

try:
    response = requests.post(TRANSCRIBE_ENDPOINT, json=payload, timeout=300)
    if response.status_code != 200:
        print(f"❌ HTTP Error {response.status_code}: {response.text}")
        sys.exit(1)

    res = response.json()
    if not res.get("success"):
        print(f"❌ Transcription failed: {res}")
        sys.exit(1)

    print("\n🎉 Transcription Success!")
    print(f"Full Text:\n\"{res.get('fullText')}\"")

    # Save the transcription JSON for the next step
    json_path = "scratch/panel_transcript_en.json"
    with open(json_path, "w") as f:
        json.dump(res, f, indent=2)
    print(f"\n💾 Saved transcript to: {json_path}")

except Exception as e:
    print(f"❌ Connection or processing failed: {e}")
    sys.exit(1)

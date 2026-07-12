#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv

# Add modal directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modal")))

from r2_storage import upload_to_r2

load_dotenv()

# Verify that R2 credentials exist
required = ["R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_PUBLIC_URL"]
# If endpoint URL is not set in .env, construct it from R2_ACCOUNT_ID
if not os.getenv("R2_ENDPOINT_URL") and os.getenv("R2_ACCOUNT_ID"):
    os.environ["R2_ENDPOINT_URL"] = f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com"

# Clean up R2_BUCKET_NAME quotes if they exist in env
if os.getenv("R2_BUCKET_NAME"):
    os.environ["R2_BUCKET_NAME"] = os.getenv("R2_BUCKET_NAME").strip('"').strip("'")

files_to_upload = {
    "result_examples_from_vizard.ai/interview.mp4": "test_vizard_interview.mp4",
    "result_examples_from_vizard.ai/news.mp4": "test_vizard_news.mp4",
    "result_examples_from_vizard.ai/tv_show.mp4": "test_vizard_tv_show.mp4",
}

print("=== UPLOADING TEST VIDEOS TO CLOUDFLARE R2 ===")

for local_path, key in files_to_upload.items():
    if not os.path.exists(local_path):
        print(f"⚠️ Warning: {local_path} not found. Skipping...")
        continue
    print(f"\nUploading {local_path} as {key}...")
    try:
        url = upload_to_r2(local_path, key)
        print(f"✅ Uploaded successfully! URL:\n{url}")
    except Exception as e:
        print(f"❌ Failed to upload {local_path}: {e}")

print("\n=== UPLOADS COMPLETED ===")

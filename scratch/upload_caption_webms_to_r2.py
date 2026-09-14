#!/usr/bin/env python3
import os
import sys
import boto3
import urllib.request
from dotenv import load_dotenv

load_dotenv()

account_id = os.getenv("R2_ACCOUNT_ID")
endpoint = os.getenv("R2_ENDPOINT_URL") or f"https://{account_id}.r2.cloudflarestorage.com"
access_key = os.getenv("R2_ACCESS_KEY_ID")
secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
bucket = os.getenv("R2_BUCKET_NAME", "youtube-clipper")
pub_url_base = os.getenv("R2_PUBLIC_URL", "https://pub-dab84dec13074258806f788a00943c46.r2.dev").rstrip("/")

PRESETS = [
    "impact", "hormozi", "growth", "coral", "sticker",
    "minimal", "creator", "cinema", "focus", "neon",
    "luxury", "badge", "podcast", "bobby", "tom",
    "casey", "fred", "sara", "billy", "unbox", "aliabdlal"
]

suffix = ""
for arg in list(sys.argv[1:]):
    if arg.startswith("--suffix="):
        suffix = arg.split("=")[1]
        sys.argv.remove(arg)
    elif arg == "--v2":
        suffix = "_v2"
        sys.argv.remove(arg)

if len(sys.argv) > 1:
    targets = set(sys.argv[1:])
    PRESETS = [p for p in PRESETS if p in targets]

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PREVIEWS_DIR = os.path.join(WORKSPACE_DIR, "public", "previews")

from botocore.config import Config

boto_config = Config(
    connect_timeout=8,
    read_timeout=15,
    retries={"max_attempts": 3, "mode": "standard"},
)

print(f"Connecting to R2 endpoint: {endpoint} (Bucket: {bucket})...", flush=True)
s3 = boto3.client(
    "s3",
    endpoint_url=endpoint,
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    config=boto_config,
)

uploaded_webm_urls = {}
uploaded_mp4_urls = {}
uploaded_jpg_urls = {}

print(f"\n🚀 Uploading {len(PRESETS)} caption preset files (suffix='{suffix}') to R2...\n", flush=True)

for preset in PRESETS:
    # 1. Upload WebM
    webm_file = os.path.join(PREVIEWS_DIR, f"caption_{preset}.webm")
    if os.path.exists(webm_file):
        webm_key = f"previews/caption_{preset}{suffix}.webm"
        size_kb = os.path.getsize(webm_file) / 1024.0
        print(f"📤 Uploading {webm_file} ({size_kb:.1f} KB) -> s3://{bucket}/{webm_key}...", flush=True)
        try:
            s3.upload_file(
                webm_file,
                bucket,
                webm_key,
                ExtraArgs={
                    "ContentType": "video/webm",
                    "CacheControl": "public, max-age=31536000, immutable"
                }
            )
            full_webm_url = f"{pub_url_base}/{webm_key}"
            uploaded_webm_urls[preset] = full_webm_url
            print(f"   ✅ WebM URL: {full_webm_url}", flush=True)
        except Exception as e:
            print(f"   ❌ Failed WebM: {e}", flush=True)

    # 1b. Upload MP4 if present
    mp4_file = os.path.join(PREVIEWS_DIR, f"caption_{preset}.mp4")
    if os.path.exists(mp4_file):
        mp4_key = f"previews/caption_{preset}{suffix}.mp4"
        size_kb = os.path.getsize(mp4_file) / 1024.0
        print(f"📤 Uploading {mp4_file} ({size_kb:.1f} KB) -> s3://{bucket}/{mp4_key}...", flush=True)
        try:
            s3.upload_file(
                mp4_file,
                bucket,
                mp4_key,
                ExtraArgs={
                    "ContentType": "video/mp4",
                    "CacheControl": "public, max-age=31536000, immutable"
                }
            )
            full_mp4_url = f"{pub_url_base}/{mp4_key}"
            uploaded_mp4_urls[preset] = full_mp4_url
            print(f"   ✅ MP4 URL: {full_mp4_url}", flush=True)
        except Exception as e:
            print(f"   ❌ Failed MP4: {e}", flush=True)

    # 2. Upload JPG poster if present
    jpg_file = os.path.join(PREVIEWS_DIR, f"caption_{preset}.jpg")
    if os.path.exists(jpg_file):
        jpg_key = f"previews/caption_{preset}{suffix}.jpg"
        print(f"📤 Uploading poster -> s3://{bucket}/{jpg_key}...", flush=True)
        try:
            s3.upload_file(
                jpg_file,
                bucket,
                jpg_key,
                ExtraArgs={
                    "ContentType": "image/jpeg",
                    "CacheControl": "public, max-age=31536000, immutable"
                }
            )
            full_jpg_url = f"{pub_url_base}/{jpg_key}"
            uploaded_jpg_urls[preset] = full_jpg_url
            print(f"   ✅ Poster URL: {full_jpg_url}", flush=True)
        except Exception as e:
            print(f"   ❌ Failed JPG: {e}", flush=True)

print(f"\n🔍 Verifying all {len(uploaded_webm_urls)} WebM URLs via HTTP HEAD...")
verified_count = 0
for preset, url in uploaded_webm_urls.items():
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                verified_count += 1
            else:
                print(f"⚠️ {preset}: HTTP {resp.status}")
    except Exception as e:
        print(f"❌ {preset}: HTTP Error {e}")

print(f"\n🎉 Successfully verified {verified_count}/{len(uploaded_webm_urls)} WebM URLs (200 OK)!")

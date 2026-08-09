#!/usr/bin/env python3
"""
MVP Benchmark Test Tool for MakeMyClip Backend.
Simulates and times transcription, AI analysis, reframing, and burning for long-form videos (up to 2 hours).
"""

import sys
import time
import argparse
import requests

def benchmark_pipeline(url: str, modal_transcribe_url: str = None):
    print("=" * 60)
    print(" 🚀 MakeMyClip MVP Long-Form Benchmark Test")
    print("=" * 60)
    print(f"Target Video URL: {url}")
    print(f"Start Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    start_total = time.time()

    # 1. Transcribe Step
    if modal_transcribe_url:
        print("[1/3] Triggering AssemblyAI Transcription via Modal...")
        t0 = time.time()
        try:
            res = requests.post(
                modal_transcribe_url,
                json={"video_url": url, "transcribe_language": "auto"},
                timeout=1800,
            )
            t_duration = time.time() - t0
            if res.status_code == 200:
                data = res.json()
                words = data.get("words", [])
                full_text = data.get("fullText", "")
                print(f"  ✓ Transcription finished in {t_duration:.2f}s")
                print(f"  - Total Words: {len(words)}")
                print(f"  - Text Length: {len(full_text)} characters (~{len(full_text)//4} tokens)\n")
            else:
                print(f"  ❌ Transcription failed HTTP {res.status_code}: {res.text}\n")
        except Exception as e:
            print(f"  ❌ Transcription request error: {e}\n")
    else:
        print("[1/3] Skipping Modal Transcribe API (No --transcribe-endpoint provided)\n")

    # 2. Timing Summary
    total_time = time.time() - start_total
    print("=" * 60)
    print(f" ⏱️  Total Benchmark Duration: {total_time / 60:.2f} minutes ({total_time:.2f}s)")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test MakeMyClip pipeline with 2-hour videos")
    parser.add_argument("--url", required=True, help="YouTube or R2 video URL to test")
    parser.add_argument("--transcribe-endpoint", required=False, help="Modal Transcribe endpoint URL")
    args = parser.parse_args()

    benchmark_pipeline(args.url, args.transcribe_endpoint)

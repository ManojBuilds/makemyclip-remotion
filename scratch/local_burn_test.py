import os
import sys
import subprocess
import requests

# Add modal dir to sys.path so we can import ass_builder
modal_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modal"))
if modal_dir not in sys.path:
    sys.path.insert(0, modal_dir)

from ass_builder import generate_ass

def test_local_burn():
    print("=== LOCAL CAPTION BURN TEST WITH EXACT VIDEO & TRANSCRIPT ===")

    video_url = "https://pub-dab84dec13074258806f788a00943c46.r2.dev/reframes/orig_4e6d0ce6-3fbb-47f8-add0-96ea4351c153.mp4"
    input_video = os.path.abspath("scratch/orig_video_clip.mp4")
    output_video = os.path.abspath("scratch/locally_burned_output.mp4")
    ass_output_path = os.path.abspath("scratch/test_local_captions.ass")

    # 1. Download source clip video if not cached locally
    if not os.path.exists(input_video):
        print(f"Downloading source video from:\n  {video_url}")
        res = requests.get(video_url, timeout=120)
        with open(input_video, "wb") as f:
            f.write(res.content)
        print(f"Saved source video ({len(res.content) / 1024 / 1024:.1f} MB)")

    # 2. Extract transcript from test_batch_reframe.py
    import test_batch_reframe
    transcript = test_batch_reframe.payload["clips"][0]["transcript"]

    styling = {
        "preset": "impact",
        "font_size": 48,
    }

    print(f"\nGenerating ASS subtitle file using ass_builder.py...")
    generate_ass(transcript, styling, ass_output_path, crop_mode="reframe")

    with open(ass_output_path, "r", encoding="utf-8") as f:
        ass_content = f.read()

    event_lines = [line for line in ass_content.splitlines() if line.startswith("Dialogue:")]
    print(f"Generated ASS with {len(event_lines)} subtitle events.")
    print("First 5 subtitle events:")
    for line in event_lines[:5]:
        print("  ", line)

    print(f"\nBurning ASS captions locally onto video using FFmpeg...")
    ass_escaped = ass_output_path.replace(":", r"\:")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_video,
        "-vf", f"ass='{ass_escaped}'",
        "-c:a", "copy",
        output_video
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"\n✅ Success! Locally burned video saved to:\n  {output_video}")
    else:
        print(f"\n❌ FFmpeg error:\n{res.stderr}")

if __name__ == "__main__":
    test_local_burn()

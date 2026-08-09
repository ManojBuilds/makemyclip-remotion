#!/usr/bin/env python3
import os
import sys
import json
import shutil
import subprocess
import requests
from dotenv import load_dotenv

# Ensure modal folder is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modal")))
from ass_builder import generate_ass
from presets import PRESET_STYLES

load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

# Mapping each demo clip to its ideal preset based on use case
CLIP_PRESETS = {
    # 1. Impact: TikTok / Shorts / Reels (Anton, yellow highlight, thick outline)
    "solo_talking_head_output.mp4": {
        "preset": "impact",
        "word_highlight": True,
    },
    "background_poster_output.mp4": {
        "preset": "impact",
        "word_highlight": True,
    },
    # 2. Creator: Modern YouTubers / Tech / Education (Space Grotesk, cyan highlight, smooth slide)
    "clean_result_course_presentation.mp4": {
        "preset": "creator",
        "word_highlight": True,
    },
    "webcam_course_layout_output.mp4": {
        "preset": "creator",
        "word_highlight": True,
    },
    # 3. Cinema: Podcasts / Interviews / Storytelling (Roxborough CF serif, soft yellow highlight, smooth fade)
    "result_podcast_reframe.mp4": {
        "preset": "cinema",
        "word_highlight": True,
    },
    "tv_show_output.mp4": {
        "preset": "cinema",
        "word_highlight": True,
    },
    # 4. Focus: Flagship pill highlight behind active word (SF Pro Display, yellow pill, active word black)
    "fast_crosstalk_output.mp4": {
        "preset": "impact",
        "word_highlight": True,
    },
    "two_person_podcast_output.mp4": {
        "preset": "cinema",
        "word_highlight": True,
    },
    # 5. Neon: Gaming / Streaming / Cyberpunk / AI (Bebas Neue, pulsing pink neon glow)
    "occluded_profile_face_output.mp4": {
        "preset": "neon",
        "word_highlight": True,
    },
    "yt_interview_split_grid_output.mp4": {
        "preset": "neon",
        "word_highlight": True,
    },
}

def install_fonts():
    font_dirs = [os.path.abspath("fonts"), os.path.abspath("public/fonts")]
    user_fonts_dir = os.path.expanduser("~/.local/share/fonts/makemyclip")
    os.makedirs(user_fonts_dir, exist_ok=True)

    installed_new = False
    for font_dir in font_dirs:
        if not os.path.exists(font_dir):
            continue
        for filename in os.listdir(font_dir):
            if filename.lower().endswith((".ttf", ".otf")):
                src = os.path.join(font_dir, filename)
                dst = os.path.join(user_fonts_dir, filename)
                if not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst):
                    shutil.copy2(src, dst)
                    installed_new = True

    if installed_new:
        print("🔄 Rebuilding font cache (fc-cache -f)...")
        subprocess.run(["fc-cache", "-f"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✅ Font cache updated!")

def get_duration(video_path):
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", video_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    info = json.loads(res.stdout)
    return float(info["format"]["duration"])

def has_audio_stream(video_path):
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", video_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    info = json.loads(res.stdout)
    aud_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    return len(aud_streams) > 0

def transcribe_with_deepgram(video_path):
    if not DEEPGRAM_API_KEY:
        print("❌ Error: DEEPGRAM_API_KEY missing from environment")
        return []

    url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&punctuate=true&utterances=true&diarize=true"
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/mp4"
    }
    with open(video_path, "rb") as f:
        data = f.read()

    resp = requests.post(url, headers=headers, data=data)
    if resp.status_code == 200:
        res = resp.json()
        words = res["results"]["channels"][0]["alternatives"][0]["words"]
        formatted_words = []
        for w in words:
            formatted_words.append({
                "word": w.get("punctuated_word") or w.get("word"),
                "start": w["start"],
                "end": w["end"],
                "speaker": f"speaker_{w.get('speaker', 0) + 1}"
            })
        return formatted_words
    else:
        print(f"❌ Deepgram error {resp.status_code}: {resp.text}")
        return []

def main():
    print("=== PROCESSING DEMO CLIPS WITH DIVERSE PRESET STYLES ===")
    install_fonts()

    demo_dir = "demo"
    tmp_dir = os.path.join("scratch", "demo_processing_tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    # Get source video files (exclude existing _captioned outputs)
    files = sorted([
        f for f in os.listdir(demo_dir)
        if f.endswith(".mp4") and not f.endswith("_captioned.mp4")
    ])

    print(f"Found {len(files)} source clips in '{demo_dir}':")

    for f in files:
        src_path = os.path.join(demo_dir, f)
        base_name = os.path.splitext(f)[0]
        captioned_out_path = os.path.join(demo_dir, f"{base_name}_captioned.mp4")

        # Get style configuration for this file
        caption_style = CLIP_PRESETS.get(f, {"preset": "impact", "word_highlight": True})
        preset_name = caption_style["preset"]

        print(f"\n--------------------------------------------------")
        print(f"📹 Processing clip: {f} using preset: '{preset_name.upper()}'")

        # 1. Check duration
        duration = get_duration(src_path)
        print(f"   Original duration: {duration:.2f}s")

        # 2. Copy & trim to working file if > 5.0s (do NOT mutate source)
        trimmed_copy_path = os.path.join(tmp_dir, f"{base_name}_trimmed_copy.mp4")

        if duration > 5.0:
            print(f"   ✂️ Duration > 5s. Trimming copy to 5.0 seconds...")
            cmd_trim = [
                "ffmpeg", "-y",
                "-ss", "0",
                "-i", src_path,
                "-t", "5.0",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "18",
                "-c:a", "aac",
                trimmed_copy_path
            ]
            subprocess.run(cmd_trim, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        else:
            print(f"   📋 Duration <= 5s. Copying file...")
            shutil.copy2(src_path, trimmed_copy_path)

        trimmed_dur = get_duration(trimmed_copy_path)
        print(f"   Copy duration: {trimmed_dur:.2f}s")

        # 3. Transcribe audio from copied video
        words = []
        if has_audio_stream(trimmed_copy_path):
            print("   🎙️ Transcribing audio with Deepgram...")
            words = transcribe_with_deepgram(trimmed_copy_path)
            print(f"   Transcribed {len(words)} words.")
        else:
            print("   ⚠️ No audio stream found in video! Attempting fallback transcript...")
            course_ts_path = "scratch/course_transcript_en.json"
            if "course" in f and os.path.exists(course_ts_path):
                with open(course_ts_path, "r") as json_f:
                    data = json.load(json_f)
                    words = data.get("words", [])
                    words = [w for w in words if w["start"] < 5.0]
                print(f"   Loaded {len(words)} fallback words from course_transcript_en.json.")

        if not words:
            print(f"   ⚠️ Warning: No words found for {f}. Creating simple default caption.")
            words = [
                {"word": "DEMO", "start": 0.5, "end": 2.5, "speaker": "speaker_1"},
                {"word": "PRESENTATION", "start": 2.5, "end": 4.5, "speaker": "speaker_1"}
            ]

        # Filter words to ensure timestamps fit within trimmed duration
        words = [w for w in words if w["start"] < trimmed_dur]
        for w in words:
            if w["end"] > trimmed_dur:
                w["end"] = trimmed_dur

        # 4. Generate ASS file using designated preset
        ass_path = os.path.join(tmp_dir, f"{base_name}.ass")
        print(f"   📝 Generating ASS subtitles with preset '{preset_name}': {ass_path}")
        generate_ass(words, caption_style, ass_path, crop_mode="reframe")

        # 5. Burn captions onto the copied video with FFmpeg
        print(f"   🔥 Burning captions to output: {captioned_out_path}")
        cmd_burn = [
            "ffmpeg", "-y",
            "-i", trimmed_copy_path,
            "-vf", f"ass='{ass_path}'",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-c:a", "copy" if has_audio_stream(trimmed_copy_path) else "none",
            captioned_out_path
        ]
        res_burn = subprocess.run(cmd_burn, capture_output=True, text=True)
        if res_burn.returncode == 0:
            out_dur = get_duration(captioned_out_path)
            out_size_mb = os.path.getsize(captioned_out_path) / (1024 * 1024)
            print(f"   ✅ SUCCESS: {captioned_out_path} [{preset_name.upper()}] (Duration: {out_dur:.2f}s, Size: {out_size_mb:.2f} MB)")
        else:
            print(f"   ❌ FAILED to burn captions for {f}:")
            print(res_burn.stderr[-500:])

    print("\n🎉 ALL DEMO CLIPS RE-PROCESSED WITH DIVERSE PRESET STYLES SUCCESSFULLY!")

if __name__ == "__main__":
    main()

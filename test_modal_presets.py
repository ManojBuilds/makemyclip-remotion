#!/usr/bin/env python3
"""
Test script for verifying MakeMyClip caption presets and templates using the production Modal code.
"""

import sys
import os
import argparse
import subprocess
import json
import shutil

# Ensure modal folder is in python path for absolute imports inside ass_builder to work
modal_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "modal"))
sys.path.insert(0, modal_dir)

try:
    from ass_builder import generate_ass
    from presets import PRESET_STYLES
except ImportError as e:
    print(f"Error: Could not import modal dependencies. Details: {e}")
    sys.exit(1)

# Default Test Transcript (Jensen Huang/NVIDIA topic)
DEFAULT_TRANSCRIPT = [
    {"word": "That's", "start": 0.005, "end": 0.39},
    {"word": "Jensen", "start": 0.39, "end": 0.79},
    {"word": "Huang.", "start": 0.79, "end": 1.43},
    {"word": "And", "start": 3.19, "end": 3.51},
    {"word": "whether", "start": 3.51, "end": 3.83},
    {"word": "you", "start": 3.83, "end": 3.99},
    {"word": "know", "start": 3.99, "end": 4.15},
    {"word": "it", "start": 4.15, "end": 4.31},
    {"word": "or", "start": 4.31, "end": 4.47},
    {"word": "not,", "start": 4.47, "end": 4.79},
    {"word": "his", "start": 4.79, "end": 4.95},
    {"word": "decisions", "start": 4.95, "end": 5.35},
    {"word": "are", "start": 5.35, "end": 5.75},
    {"word": "shaping", "start": 5.75, "end": 6.23},
    {"word": "your", "start": 6.23, "end": 6.63},
    {"word": "future.", "start": 6.63, "end": 7.11},
    {"word": "He's", "start": 7.11, "end": 7.35},
    {"word": "the", "start": 7.35, "end": 7.51},
    {"word": "CEO", "start": 7.51, "end": 7.83},
    {"word": "of", "start": 7.83, "end": 8.07},
    {"word": "NVIDIA,", "start": 8.07, "end": 8.71},
    {"word": "the", "start": 8.71, "end": 8.79},
    {"word": "company", "start": 8.79, "end": 9.03},
    {"word": "that", "start": 9.03, "end": 9.27},
    {"word": "skyrocketed", "start": 9.27, "end": 9.99},
    {"word": "over", "start": 9.99, "end": 10.23},
    {"word": "the", "start": 10.23, "end": 10.31},
    {"word": "past", "start": 10.31, "end": 10.55},
    {"word": "few", "start": 10.55, "end": 10.79},
    {"word": "years", "start": 10.79, "end": 11.03},
    {"word": "to", "start": 11.03, "end": 11.35},
    {"word": "become", "start": 11.35, "end": 11.67},
    {"word": "one", "start": 11.67, "end": 11.83},
    {"word": "of", "start": 11.83, "end": 11.91},
    {"word": "the", "start": 11.91, "end": 11.99},
    {"word": "most", "start": 11.99, "end": 12.23},
    {"word": "valuable", "start": 12.23, "end": 12.67},
    {"word": "companies", "start": 12.67, "end": 13.15},
    {"word": "in", "start": 13.15, "end": 13.31},
    {"word": "the", "start": 13.31, "end": 13.47},
    {"word": "world.", "start": 13.47, "end": 14.03},
]

# Frontend Templates mapping from components/video/caption_templates.ts
FRONTEND_TEMPLATES = {
    "hormozi": {
        "name": "Money Mode",
        "preset": "hormozi",
        "font_family": "The Bold Font",
        "font_size": 102.0,  # Updated to optimal pixel size
        "font_color": "#FFFFFF",
        "highlight_color": "#FFDC00",  # Iconic yellow highlight
        "stroke_color": "#000000",
        "stroke_width": 4.5,  # Thicker stroke for readability
        "background": False,
        "background_color": "transparent",
        "animation": "pop-up",  # Authentic upward bounce
        "future_dim": False,
        "shadow": True,
        "shadow_depth": 4.0,
        "letter_spacing": -1.5,  # Tighter tracking for short-form
        "uppercase": True,  # Strict uppercase format
        "highlight_scale": 1.15,  # Noticeable scale bump
        "position_y": 0.70,  # Shifted closer to safe-zone center
        "max_words": 2,  # Reduced to 2 words max for speed
    },
    "beast": {
        "name": "Hype Beast",
        "preset": "beast",
        "font_family": "Anton",
        "font_size": 115.0,  # Updated to optimal pixel size
        "font_color": "#FFFFFF",
        "highlight_color": "#00FF00",  # Changed to iconic bright green
        "stroke_color": "#000000",
        "stroke_width": 5.0,  # Extra heavy black outline
        "background": False,
        "background_color": "transparent",
        "animation": "overshoot-zoom",  # Classic snappy zoom animation
        "future_dim": False,
        "shadow": True,
        "shadow_depth": 5.0,
        "letter_spacing": -0.5,
        "uppercase": True,
        "highlight_scale": 1.25,  # High dramatic scale factor
        "position_y": 0.50,  # Dead center positioning
        "max_words": 2,  # Fast 1-2 word cuts
    },
    "box-highlight": {
        "name": "Clean Glow",
        "preset": "box-highlight",
        "font_family": "Poppins",
        "font_size": 76.8,  # Updated to optimal pixel size
        "font_color": "#FFFFFF",
        "highlight_color": "#FFDC00",
        "stroke_color": "transparent",
        "stroke_width": 0.0,
        "background": True,
        "background_color": "#FFDC00",
        "animation": "box-fade",
        "future_dim": False,
        "shadow": False,
        "shadow_depth": 0.0,
        "letter_spacing": -0.5,
        "uppercase": False,
        "highlight_scale": 1.0,
        "position_y": 0.75,
        "max_words": 4,
    },
    "simple": {
        "name": "Podcast Pro",
        "preset": "simple",
        "font_family": "TikTok Sans",
        "font_size": 72.0,  # Updated to optimal pixel size
        "font_color": "#E5E5E5",  # Subtle off-white for cinematic look
        "highlight_color": "#FFFFFF",
        "stroke_color": "#000000",
        "stroke_width": 2.0,
        "background": False,
        "background_color": "transparent",
        "animation": "smooth-fade",
        "future_dim": True,  # Karaoke-style text dimming
        "shadow": True,
        "shadow_depth": 2.0,
        "letter_spacing": 0.0,
        "position_y": 0.80,  # Lower thirds placement
        "uppercase": False,
        "max_words": 5,  # Displays longer elegant phrases
    },
    "opus": {
        "name": "Viral Pop",
        "preset": "opus",
        "font_family": "Bebas Neue",
        "font_size": 88.0,  # Updated to optimal pixel size
        "font_color": "#000000",
        "highlight_color": "#FFFFFF",  # Contrast white highlight on yellow box
        "stroke_color": "#FFDC00",  # Match background to expand and round the box
        "stroke_width": 10.0,
        "background": True,
        "background_color": "#FFDC00",
        "animation": "spring-pop",  # Signature bouncy feel
        "future_dim": False,
        "shadow": True,
        "shadow_depth": 3.0,
        "letter_spacing": -0.5,
        "position_y": 0.60,  # Optimal center-low balance
        "uppercase": True,  # Changed to True for higher engagement
        "highlight_scale": 1.10,
        "max_words": 3,
    },
    "popline": {
        "name": "Underline It",
        "preset": "popline",
        "font_family": "Lilita One",
        "font_size": 89.6,  # Updated to optimal pixel size
        "font_color": "#FFFFFF",
        "highlight_color": "#FF4500",  # Electric orange-red
        "stroke_color": "#000000",  # Added dark stroke for definition
        "stroke_width": 3.5,
        "background": False,
        "background_color": "transparent",
        "animation": "slide-up",
        "future_dim": False,
        "shadow": True,
        "shadow_depth": 2.0,
        "letter_spacing": -0.5,
        "position_y": 0.70,
        "uppercase": True,
        "highlight_scale": 1.05,
        "max_words": 3,
    },
    "neon-glow": {
        "name": "Neon Glow",
        "preset": "neon-glow",
        "font_family": "Teko",
        "font_size": 92.8,  # Updated to optimal pixel size
        "font_color": "#FFFFFF",
        "highlight_color": "#FF007F",  # Neon hot pink
        "stroke_color": "transparent",
        "stroke_width": 0.0,
        "background": False,
        "background_color": "transparent",
        "animation": "neon-flicker",  # Smooth glow pulsing
        "future_dim": True,  # Highly effective for dark backgrounds
        "shadow": True,
        "shadow_depth": 6.0,  # Deeper shadow to emphasize outer glow
        "letter_spacing": 1.0,
        "uppercase": True,
        "highlight_scale": 1.0,
        "position_y": 0.65,
        "max_words": 3,
    },
    "sticker": {
        "name": "Sticker",
        "preset": "sticker",
        "font_family": "Bangers",
        "font_size": 144.0,  # Updated to optimal pixel size
        "font_color": "#000000",
        "highlight_color": "#000000",
        "stroke_color": "#FFFFFF",
        "stroke_width": 10.0,
        "background": False,
        "background_color": "transparent",
        "animation": "none",
        "future_dim": False,
        "shadow": False,
        "shadow_depth": 0.0,
        "letter_spacing": 0.0,
        "position_y": 0.50,
        "uppercase": True,
        "max_words": 3,
    },
}


def burn_caption(input_video, output_video, ass_path):
    """Run FFmpeg command to burn subtitles into video using libass filter."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_video,
        "-vf",
        f"ass='{ass_path}'",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-c:a",
        "copy",
        output_video,
    ]

    print(f"🎬 Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("❌ FFmpeg failed!")
        print(f"Stderr tail:\n{result.stderr[-1000:]}")
        return False
    return True


def test_preset(preset_name, input_video, output_dir):
    """Test a raw backend preset style from presets.py."""
    if preset_name not in PRESET_STYLES:
        print(f"❌ Preset '{preset_name}' not found in presets.py!")
        return False

    print(f"\n--- Testing Backend Preset: {preset_name} ---")

    # Create output paths
    ass_path = os.path.join(output_dir, f"preset_{preset_name}.ass")
    out_video = os.path.join(output_dir, f"preset_{preset_name}.mp4")

    # Generate ASS with default styling referencing the preset
    styling = {"animation": preset_name}
    generate_ass(DEFAULT_TRANSCRIPT, styling, ass_path)

    # Burn captions
    success = burn_caption(input_video, out_video, ass_path)
    if success:
        print(f"✅ Generated: {out_video}")
    return success


def test_template(template_name, input_video, output_dir):
    """Test a frontend style template with full overrides."""
    if template_name not in FRONTEND_TEMPLATES:
        print(f"❌ Template '{template_name}' not found!")
        return False

    template = FRONTEND_TEMPLATES[template_name]
    print(f"\n--- Testing Frontend Template: {template['name']} ({template_name}) ---")

    # Create output paths
    ass_path = os.path.join(output_dir, f"template_{template_name}.ass")
    out_video = os.path.join(output_dir, f"template_{template_name}.mp4")

    # Generate ASS using frontend template overrides
    generate_ass(DEFAULT_TRANSCRIPT, template, ass_path)

    # Burn captions
    success = burn_caption(input_video, out_video, ass_path)
    if success:
        print(f"✅ Generated: {out_video}")
    return success


def find_default_video():
    """Find a default test video in the workspace."""
    search_dirs = ["trimmed_video_clips", "."]
    video_names = [
        "elon_musk_s_crazy_ai_chip_moment_n6p3f.mp4",
        "input.mp4",
        "test.mp4",
        "clip.mp4",
    ]

    for d in search_dirs:
        for v in video_names:
            path = os.path.join(d, v)
            if os.path.exists(path):
                return path
    return None


def install_fonts():
    """Locally sync fonts from public/fonts/ to user's local fonts directory."""
    public_fonts_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "public", "fonts")
    )
    if not os.path.exists(public_fonts_dir):
        print(
            "⚠️ Warning: public/fonts/ folder not found. Skipping local font installation."
        )
        return

    user_fonts_dir = os.path.expanduser("~/.local/share/fonts/makemyclip")
    os.makedirs(user_fonts_dir, exist_ok=True)

    installed_new = False
    for filename in os.listdir(public_fonts_dir):
        if filename.lower().endswith((".ttf", ".otf")):
            src = os.path.join(public_fonts_dir, filename)
            dst = os.path.join(user_fonts_dir, filename)
            if not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst):
                print(f"📁 Copying font to system cache: {filename}")
                shutil.copy2(src, dst)
                installed_new = True

    if installed_new:
        print("🔄 Rebuilding font cache (fc-cache -f)...")
        subprocess.run(
            ["fc-cache", "-f"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print("✅ Font cache updated!")


def main():
    # Ensure local system has all font assets registered before rendering
    install_fonts()

    parser = argparse.ArgumentParser(
        description="Test MakeMyClip captions rendering locally using the production ass_builder."
    )
    parser.add_argument("--input", "-i", type=str, help="Path to input test video")
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default="test_outputs",
        help="Directory for output videos",
    )
    parser.add_argument(
        "--preset",
        "-p",
        type=str,
        choices=list(PRESET_STYLES.keys()) + ["all"],
        help="Test specific backend base preset",
    )
    parser.add_argument(
        "--template",
        "-t",
        type=str,
        choices=list(FRONTEND_TEMPLATES.keys()) + ["all"],
        help="Test specific frontend template overrides",
    )

    args = parser.parse_args()

    # 1. Resolve Input Video
    input_video = args.input
    if not input_video:
        input_video = find_default_video()
        if not input_video:
            print(
                "❌ Error: Could not find any default test video in 'trimmed_video_clips/' or root workspace."
            )
            print("Please place a video file or specify --input <path_to_video>")
            sys.exit(1)

    print(f"Using input video: {input_video}")

    # 2. Setup Output Directory
    os.makedirs(args.output_dir, exist_ok=True)

    # If no specific action is chosen, enter interactive mode
    if not args.preset and not args.template:
        print("\n=== MakeMyClip Local Caption Tester ===")
        print("1. Test Frontend Templates (matches UI options)")
        print("2. Test Backend Base Presets (raw styles)")
        print("3. Test ALL Frontend Templates")
        print("4. Test ALL Backend Presets")
        print("5. Exit")
        try:
            choice = input("\nEnter choice [1-5]: ").strip()
        except KeyboardInterrupt:
            print("\nExited.")
            sys.exit(0)

        if choice == "1":
            print("\nAvailable Templates:")
            template_keys = list(FRONTEND_TEMPLATES.keys())
            for idx, key in enumerate(template_keys, start=1):
                print(f"  {idx}. {FRONTEND_TEMPLATES[key]['name']} ({key})")

            try:
                t_idx = (
                    int(input(f"Choose template [1-{len(template_keys)}]: ").strip())
                    - 1
                )
                if 0 <= t_idx < len(template_keys):
                    test_template(template_keys[t_idx], input_video, args.output_dir)
            except (ValueError, KeyboardInterrupt, IndexError):
                print("Invalid selection.")
        elif choice == "2":
            print("\nAvailable Base Presets:")
            preset_keys = list(PRESET_STYLES.keys())
            for idx, key in enumerate(preset_keys, start=1):
                print(f"  {idx}. {key}")

            try:
                p_idx = (
                    int(input(f"Choose preset [1-{len(preset_keys)}]: ").strip()) - 1
                )
                if 0 <= p_idx < len(preset_keys):
                    test_preset(preset_keys[p_idx], input_video, args.output_dir)
            except (ValueError, KeyboardInterrupt, IndexError):
                print("Invalid selection.")
        elif choice == "3":
            for key in FRONTEND_TEMPLATES.keys():
                test_template(key, input_video, args.output_dir)
        elif choice == "4":
            for key in PRESET_STYLES.keys():
                test_preset(key, input_video, args.output_dir)
        else:
            print("Exited.")
            sys.exit(0)

    # Handle Command Line Arguments
    if args.preset:
        if args.preset == "all":
            for key in PRESET_STYLES.keys():
                test_preset(key, input_video, args.output_dir)
        else:
            test_preset(args.preset, input_video, args.output_dir)

    if args.template:
        if args.template == "all":
            for key in FRONTEND_TEMPLATES.keys():
                test_template(key, input_video, args.output_dir)
        else:
            test_template(args.template, input_video, args.output_dir)


if __name__ == "__main__":
    main()

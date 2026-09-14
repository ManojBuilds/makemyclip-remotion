import sys
import os
import subprocess

# Ensure workspace root and modal directory are in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../modal")))

from ass_builder import generate_ass
from burner import burn_captions_local
from presets import PRESET_STYLES, ALWAYS_UPPERCASE

# ----------------------------------------------------------------------
# Test Transcript
# ----------------------------------------------------------------------

CUSTOM_TRANSCRIPT = [
    # Speaker 1
    {"word": "Wait...", "start": 0.00, "end": 0.35, "speaker": "speaker_1"},
    {"word": "this", "start": 0.35, "end": 0.60, "speaker": "speaker_1"},
    {"word": "changes", "start": 0.60, "end": 1.00, "speaker": "speaker_1"},
    {"word": "everything!", "start": 1.00, "end": 1.50, "speaker": "speaker_1"},
    # Speaker 2
    {"word": "Watch", "start": 1.50, "end": 1.85, "speaker": "speaker_2"},
    {"word": "closely", "start": 1.85, "end": 2.20, "speaker": "speaker_2"},
    {"word": "right", "start": 2.20, "end": 2.50, "speaker": "speaker_2"},
    {"word": "now!", "start": 2.50, "end": 2.90, "speaker": "speaker_2"},
]


# ----------------------------------------------------------------------
# Video Helpers
# ----------------------------------------------------------------------


def generate_black_video(output_video):
    """Generate a 3-second black video with silent audio."""

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=1080x1920:r=30:d=3",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=44100:cl=mono",
        "-t",
        "3",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        output_video,
    ]

    print("🎬 Creating black video...")
    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def generate_image_video(image_path: str, output_video: str, duration: int = 3):
    """Generate a 3-second video looping an image at 1080x1920 with silent audio."""
    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", image_path,
        "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=mono",
        "-t", str(duration),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        output_video,
    ]
    print(f"🎬 Creating image video from {image_path}...")
    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ----------------------------------------------------------------------
# Preset → Styling conversion
# ----------------------------------------------------------------------


def preset_to_styling(name: str, preset: dict) -> dict:
    """
    Converts PRESET_STYLES into the styling dict expected by generate_ass().
    """

    styling = {
        "preset": name,
        "font_family": preset["fontname"],
        "font_size": preset["fontsize"],
        "text_color": preset["primary"],
        "highlight_color": preset["highlightcolor"],
        "stroke_color": preset["outlinecolor"],
        "stroke_width": preset["outline"],
        "shadow_depth": preset["shadow"],
        "text_transform": ("uppercase" if name in ALWAYS_UPPERCASE else "none"),
        # Use preset default for word-level active highlighting (True for Shorts/Reels, False for Cinema/Luxury)
        "word_highlight": preset.get("word_highlight_default", True),
        # Use layout default caption position (reframe = 0.65)
        "position_y": None,
    }

    if preset["backcolor"]:
        styling["background_enabled"] = True
        styling["background_color"] = preset["backcolor"][0]
        styling["background_alpha"] = preset["backcolor"][1]
    else:
        styling["background_enabled"] = False

    return styling


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------


def main():
    output_dir = os.path.join(os.path.dirname(__file__), "test_outputs")
    os.makedirs(output_dir, exist_ok=True)

    source_img = os.path.abspath(os.path.join(os.path.dirname(__file__), "source_image.jpg"))
    image_video = os.path.join(output_dir, "image_canvas.mp4")

    default_video = os.path.abspath(os.path.join(os.path.dirname(__file__), "../reframed_3s.mp4"))
    if not os.path.exists(default_video):
        default_video = os.path.abspath(os.path.join(os.path.dirname(__file__), "../reframed_stable_zoom_fixed.mp4"))

    # Parse arguments
    args = [a for a in sys.argv[1:]]
    use_black = "--black" in args
    args = [a for a in args if a != "--black"]

    custom_video = None
    target_preset = "all"

    for a in args:
        if a.endswith(".mp4") and os.path.exists(a):
            custom_video = os.path.abspath(a)
        elif a.lower() in PRESET_STYLES or a.lower() == "all":
            target_preset = a.lower()

    if use_black:
        black_video = os.path.join(output_dir, "black_canvas.mp4")
        generate_black_video(black_video)
        input_video = black_video
    elif custom_video:
        input_video = custom_video
    elif os.path.exists(source_img):
        generate_image_video(source_img, image_video)
        input_video = image_video
    elif os.path.exists(default_video):
        input_video = default_video
    else:
        black_video = os.path.join(output_dir, "black_canvas.mp4")
        generate_black_video(black_video)
        input_video = black_video

    print(f"📹 Using input video: {input_video}")

    for preset_name, preset in PRESET_STYLES.items():
        if target_preset != "all" and preset_name != target_preset:
            continue

        print(f"\n{'=' * 60}")
        print(f"Testing preset: {preset_name}")
        print(f"{'=' * 60}")

        styling = preset_to_styling(
            preset_name,
            preset,
        )

        out_video = os.path.join(
            output_dir,
            f"{preset_name}.mp4",
        )

        try:
            video_url, _ = burn_captions_local(
                local_video=input_video,
                local_output=out_video,
                transcript=CUSTOM_TRANSCRIPT,
                styling=styling,
                show_watermark=False,
                crop_mode="reframe",
                quality="export",
                tmpdir=output_dir,
            )
            print(f"✅ Generated {out_video}")
        except Exception as e:
            print(f"❌ Failed preset {preset_name}: {e}")


if __name__ == "__main__":
    main()

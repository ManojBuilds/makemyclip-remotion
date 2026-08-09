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
    {"word": "Wait...", "start": 0.00, "end": 0.35},
    {"word": "this", "start": 0.35, "end": 0.60},
    {"word": "changes", "start": 0.60, "end": 1.00},
    {"word": "everything!", "start": 1.00, "end": 1.70},
    {"word": "Watch", "start": 1.70, "end": 2.10},
    {"word": "closely.", "start": 2.10, "end": 3.00},
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
        # Enable word-level active highlighting by default
        "word_highlight": True,
        # Approximate vertical position from margin
        "position_y": 0.5,
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
    output_dir = "test_outputs"
    os.makedirs(output_dir, exist_ok=True)

    black_video = os.path.join(output_dir, "video_for_caption_testing.mp4")
    generate_black_video(black_video)

    # Target a single preset (change to any preset name, e.g. "hormozi")
    target_preset = "cinema"

    for preset_name, preset in PRESET_STYLES.items():
        if preset_name != target_preset:
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
                local_video=black_video,
                local_output=out_video,
                transcript=CUSTOM_TRANSCRIPT,
                styling=styling,
                show_watermark=True,
                crop_mode="reframe",
                quality="export",
                tmpdir=output_dir,
            )
            print(f"✅ {out_video}")
        except Exception as e:
            print(f"❌ Failed: {preset_name}: {e}")


if __name__ == "__main__":
    main()

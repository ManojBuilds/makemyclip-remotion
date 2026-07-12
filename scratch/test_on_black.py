import sys
import os
import subprocess

# Ensure workspace root and modal directory are in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../modal")))

from ass_builder import generate_ass
from caption_presets import PRESET_STYLES, ALWAYS_UPPERCASE

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

    print(f"🎬 Creating black video...")
    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def burn_caption(input_video, output_video, ass_path):
    """Burn ASS subtitles onto the video."""

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

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(result.stderr[-1000:])
        return False

    return True


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
        "stroke_color": preset["outlinecolor"],
        "stroke_width": preset["outline"],
        "shadow_depth": preset["shadow"],
        "text_transform": ("uppercase" if name in ALWAYS_UPPERCASE else "none"),
        # Approximate vertical position from margin
        "position_y": (
            0.50
            if preset["alignment"] == 5
            else max(0.0, min(1.0, 1.0 - preset["marginv"] / 1920))
        ),
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

    black_video = os.path.join(output_dir, "black_3s.mp4")
    generate_black_video(black_video)

    for preset_name, preset in PRESET_STYLES.items():

        print(f"\n{'=' * 60}")
        print(f"Testing preset: {preset_name}")
        print(f"{'=' * 60}")

        styling = preset_to_styling(
            preset_name,
            preset,
        )

        ass_path = os.path.join(
            output_dir,
            f"{preset_name}.ass",
        )

        out_video = os.path.join(
            output_dir,
            f"{preset_name}.mp4",
        )

        generate_ass(
            CUSTOM_TRANSCRIPT,
            styling,
            ass_path,
        )

        success = burn_caption(
            black_video,
            out_video,
            ass_path,
        )

        if success:
            print(f"✅ {out_video}")
        else:
            print(f"❌ Failed: {preset_name}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""TikTok-style captions at bottom with proper font handling."""

import pysubs2
import subprocess
import os

# ==========================================
# CONFIG
# ==========================================

INPUT_VIDEO = "cap_226797cd-0719-45f1-8adb-ead57cdf49f8.mp4"
OUTPUT_VIDEO = "test_captioned_output.mp4"

ASS_FILE = os.path.abspath("test_subs.ass")

captions_json = [
    {"word": "That's", "start": 0.005, "end": 1.045},
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
    {"word": "valuable", "start": 12.23, "end": 13.11},
    {"word": "companies", "start": 12.67, "end": 13.15},
    {"word": "in", "start": 13.15, "end": 13.31},
    {"word": "the", "start": 13.31, "end": 13.47},
    {"word": "world.", "start": 13.47, "end": 14.03},
]

# ==========================================
# STYLE
# ==========================================

# IMPORTANT:
# Install TikTok font first:
#
# mkdir -p ~/.fonts
# cp TikTokSans-Bold.ttf ~/.fonts/
# fc-cache -fv
#
# Then verify:
# fc-list | grep -i "tiktok"

FONT = "TikTok Sans"

FONT_SIZE = 12

TEXT_COLOR = "#FFFF00"
OUTLINE_COLOR = "#000000"

OUTLINE = 1.8
SHADOW = 0

WORDS_PER_GROUP = 2

# Distance from bottom
MARGIN_V = 40


# ==========================================
# HELPERS
# ==========================================


def hex_to_ass_color(hex_color):
    hex_color = hex_color.replace("#", "")

    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    return pysubs2.Color(r, g, b)


# ==========================================
# CREATE ASS
# ==========================================

subs = pysubs2.SSAFile()

style = pysubs2.SSAStyle()

style.fontname = FONT
style.fontsize = FONT_SIZE

style.primarycolor = hex_to_ass_color(TEXT_COLOR)
style.outlinecolor = hex_to_ass_color(OUTLINE_COLOR)

style.bold = True

style.outline = OUTLINE
style.shadow = SHADOW

# Bottom center
style.alignment = 2

# Small bottom margin
style.marginv = MARGIN_V

style.borderstyle = 1

# Better spacing
style.spacing = 0.2

subs.styles["Default"] = style

# ==========================================
# EVENTS
# ==========================================

for i in range(0, len(captions_json), WORDS_PER_GROUP):

    group = captions_json[i : i + WORDS_PER_GROUP]

    # NO UPPERCASE
    phrase = " ".join(w["word"] for w in group)

    # Prevent weird wrapping
    phrase = "{\\q2}" + phrase

    start_time = group[0]["start"]
    end_time = group[-1]["end"]

    event = pysubs2.SSAEvent(
        start=pysubs2.make_time(s=start_time),
        end=pysubs2.make_time(s=end_time),
        text=phrase,
    )

    subs.events.append(event)

# Save ASS
subs.save(ASS_FILE)

print(f"\nSaved ASS file: {ASS_FILE}")

# ==========================================
# PRINT ASS FOR DEBUG
# ==========================================

with open(ASS_FILE, "r") as f:
    ass_content = f.read()

print("\n========== ASS ==========\n")
print(ass_content)
print("\n=========================\n")

# ==========================================
# VERIFY FONT
# ==========================================

print("\nChecking installed fonts...\n")

subprocess.run("fc-list | grep -i 'tiktok'", shell=True)

print("\nIf nothing printed above, TikTok Sans is NOT installed.\n")

# ==========================================
# FFMPEG
# ==========================================

cmd = [
    "ffmpeg",
    "-y",
    "-i",
    INPUT_VIDEO,
    "-vf",
    f"ass='{ASS_FILE}'",
    "-c:v",
    "libx264",
    "-preset",
    "fast",
    "-crf",
    "20",
    "-c:a",
    "copy",
    OUTPUT_VIDEO,
]

print("\nRunning FFmpeg:\n")
print(" ".join(cmd))
print()

result = subprocess.run(cmd)

# ==========================================
# RESULT
# ==========================================

if result.returncode == 0:
    print("\n✅ Success")
    print(f"\nOutput: {OUTPUT_VIDEO}")

    print("\nPreview:")
    print(f'ffplay "{OUTPUT_VIDEO}"')

else:
    print("\n❌ FFmpeg failed")

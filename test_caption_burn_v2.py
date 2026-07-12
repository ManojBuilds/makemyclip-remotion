#!/usr/bin/env python3
"""TikTok-style karaoke captions at bottom with proper font handling."""

import pysubs2
import subprocess
import os

# ==========================================
# CONFIG
# ==========================================

INPUT_VIDEO = "trimmed_video_clips/elon_musk_s_crazy_ai_chip_moment_n6p3f.mp4"
OUTPUT_VIDEO = "trimmed_video_clips/test_captioned_v2.mp4"
ASS_FILE = os.path.abspath("trimmed_video_clips/test_subs_v2.ass")

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

# Style Settings
FONT = "THE BOLD FONT"
FONT_SIZE = 60 # Sized relative to 720p/1080p width
FONT_COLOR = "#FFFFFF"
HIGHLIGHT_COLOR = "#FFD700"
STROKE_COLOR = "#000000"
STROKE_WIDTH = 3.0
SHADOW = True
POSITION_Y = 0.75 # 75% down the screen
UPPERCASE = True

WORDS_PER_PHRASE = 6

# ==========================================
# HELPERS
# ==========================================

def hex_to_ass_color(hex_color, alpha=0):
    hex_color = hex_color.replace("#", "")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return pysubs2.Color(r, g, b, alpha)

# ==========================================
# GENERATE ASS
# ==========================================

print("Generating ASS file...")
subs = pysubs2.SSAFile()

# Base resolution
V_WIDTH = 1080
V_HEIGHT = 1920
subs.info["PlayResX"] = V_WIDTH
subs.info["PlayResY"] = V_HEIGHT
subs.info["ScaledBorderAndShadow"] = "yes"
subs.info["WrapStyle"] = 0

scale_factor = V_HEIGHT / 720
scaled_font_size = int(FONT_SIZE * scale_factor)
scaled_font_size = max(50, min(160, scaled_font_size))

style = pysubs2.SSAStyle()
style.fontname = FONT
style.fontsize = scaled_font_size
style.primarycolor = hex_to_ass_color(FONT_COLOR)
style.outlinecolor = hex_to_ass_color(STROKE_COLOR)
style.outline = STROKE_WIDTH * (V_WIDTH / 720)

if SHADOW:
    style.shadow = 3.0 * scale_factor
    style.backcolor = pysubs2.Color(0, 0, 0, 180)
else:
    style.shadow = 0.0

style.alignment = 2
style.marginl = 80
style.marginr = 80

margin_v = int((1 - POSITION_Y) * V_HEIGHT)
margin_v = max(int(0.1 * V_HEIGHT), min(int(0.9 * V_HEIGHT), margin_v))
style.marginv = margin_v

style.bold = True
style.spacing = 1.0 

subs.styles["Default"] = style

words = []
for item in captions_json:
    w = item["word"]
    if UPPERCASE:
        w = w.upper()
    words.append({"word": w, "start": item["start"], "end": item["end"]})

h_color = hex_to_ass_color(HIGHLIGHT_COLOR)
p_color = hex_to_ass_color(FONT_COLOR)
h_tag = f"\\c&H{h_color.b:02X}{h_color.g:02X}{h_color.r:02X}&"
reset_tag = f"\\c&H{p_color.b:02X}{p_color.g:02X}{p_color.r:02X}&"

for i in range(0, len(words), WORDS_PER_PHRASE):
    phrase_group = words[i:i + WORDS_PER_PHRASE]
    
    # Calculate group end time
    group_end = phrase_group[-1]["end"]
    
    # We want to display the phrase, highlighting word by word.
    for active_idx, active_word in enumerate(phrase_group):
        highlight_start = active_word["start"]
        # The end of this highlight is the start of the next word, or group end
        highlight_end = active_word["end"]
        if active_idx < len(phrase_group) - 1:
            highlight_end = phrase_group[active_idx + 1]["start"]
        
        text_parts = []
        for w_idx, w in enumerate(phrase_group):
            word_text = w["word"]
            if w_idx == active_idx:
                part = f"{{{h_tag}}}{word_text}{{{reset_tag}}}"
            else:
                part = word_text
            
            if w_idx > 0 and w_idx % 3 == 0:
                text_parts.append("\\N" + part)
            else:
                text_parts.append(part)
        
        event_text = "{\\q2}" + " ".join(text_parts).replace(" \\N", "\\N")
        
        event = pysubs2.SSAEvent(
            start=pysubs2.make_time(s=highlight_start),
            end=pysubs2.make_time(s=highlight_end),
            text=event_text
        )
        subs.events.append(event)

subs.save(ASS_FILE)
print(f"Saved ASS file: {ASS_FILE}")

# ==========================================
# BURN WITH FFMPEG
# ==========================================

cmd = [
    "ffmpeg", "-y",
    "-i", INPUT_VIDEO,
    "-vf", f"ass='{ASS_FILE}'",
    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
    "-c:a", "copy",
    OUTPUT_VIDEO
]

print(f"\nRunning FFmpeg...\n")
result = subprocess.run(cmd)

if result.returncode == 0:
    print(f"\n✅ Success: {OUTPUT_VIDEO}")
else:
    print("\n❌ FFmpeg failed")

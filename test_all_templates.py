#!/usr/bin/env python3
"""Test all caption templates locally."""

import pysubs2
import subprocess
import os

INPUT_VIDEO = "trimmed_video_clips/input.mp4"

CAPTION_TEMPLATES = {
    "default": {
        "name": "TikTok Pink",
        "font_family": "TikTok Sans",
        "font_size": 38,
        "font_color": "#FFFFFF",
        "highlight_color": "#FE2C55",
        "stroke_color": "#000000",
        "stroke_width": 4.0,
        "background": False,
        "background_color": "transparent",
        "animation": "bounce",
        "future_dim": False,
        "shadow": True,
        "shadow_depth": 2.0,
        "letter_spacing": 1.5,
        "uppercase": True,
        "highlight_scale": 1.15,
        "power_color": "#00F5FF",
        "position_y": 0.75,
        "max_words": 3,
        "speaker_colors": {
            "speaker_1": "#E0F7FA",
            "speaker_2": "#FFFFFF",
        },
    },
    "hormozi": {
        "name": "Bold Lime (Hormozi)",
        "font_family": "Montserrat",
        "font_size": 46,
        "font_color": "#FFFFFF",
        "highlight_color": "#00FF57",
        "stroke_color": "#000000",
        "stroke_width": 5.5,
        "background": False,
        "background_color": "transparent",
        "animation": "bounce",
        "future_dim": True,
        "shadow": True,
        "shadow_depth": 3.0,
        "letter_spacing": 2.0,
        "uppercase": True,
        "highlight_scale": 1.22,
        "power_color": "#FFE600",
        "position_y": 0.70,
        "max_words": 3,
        "speaker_colors": {
            "speaker_1": "#FFFF54",
            "speaker_2": "#FFFFFF",
        },
    },
    "mrbeast": {
        "name": "Wobbly Yellow (MrBeast)",
        "font_family": "Bebas Neue",
        "font_size": 48,
        "font_color": "#FFE600",
        "highlight_color": "#FFFFFF",
        "stroke_color": "#000000",
        "stroke_width": 5.0,
        "background": False,
        "background_color": "transparent",
        "animation": "wobble",
        "future_dim": True,
        "shadow": True,
        "shadow_depth": 3.0,
        "letter_spacing": 1.5,
        "uppercase": True,
        "highlight_scale": 1.20,
        "power_color": "#FF3A3A",
        "position_y": 0.68,
        "max_words": 3,
        "speaker_colors": {
            "speaker_1": "#FFE600",
            "speaker_2": "#FFFFFF",
        },
    },
    "minimal": {
        "name": "Frosted Minimal",
        "font_family": "Inter",
        "font_size": 28,
        "font_color": "#FFFFFF",
        "highlight_color": "#FFD700",
        "stroke_color": "transparent",
        "stroke_width": 0.0,
        "background": True,
        "background_color": "#000000AA",
        "animation": "fade",
        "future_dim": False,
        "shadow": True,
        "shadow_depth": 2.0,
        "letter_spacing": 1.0,
        "uppercase": False,
        "highlight_scale": 1.10,
        "power_color": "#FFD700",
        "position_y": 0.80,
        "max_words": 4,
        "speaker_colors": {
            "speaker_1": "#FFE082",
            "speaker_2": "#FFFFFF",
        },
    },
    "podcast": {
        "name": "Dual Podcast",
        "font_family": "TikTok Sans",
        "font_size": 28,
        "font_color": "#FFFFFF",
        "highlight_color": "#FFFFFF",
        "stroke_color": "#000000",
        "stroke_width": 1.2,
        "background": False,
        "background_color": "transparent",
        "animation": "none",
        "future_dim": False,
        "shadow": True,
        "shadow_depth": 1.0,
        "shadow_alpha": 220,
        "position_y": 0.75,
        "uppercase": True,
        "max_words": 3,
        "speaker_colors": {
            "speaker_1": "#F0E547",
            "speaker_2": "#EFF6FE",
        },
    },
}

# Tag each word with a speaker field.
# speaker_1 = interviewer asking the question
# speaker_2 = the person answering
# ⬇ Adjust speaker tags to match your actual audio transcript.
captions_json = [
    {"word": "Elon", "start": 0, "end": 0.239, "speaker": "speaker_1"},
    {"word": "that", "start": 0, "end": 0.24, "speaker": "speaker_1"},
    {"word": "crazy", "start": 0.24, "end": 0.56, "speaker": "speaker_1"},
    {"word": "AI", "start": 0.56, "end": 1.04, "speaker": "speaker_1"},
    {"word": "chip.", "start": 1.04, "end": 1.44, "speaker": "speaker_1"},
    {"word": "Right.", "start": 1.44, "end": 1.76, "speaker": "speaker_2"},
    {"word": "DGX", "start": 1.76, "end": 2.24, "speaker": "speaker_2"},
    {"word": "Spark.", "start": 2.24, "end": 2.64, "speaker": "speaker_2"},
    {"word": "Yeah.", "start": 2.64, "end": 2.96, "speaker": "speaker_2"},
    {"word": "Oh,", "start": 2.96, "end": 3.36, "speaker": "speaker_2"},
    {"word": "that", "start": 3.36, "end": 3.52, "speaker": "speaker_2"},
    {"word": "was", "start": 3.52, "end": 3.68, "speaker": "speaker_2"},
    {"word": "a", "start": 3.68, "end": 3.76, "speaker": "speaker_2"},
    {"word": "big", "start": 3.76, "end": 3.84, "speaker": "speaker_2"},
    {"word": "moment.", "start": 3.84, "end": 4.16, "speaker": "speaker_2"},
    {"word": "That", "start": 4.335, "end": 4.655, "speaker": "speaker_2"},
    {"word": "was", "start": 4.655, "end": 4.735, "speaker": "speaker_2"},
    {"word": "a", "start": 4.735, "end": 4.815, "speaker": "speaker_2"},
    {"word": "huge", "start": 4.815, "end": 4.975, "speaker": "speaker_2"},
    {"word": "moment.", "start": 4.975, "end": 5.055, "speaker": "speaker_2"},
    {"word": "Crazy", "start": 5.295, "end": 5.775, "speaker": "speaker_2"},
    {"word": "to", "start": 5.775, "end": 6.095, "speaker": "speaker_2"},
    {"word": "be", "start": 6.095, "end": 6.175, "speaker": "speaker_2"},
    {"word": "there.", "start": 6.175, "end": 6.415, "speaker": "speaker_2"},
    {"word": "I", "start": 6.415, "end": 6.495, "speaker": "speaker_2"},
    {"word": "was", "start": 6.495, "end": 6.655, "speaker": "speaker_2"},
    {"word": "like", "start": 6.655, "end": 6.815, "speaker": "speaker_2"},
    {"word": "watching", "start": 6.815, "end": 7.375, "speaker": "speaker_2"},
    {"word": "these", "start": 7.375, "end": 7.935, "speaker": "speaker_2"},
    {"word": "wizards", "start": 8.175, "end": 8.655, "speaker": "speaker_2"},
    {"word": "of", "start": 8.655, "end": 8.895, "speaker": "speaker_2"},
    {"word": "tech,", "start": 8.895, "end": 9.375, "speaker": "speaker_2"},
    {"word": "like,", "start": 9.375, "end": 9.775, "speaker": "speaker_2"},
    {"word": "exchange", "start": 9.775, "end": 10.575, "speaker": "speaker_1"},
    {"word": "information", "start": 10.895, "end": 11.615, "speaker": "speaker_1"},
    {"word": "and", "start": 11.615, "end": 11.935, "speaker": "speaker_1"},
    {"word": "and", "start": 11.935, "end": 12.175, "speaker": "speaker_1"},
    {"word": "what", "start": 12.175, "end": 12.415, "speaker": "speaker_1"},
    {"word": "you're", "start": 12.495, "end": 12.735, "speaker": "speaker_1"},
    {"word": "giving", "start": 12.735, "end": 12.895, "speaker": "speaker_1"},
    {"word": "him", "start": 12.895, "end": 13.135, "speaker": "speaker_1"},
    {"word": "this", "start": 13.135, "end": 13.375, "speaker": "speaker_1"},
    {"word": "crazy", "start": 13.375, "end": 13.695, "speaker": "speaker_1"},
    {"word": "device.", "start": 13.695, "end": 14.335, "speaker": "speaker_1"},
]


def hex_to_ass_color(hex_color, alpha=0):
    if hex_color is None or hex_color == "transparent":
        return pysubs2.Color(0, 0, 0, 255)  # Fully transparent
    hex_color = hex_color.replace("#", "")
    r = 255
    g = 255
    b = 255
    a = alpha
    if len(hex_color) >= 6:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
    if len(hex_color) == 8:
        # Hex color with alpha e.g. #000000AA -> AA is alpha.
        # ASS uses 0 for opaque, 255 for transparent
        a_hex = int(hex_color[6:8], 16)
        a = 255 - a_hex
    return pysubs2.Color(r, g, b, a)


def ass_color_tag(hex_color):
    """Return an ASS inline \\c color override tag string for the given hex color."""
    c = hex_to_ass_color(hex_color)
    return f"\\c&H{c.b:02X}{c.g:02X}{c.r:02X}&"


def generate_ass(template, output_path):
    subs = pysubs2.SSAFile()
    V_WIDTH = 1080
    V_HEIGHT = 1920
    subs.info["PlayResX"] = V_WIDTH
    subs.info["PlayResY"] = V_HEIGHT
    subs.info["ScaledBorderAndShadow"] = "yes"
    subs.info["WrapStyle"] = 0

    scale_factor = V_HEIGHT / 720
    scaled_font_size = int(template.get("font_size", 38) * scale_factor)
    scaled_font_size = max(50, min(160, scaled_font_size))

    style = pysubs2.SSAStyle()
    style.fontname = template.get("font_family", "Montserrat")
    style.fontsize = scaled_font_size
    style.primarycolor = hex_to_ass_color(template.get("font_color", "#FFFFFF"))
    style.outlinecolor = hex_to_ass_color(template.get("stroke_color", "#000000"))
    style.outline = (template.get("stroke_width") or 0) * (V_WIDTH / 720)

    if template.get("background"):
        style.borderstyle = 3  # Opaque box
        style.backcolor = hex_to_ass_color(template.get("background_color"))
        # Padding in ASS is controlled by outline width. Set a generous uniform padding matching our preview layout:
        style.outline = 11.5 * (V_WIDTH / 720)
        if template.get("shadow"):
            depth = template.get("shadow_depth", 8.0)
            style.shadow = depth * scale_factor
        else:
            style.shadow = 0.0
    else:
        style.borderstyle = 1  # Outline
        if template.get("shadow"):
            depth = template.get("shadow_depth", 8.0)
            alpha = template.get("shadow_alpha", 0)
            style.shadow = depth * scale_factor
            style.backcolor = pysubs2.Color(0, 0, 0, alpha)
        else:
            style.shadow = 0.0

    style.alignment = 2
    style.marginl = 140
    style.marginr = 140

    margin_v = int((1 - template.get("position_y", 0.8)) * V_HEIGHT)
    margin_v = max(int(0.1 * V_HEIGHT), min(int(0.9 * V_HEIGHT), margin_v))
    style.marginv = margin_v

    style.bold = True
    style.spacing = template.get("letter_spacing", 1.0)
    subs.styles["Default"] = style

    # ── Hook Style for Roy Lee ───────────────────────────────────────────
    if template.get("animation") == "roylee":
        hook_style = pysubs2.SSAStyle()
        hook_style.fontname = template.get(
            "hook_font_family", template.get("font_family", "Inter")
        )
        hook_scaled_fs = int(template.get("hook_font_size", 52) * scale_factor)
        hook_style.fontsize = max(50, min(160, hook_scaled_fs))
        hook_style.primarycolor = hex_to_ass_color(
            template.get("hook_font_color", "#FFFFFF")
        )
        hook_style.outlinecolor = hex_to_ass_color(template.get("hook_stroke_color"))
        hook_style.outline = (template.get("hook_stroke_width") or 0) * (V_WIDTH / 720)
        hook_style.borderstyle = 3  # Hook pill has background
        hook_style.backcolor = hex_to_ass_color(
            template.get("hook_background_color", "#CC000000")
        )
        hook_style.alignment = 2
        hook_style.marginl = 100
        hook_style.marginr = 100
        hook_margin_v = int((1 - template.get("hook_position_y", 0.28)) * V_HEIGHT)
        hook_style.marginv = max(
            int(0.1 * V_HEIGHT), min(int(0.9 * V_HEIGHT), hook_margin_v)
        )
        hook_style.bold = True
        hook_style.spacing = 1.0
        subs.styles["Hook"] = hook_style

    # Build word list — apply uppercase and carry speaker tag through
    words = []
    for item in captions_json:
        w = item["word"]
        if template.get("uppercase"):
            w = w.upper()
        words.append(
            {
                "word": w,
                "start": item["start"],
                "end": item["end"],
                "speaker": item.get("speaker", "speaker_1"),  # default if tag missing
            }
        )

    # Speaker colors (only used when template has "speaker_colors" key)
    speaker_colors = template.get("speaker_colors", {})
    default_color = template.get("font_color", "#FFFFFF")

    # Karaoke / Pop / Bounce highlight & scaling tags
    h_color = hex_to_ass_color(template.get("highlight_color", default_color))
    p_color = hex_to_ass_color(default_color)
    h_tag = f"\\c&H{h_color.b:02X}{h_color.g:02X}{h_color.r:02X}&"
    reset_tag = f"\\c&H{p_color.b:02X}{p_color.g:02X}{p_color.r:02X}&"

    scale_pct = int(template.get("highlight_scale", 1.18) * 100)
    h_scale_tag = f"\\fscx{scale_pct}\\fscy{scale_pct}" if scale_pct != 100 else ""
    reset_scale_tag = "\\fscx100\\fscy100" if scale_pct != 100 else ""

    power_hex = template.get("power_color")

    WORDS_PER_PHRASE = template.get("max_words", 3)

    for i in range(0, len(words), WORDS_PER_PHRASE):
        phrase_group = words[i : i + WORDS_PER_PHRASE]

        # ── Roy Lee: Dual-layer Hook + Subtitle ──────────────────────────
        if template.get("animation") == "roylee":
            hook_duration = template.get("hook_duration_s", 3.0)
            is_hook = phrase_group[0]["start"] < hook_duration
            phrase_text = " ".join(w["word"] for w in phrase_group)

            event_text = "{\\q1}" + phrase_text
            event = pysubs2.SSAEvent(
                start=pysubs2.make_time(s=phrase_group[0]["start"]),
                end=pysubs2.make_time(s=phrase_group[-1]["end"]),
                text=event_text,
                style="Hook" if is_hook else "Default",
            )
            subs.events.append(event)

        # ── Karaoke / Pop / Bounce / Wobble / Elastic / Fade Word: word-by-word highlight & scale ───────
        elif template.get("animation") in [
            "karaoke",
            "pop",
            "bounce",
            "wobble",
            "elastic",
            "fade_word",
        ]:
            for active_idx, active_word in enumerate(phrase_group):
                highlight_start = active_word["start"]
                highlight_end = active_word["end"]
                if active_idx < len(phrase_group) - 1:
                    highlight_end = phrase_group[active_idx + 1]["start"]

                text_parts = []
                for w_idx, w in enumerate(phrase_group):
                    word_text = w["word"]

                    # Check if power word
                    is_power = False
                    if power_hex:
                        clean_w = word_text.upper()
                        if clean_w in [
                            "AI",
                            "DGX",
                            "CRAZY",
                            "HUGE",
                            "BIG",
                            "WIZARDS",
                            "DEVICE",
                            "ELON",
                        ] or any(c in clean_w for c in ["!", "?"]):
                            is_power = True

                    # Resolve speaker-specific base color for this word
                    w_speaker = w.get("speaker", "speaker_1")
                    w_base_hex = speaker_colors.get(w_speaker, default_color)
                    w_base_color = hex_to_ass_color(w_base_hex)

                    if w_idx < active_idx:
                        # Past word: fully opaque, speaker color, normal scale
                        tags = f"\\c&H{w_base_color.b:02X}{w_base_color.g:02X}{w_base_color.r:02X}&\\1a&H00&\\3a&H00&\\fscx100\\fscy100\\frz0"
                    elif w_idx == active_idx:
                        # Active word: Highlight color, opaque, animated scale/rotation!
                        anim_type = template.get("animation", "karaoke")
                        scale_pct = int(template.get("highlight_scale", 1.18) * 100)
                        settle_scale = scale_pct
                        peak_scale = int(scale_pct * 1.16)
                        elastic_peak_x = int(scale_pct * 1.28)
                        elastic_peak_y = int(scale_pct * 1.24)
                        elastic_drop_x = int(scale_pct * 0.90)
                        elastic_drop_y = int(scale_pct * 0.94)

                        if anim_type == "bounce":
                            # Punchy scale up with a dynamic slight tilt (-3 deg) that settles back
                            h_scale_tag = f"\\frz0\\fscx100\\fscy100\\t(0,60,\\frz-3\\fscx{peak_scale}\\fscy{peak_scale})\\t(60,150,\\frz-1\\fscx{settle_scale}\\fscy{settle_scale})"
                            tags = f"\\c&H{h_color.b:02X}{h_color.g:02X}{h_color.r:02X}&\\1a&H00&\\3a&H00&{h_scale_tag}"
                        elif anim_type == "wobble":
                            # Springy rotation wobble (from -6 deg to +4 deg to settle)
                            h_scale_tag = f"\\frz0\\fscx100\\fscy100\\t(0,50,\\frz-6\\fscx{peak_scale}\\fscy{peak_scale})\\t(50,110,\\frz4\\fscx{settle_scale}\\fscy{settle_scale})\\t(110,185,\\frz-2\\fscx{settle_scale}\\fscy{settle_scale})"
                            tags = f"\\c&H{h_color.b:02X}{h_color.g:02X}{h_color.r:02X}&\\1a&H00&\\3a&H00&{h_scale_tag}"
                        elif anim_type == "elastic":
                            # Squash & stretch: stretch wide and flat first, then stretch tall and narrow, then settle
                            h_scale_tag = f"\\fscx100\\fscy100\\t(0,50,\\fscx{elastic_peak_x}\\fscy{elastic_drop_y})\\t(50,110,\\fscx{elastic_drop_x}\\fscy{elastic_peak_y})\\t(110,180,\\fscx{settle_scale}\\fscy{settle_scale})\\frz0"
                            tags = f"\\c&H{h_color.b:02X}{h_color.g:02X}{h_color.r:02X}&\\1a&H00&\\3a&H00&{h_scale_tag}"
                        elif anim_type == "fade_word":
                            # Grow and fade-in from 0 to 100% opacity in 100ms
                            h_scale_tag = f"\\fscx90\\fscy90\\t(0,110,\\fscx{settle_scale}\\fscy{settle_scale})\\frz0"
                            tags = f"\\c&H{w_base_color.b:02X}{w_base_color.g:02X}{w_base_color.r:02X}&\\1a&HFF&\\3a&HFF&\\t(0,110,\\1a&H00&\\3a&H00&\\c&H{h_color.b:02X}{h_color.g:02X}{h_color.r:02X}&){h_scale_tag}"
                        elif anim_type == "pop":
                            h_scale_tag = f"\\fscx100\\fscy100\\t(0,60,\\fscx{peak_scale}\\fscy{peak_scale})\\t(60,130,\\fscx{settle_scale}\\fscy{settle_scale})\\frz0"
                            tags = f"\\c&H{h_color.b:02X}{h_color.g:02X}{h_color.r:02X}&\\1a&H00&\\3a&H00&{h_scale_tag}"
                        else:  # karaoke / other
                            tags = f"\\c&H{h_color.b:02X}{h_color.g:02X}{h_color.r:02X}&\\1a&H00&\\3a&H00&\\fscx{settle_scale}\\fscy{settle_scale}\\frz0"
                    else:
                        # Future word
                        if template.get("future_dim", False):
                            # Dimmed (approx 66% opacity: alpha is AA)
                            tags = f"\\c&H{w_base_color.b:02X}{w_base_color.g:02X}{w_base_color.r:02X}&\\1a&HAA&\\3a&HAA&\\fscx100\\fscy100\\frz0"
                        else:
                            # Fully opaque, default/speaker color, or power color
                            if is_power and power_hex:
                                pw_color = hex_to_ass_color(power_hex)
                                tags = f"\\c&H{pw_color.b:02X}{pw_color.g:02X}{pw_color.r:02X}&\\1a&H00&\\3a&H00&\\fscx100\\fscy100\\frz0"
                            else:
                                tags = f"\\c&H{w_base_color.b:02X}{w_base_color.g:02X}{w_base_color.r:02X}&\\1a&H00&\\3a&H00&\\fscx100\\fscy100\\frz0"

                    part = f"{{{tags}}}{word_text}"
                    text_parts.append(part)

                event_text = "{\\q1}" + " ".join(text_parts).replace(" \\N", "\\N")
                event = pysubs2.SSAEvent(
                    start=pysubs2.make_time(s=highlight_start),
                    end=pysubs2.make_time(s=highlight_end),
                    text=event_text,
                )
                subs.events.append(event)

        # ── Fade / None: whole phrase at once, with optional fade/colors ──
        else:
            phrase_text = " ".join(w["word"] for w in phrase_group)

            prefix = (
                "{\\q1\\fad(150,150)}"
                if template.get("animation") == "fade"
                else "{\\q1}"
            )

            if speaker_colors:
                speaker_key = phrase_group[0].get("speaker", "speaker_1")
                phrase_hex = speaker_colors.get(speaker_key, default_color)
                color_tag = ass_color_tag(phrase_hex)
                event_text = prefix + "{" + color_tag + "}" + phrase_text
            else:
                event_text = prefix + phrase_text

            event = pysubs2.SSAEvent(
                start=pysubs2.make_time(s=phrase_group[0]["start"]),
                end=pysubs2.make_time(s=phrase_group[-1]["end"]),
                text=event_text,
            )
            subs.events.append(event)

    subs.save(output_path)
    return output_path


def burn(template_key, template):
    print(f"\n--- Processing {template['name']} ({template_key}) ---")
    ass_file = os.path.abspath(f"trimmed_video_clips/test_subs_{template_key}.ass")
    out_file = f"trimmed_video_clips/test_{template_key}.mp4"

    generate_ass(template, ass_file)

    cmd = [
        "ffmpeg",
        "-y",
        "-hwaccel",
        "auto",
        "-i",
        INPUT_VIDEO,
        "-vf",
        f"ass='{ass_file}'",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "23",
        "-c:a",
        "copy",
        out_file,
    ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Generated: {out_file}")


TEMPLATE_TO_TEST = "all"  # Change to a template key, or "all" to run all

if __name__ == "__main__":
    if TEMPLATE_TO_TEST == "all":
        for key, template in CAPTION_TEMPLATES.items():
            burn(key, template)
        print("\n✅ All templates processed!")
    else:
        if TEMPLATE_TO_TEST in CAPTION_TEMPLATES:
            burn(TEMPLATE_TO_TEST, CAPTION_TEMPLATES[TEMPLATE_TO_TEST])
            print(f"\n✅ Template '{TEMPLATE_TO_TEST}' processed!")
        else:
            print(f"❌ Template '{TEMPLATE_TO_TEST}' not found.")

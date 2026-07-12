"""ASS subtitle file builder.

Takes a transcript + ``CaptionStyle`` and writes an ``.ass`` subtitle file that
matches the React ``CaptionRenderer`` previews on the frontend.
"""

from __future__ import annotations

import logging
from typing import Iterable

from colors import ass_color_override, hex_to_ass_color
from fonts import resolve_font_name
from presets import (
    ALWAYS_UPPERCASE,
    DEFAULT_PRESET_STYLE,
    get_preset_style,
    normalize_preset,
)

logger = logging.getLogger("makemyclip.ass_builder")

V_WIDTH, V_HEIGHT = 1080, 1920
SCALE_FACTOR = V_HEIGHT / 1920.0
CX, CY = V_WIDTH // 2, V_HEIGHT // 2
_MAX_SAFE_WIDTH = 840.0

_SHADOW_TAG = r"\xshad2\yshad2\blur0\4a&H20&"
_NO_SHADOW_TAG = r"\xshad0\yshad0\blur0"

_SPRING_CONFIG: dict[str, dict[str, int]] = {
    "hormozi": {"scale_from": 94, "overshoot": 103},
    "beast": {"scale_from": 94, "overshoot": 105},
    "opus": {"scale_from": 94, "overshoot": 103},
    "popline": {"scale_from": 94, "overshoot": 103},
    "neon-glow": {"scale_from": 94, "overshoot": 103},
    "sticker": {"scale_from": 94, "overshoot": 103},
}
_BOTTOM_ANCHOR = frozenset({"hormozi", "popline", "neon-glow", "simple", "opus"})
_CENTER_ANCHOR = frozenset({"beast", "boxed"})


def spring_pop(scale_from: int = 94, overshoot: int = 103, duration: int = 150) -> str:
    """Subtle scale-in with a short overshoot settle (≤150 ms)."""
    mid = int(duration * 0.6)
    return (
        rf"\fscx{scale_from}\fscy{scale_from}"
        rf"\t(0,{mid},\fscx{overshoot}\fscy{overshoot})"
        rf"\t({mid},{duration},\fscx100\fscy100)"
    )


def _styling_to_dict(styling) -> dict:
    if hasattr(styling, "model_dump"):
        return styling.model_dump()
    if hasattr(styling, "dict"):
        return styling.dict()
    if isinstance(styling, dict):
        return dict(styling)
    return dict(styling)


def _flatten_transcript(transcript) -> list[dict]:
    raw_items: list[dict] = []
    if not isinstance(transcript, Iterable):
        return raw_items
    for item in transcript:
        if not isinstance(item, dict):
            item_dict = (
                item.model_dump()
                if hasattr(item, "model_dump")
                else item.dict() if hasattr(item, "dict") else dict(item)
            )
        else:
            item_dict = item
        nested = item_dict.get("words")
        (
            raw_items.extend(nested)
            if isinstance(nested, list)
            else raw_items.append(item_dict)
        )
    return raw_items


def _tpl(template: dict, snake: str, camel: str):
    val = template.get(snake)
    return val if val is not None else template.get(camel)


def _resolve_overrides(template: dict) -> dict:
    font_size = _tpl(template, "font_size", "fontSize")
    stroke_width = _tpl(template, "stroke_width", "strokeWidth")
    position_y = _tpl(template, "position_y", "positionY")
    shadow_depth = _tpl(template, "shadow_depth", "shadowDepth")
    return {
        "font": _tpl(template, "font_family", "fontFamily"),
        "fontsize": float(font_size) if font_size is not None else None,
        "font_color": _tpl(template, "font_color", "fontColor"),
        "stroke_color": _tpl(template, "stroke_color", "strokeColor"),
        "stroke_width": float(stroke_width) if stroke_width is not None else None,
        "shadow_depth": float(shadow_depth) if shadow_depth is not None else None,
        "shadow": template.get("shadow"),
        "position_y": float(position_y) if position_y is not None else None,
        "italic": template.get("italic"),
        "alignment": template.get("alignment"),
    }


def _build_style(base: dict, overrides: dict, template: dict):
    import pysubs2

    fontname, fontsize = base["fontname"], base["fontsize"]
    primarycolor = hex_to_ass_color(base["primary"])
    outlinecolor = hex_to_ass_color(base["outlinecolor"])
    outline, shadow = base["outline"], base["shadow"]
    backcolor = (
        hex_to_ass_color(*base["backcolor"])
        if base.get("backcolor")
        else hex_to_ass_color(None)
    )
    alignment, marginv = base["alignment"], base["marginv"]

    if overrides["font"]:
        fontname = overrides["font"]
    if overrides["fontsize"]:
        fontsize = overrides["fontsize"]
    if overrides["font_color"]:
        primarycolor = hex_to_ass_color(overrides["font_color"])

    transparent_stroke = overrides["stroke_width"] in (0, None) and overrides[
        "stroke_color"
    ] in ("transparent", None, "")
    if not transparent_stroke:
        if overrides["stroke_color"]:
            outlinecolor = hex_to_ass_color(overrides["stroke_color"])
        if overrides["stroke_width"] is not None:
            outline = float(overrides["stroke_width"])

    shadow = 0 if overrides["shadow_depth"] == 0.0 else 3
    if overrides["position_y"] is not None:
        marginv = int((1.0 - overrides["position_y"]) * V_HEIGHT)

    style = pysubs2.SSAStyle()
    style.fontname = resolve_font_name(fontname)
    style.fontsize = int(fontsize * SCALE_FACTOR)
    style.bold = True
    style.italic = overrides.get("italic") or False
    style.primarycolor = primarycolor
    style.outlinecolor = outlinecolor
    style.outline = outline * SCALE_FACTOR
    style.shadow = shadow * SCALE_FACTOR
    style.backcolor = backcolor
    style.borderstyle = base.get("borderstyle", 1)
    if "secondary" in base:
        style.secondarycolor = hex_to_ass_color(base["secondary"])
    style.alignment = (
        int(overrides["alignment"])
        if overrides.get("alignment") is not None
        else alignment
    )
    style.marginl = style.marginr = int(140 * SCALE_FACTOR)
    style.marginv = int(marginv * SCALE_FACTOR)
    style.spacing = template.get("letter_spacing", 0.0) or 0.0
    return style


def _safe_event_fontsize(phrase_group: list[dict], style_fontsize: int) -> int:
    longest = max(
        (w["word"].strip(".,!?\"'") for w in phrase_group), key=len, default=""
    )
    est = len(longest) * style_fontsize * 0.72
    return int(
        style_fontsize
        * min(1.0, _MAX_SAFE_WIDTH / est if est > _MAX_SAFE_WIDTH else 1.0)
    )


def _resolve_y_anchor(preset: str, position_y: float | None, fs: int) -> int | None:
    if preset not in _BOTTOM_ANCHOR | _CENTER_ANCHOR:
        return None
    if position_y is not None:
        raw = int(position_y * V_HEIGHT)
        return int(raw + fs / 2.0) if preset in _BOTTOM_ANCHOR else raw
    if preset in _BOTTOM_ANCHOR:
        margin = 150 if preset == "hormozi" else 130
        return V_HEIGHT - int(margin * SCALE_FACTOR)
    return CY


def build_animation(
    preset: str, fs: int, shadow_tag: str, *, animate: bool, y: int | None = None
) -> str:
    tags: list[str] = []
    if preset in _CENTER_ANCHOR:
        tags.append(r"\an5")
    if y is not None:
        tags.append(rf"\pos({CX},{y})")
    tags.append(shadow_tag)
    if animate and preset in _SPRING_CONFIG:
        tags.append(spring_pop(**_SPRING_CONFIG[preset]))
    tags.append(rf"\fs{fs}")
    return "{" + "".join(tags) + "}"


def build_word_line(
    phrase_group: list[dict],
    active_idx: int,
    preset: str,
    normal_color_hex: str,
    h_color_hex: str,
    stroke_c,
    stroke_bord: int,
) -> str:
    hi_tag, normal_tag = ass_color_override(h_color_hex), ass_color_override(
        normal_color_hex
    )
    normal_ass = hex_to_ass_color(normal_color_hex)
    parts: list[str] = []

    for w_idx, w in enumerate(phrase_group):
        if w_idx != active_idx:
            parts.append(w["word"])
            continue

        if preset == "box-highlight":
            hi = h_color_hex.lstrip("#")
            hi_r = int(hi[0:2], 16) if len(hi) >= 2 else 255
            hi_g = int(hi[2:4], 16) if len(hi) >= 4 else 220
            hi_b = int(hi[4:6], 16) if len(hi) >= 6 else 0
            parts.append(
                rf"{{\c&H000000&\3c&H{hi_b:02X}{hi_g:02X}{hi_r:02X}&"
                rf"\bord{int(18 * SCALE_FACTOR)}}}{w['word']}"
                rf"{{\c&H{normal_ass.b:02X}{normal_ass.g:02X}{normal_ass.r:02X}&"
                rf"\3c&H{stroke_c.b:02X}{stroke_c.g:02X}{stroke_c.r:02X}&\bord{stroke_bord}}}"
            )
        else:
            # Determine premium Canva/CapCut effects based on the preset
            active_prefix = ""
            active_suffix = ""

            if preset in ("hormozi", "beast", "sticker"):
                # Bold Pop scale effect (12% larger)
                active_prefix = r"\fscx112\fscy112"
                active_suffix = r"\fscx100\fscy100"
            elif preset == "popline":
                # Underline & scale effect
                active_prefix = r"\u1\fscx106\fscy106"
                active_suffix = r"\u0\fscx100\fscy100"
            elif preset == "neon-glow":
                # Glow/bloom & scale effect
                active_prefix = rf"\bord6\3c&H{stroke_c.b:02X}{stroke_c.g:02X}{stroke_c.r:02X}&\blur8\fscx110\fscy110"
                active_suffix = rf"\bord{stroke_bord}\3c&H{stroke_c.b:02X}{stroke_c.g:02X}{stroke_c.r:02X}&\blur0\fscx100\fscy100"
            elif preset == "opus":
                # Bouncy Pop scale effect (8% larger)
                active_prefix = r"\fscx108\fscy108"
                active_suffix = r"\fscx100\fscy100"

            parts.append(
                rf"{{{active_prefix}{hi_tag}}}{w['word']}{{{active_suffix}{normal_tag}}}"
            )

    return ("   " if preset == "box-highlight" else " ").join(parts)


def _emit_events(
    subs,
    preset: str,
    phrase_group: list[dict],
    p_start: float,
    p_end: float,
    fs: int,
    template: dict,
    overrides: dict,
    base: dict,
    h_color_hex: str,
    shadow_tag: str,
    global_crop_mode: str = "reframe",
) -> None:
    import pysubs2

    def add(start: float, end: float, text: str) -> None:
        subs.events.append(
            pysubs2.SSAEvent(
                start=pysubs2.make_time(s=start),
                end=pysubs2.make_time(s=end),
                text=text,
                style="Default",
            )
        )

    # Determine layout of this phrase
    phrase_layout = global_crop_mode
    layouts_in_group = [w.get("layout") for w in phrase_group if w.get("layout")]
    if layouts_in_group:
        phrase_layout = layouts_in_group[0]

    pos_y = overrides["position_y"]
    if phrase_layout in ("split", "course"):
        pos_y = 0.50
    elif phrase_layout == "letterbox":
        pos_y = 0.66
    elif phrase_layout in ("reframe", "single"):
        pos_y = 0.75

    y = _resolve_y_anchor(preset, pos_y, fs)
    uses_pos = preset in _BOTTOM_ANCHOR | _CENTER_ANCHOR

    if preset == "opus":
        y_val = y or CY
        line = "  " + " ".join(w["word"] for w in phrase_group) + "  "
        add(
            p_start,
            p_end,
            build_animation("opus", fs, shadow_tag, animate=True, y=y_val) + line,
        )
        return

    if preset == "simple":
        line = " ".join(w["word"] for w in phrase_group)
        pos_tag = rf"\pos(540,{y})" if y is not None else ""
        add(p_start, p_end, rf"{{{shadow_tag}\fs{fs}{pos_tag}}}{line}")
        return

    if preset == "karaoke":
        text, cursor = "", p_start
        for w in phrase_group:
            gap = w["start"] - cursor
            if gap > 0.01:
                text += f"{{\\K{int(gap * 100)}}}"
            text += f"{{\\K{max(0, int((w['end'] - w['start']) * 100))}}}{w['word']} "
            cursor = w["end"]
        tail = p_end - cursor
        if tail > 0.01:
            text += f"{{\\K{int(tail * 100)}}}"
        pos_tag = rf"\pos(540,{y})" if y is not None else ""
        add(p_start, p_end, rf"{{\fs{fs}{pos_tag}}}{text.strip()}")
        return

    normal_color = template.get("font_color") or base["primary"]
    stroke_c = hex_to_ass_color(
        "#000000"
        if overrides["stroke_color"] in (None, "transparent")
        else overrides["stroke_color"]
    )
    stroke_bord = (
        int(3 * SCALE_FACTOR)
        if overrides["stroke_width"] in (None, 0)
        else int(float(overrides["stroke_width"]) * SCALE_FACTOR)
    )

    for idx, word in enumerate(phrase_group):
        start = word["start"]
        end = phrase_group[idx + 1]["start"] if idx < len(phrase_group) - 1 else p_end
        line = build_word_line(
            phrase_group, idx, preset, normal_color, h_color_hex, stroke_c, stroke_bord
        )
        if preset == "box-highlight":
            prefix = rf"{{\fs{fs}}}"
        else:
            prefix = build_animation(
                preset,
                fs,
                shadow_tag,
                animate=idx == 0 and preset in _SPRING_CONFIG,
                y=y if uses_pos else None,
            )
        add(start, end, prefix + line)


def generate_ass(
    transcript, styling, output_path: str, crop_mode: str = "reframe"
) -> None:
    """Generate an ASS subtitle file from ``transcript`` + ``styling``."""
    import pysubs2

    template = _styling_to_dict(styling)
    if crop_mode in ("split", "course"):
        template["position_y"] = 0.50
    elif crop_mode == "letterbox":
        template["position_y"] = 0.66
        for snake, camel in (
            ("font_size", "fontSize"),
            ("stroke_width", "strokeWidth"),
            ("shadow_depth", "shadowDepth"),
        ):
            val = _tpl(template, snake, camel)
            if val is not None:
                template[snake] = template[camel] = float(val)
    elif crop_mode in ("reframe", "single", "auto"):
        template["position_y"] = 0.75

    overrides = _resolve_overrides(template)
    preset = normalize_preset(
        template.get("preset")
        or template.get("presetName")
        or template.get("animation")
        or "none"
    )

    subs = pysubs2.SSAFile()
    subs.info.update(
        {
            "PlayResX": V_WIDTH,
            "PlayResY": V_HEIGHT,
            "ScaledBorderAndShadow": "yes",
            "WrapStyle": 0,
        }
    )

    base = get_preset_style(preset)
    if crop_mode == "letterbox":
        base["fontsize"] = int(base["fontsize"])
        base["outline"], base["shadow"] = base["outline"], base["shadow"]

    subs.styles["Default"] = _build_style(base, overrides, template)

    raw_items = _flatten_transcript(transcript)
    do_upper = template.get("uppercase") or preset in ALWAYS_UPPERCASE
    words = [
        {
            "word": (
                (item.get("punctuated_word") or item.get("word", "")).upper()
                if do_upper
                else (item.get("punctuated_word") or item.get("word", ""))
            ),
            "start": item.get("start", 0.0),
            "end": item.get("end", 0.0),
            "speaker": item.get("speaker", "speaker_1") or "speaker_1",
            "layout": item.get("layout"),
        }
        for item in raw_items
    ]

    if not words:
        subs.save(output_path)
        logger.info("Saved empty ASS to %s", output_path)
        return

    words_per_phrase = template.get("max_words", 3) or 3
    h_color_hex = template.get("highlight_color", "#FFDC00")
    no_shadow = overrides.get("shadow") is False or overrides.get("shadow_depth") == 0.0

    groups = []
    current_group = []
    for w in words:
        if len(current_group) >= words_per_phrase:
            groups.append(current_group)
            current_group = [w]
        elif current_group and w.get("layout") != current_group[0].get("layout"):
            groups.append(current_group)
            current_group = [w]
        else:
            current_group.append(w)
    if current_group:
        groups.append(current_group)

    for group in groups:
        if not group:
            continue
        p_start, p_end = group[0]["start"], group[-1]["end"]
        if p_end <= p_start:
            continue

        fs = _safe_event_fontsize(group, subs.styles["Default"].fontsize)
        if preset == "simple":
            s_tag = _NO_SHADOW_TAG if no_shadow else _SHADOW_TAG
        elif preset == "box-highlight":
            s_tag = _NO_SHADOW_TAG
        elif preset == "neon-glow":
            # 2026 Gaming Glow: diffused shadow with high blur for neon bloom
            s_tag = _NO_SHADOW_TAG if no_shadow else r"\xshad3\yshad3\blur10\4a&H20&"
        else:
            s_tag = _SHADOW_TAG

        _emit_events(
            subs,
            preset,
            group,
            p_start,
            p_end,
            fs,
            template,
            overrides,
            base,
            h_color_hex,
            s_tag,
            crop_mode,
        )

    subs.save(output_path)
    logger.info("Saved ASS to %s with %d events", output_path, len(subs.events))

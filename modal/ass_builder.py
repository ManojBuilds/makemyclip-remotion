"""ASS subtitle file builder.

Takes a transcript + ``CaptionStyle`` and writes an ``.ass`` subtitle file for the
five premium presets defined in ``presets.py``. Each preset owns:

  * a *sentence entrance* animation  → ``ANIMATION_BUILDERS[preset]``
  * an *active-word effect*          → ``WORD_EFFECTS[preset]``

Dispatching through these registries keeps the renderer free of giant if/elif
chains and makes new presets trivial to add.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Callable, Iterable

from colors import ass_color_override, hex_to_ass_color
from fonts import resolve_font_name
from presets import (
    ALWAYS_UPPERCASE,
    DEFAULT_PRESET,
    DEFAULT_PRESET_STYLE,
    get_preset_style,
    normalize_preset,
)

logger = logging.getLogger("makemyclip.ass_builder")

# Curated multi-speaker highlight palettes (Speaker 1, Speaker 2, Speaker 3, Speaker 4)
SPEAKER_HIGHLIGHT_PALETTES: dict[str, list[str]] = {
    "impact": ["#FFE500", "#00F0FF", "#FF007A", "#34D399"],
    "creator": ["#00F0FF", "#FFE500", "#FF007A", "#A855F7"],
    "cinema": ["#FFB800", "#00F0FF", "#F43F5E", "#38BDF8"],
    "focus": ["#0A0A0A", "#0A0A0A", "#0A0A0A", "#0A0A0A"],
    "neon": ["#FF007A", "#00F0FF", "#FFE500", "#A855F7"],
    "luxury": ["#FFD700", "#00F0FF", "#F43F5E", "#38BDF8"],
}

SPEAKER_PILL_PALETTES: dict[str, list[str]] = {
    "focus": ["#FFE600", "#00F0FF", "#FF007A", "#34D399"],
}

# ── Canvas geometry ──────────────────────────────────────────────────────────
V_WIDTH, V_HEIGHT = 1080, 1920
SCALE_FACTOR = V_HEIGHT / 1920.0
CX, CY = V_WIDTH // 2, V_HEIGHT // 2
_MAX_SAFE_WIDTH = 840.0

# ── Shadow tags ──────────────────────────────────────────────────────────────
_SHADOW_TAG = r"\xshad3\yshad3\blur0\4a&H20&"
_NO_SHADOW_TAG = r"\xshad0\yshad0\blur0"
_NEON_SHADOW_TAG = r"\xshad0\yshad0\blur10\4a&H10&"

# ── Default word-effect timing (milliseconds) ────────────────────────────────
_WORD_ANIM_MS = 130


# ─────────────────────────────────────────────────────────────────────────────
# Animation context + registries
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class WordCtx:
    """Everything a word-effect builder needs to emit its active-word tags."""

    word: str
    fs: int
    highlight_tag: str  # ``\c&H..&`` for the active/highlight color
    normal_tag: str  # ``\c&H..&`` for the inactive color
    highlight_color_hex: str
    normal_color_hex: str
    stroke_c: object  # pysubs2.Color for the outline
    stroke_bord: int  # scaled outline width
    pill_color_hex: str  # focus pill background
    default_fsp: float = 0.0


# ── Sentence entrance animations (one per preset) ────────────────────────────
def impact_animation(fs: int, duration: int = 150) -> str:
    """Whole sentence squashes in: 90% → 106% → 100%."""
    mid = int(duration * 0.6)
    return (
        rf"\fscx90\fscy90"
        rf"\t(0,{mid},\fscx106\fscy106)"
        rf"\t({mid},{duration},\fscx100\fscy100)"
    )


def creator_animation(fs: int, duration: int = 150) -> str:
    """No sentence-level pop — motion lives on the active word."""
    return ""


def cinema_animation(fs: int, duration: int = 200) -> str:
    """Opacity-only fade in (FF → 00). No scaling."""
    return rf"\alpha&HFF&\t(0,{duration},\alpha&H00&)"


def focus_animation(fs: int, duration: int = 150) -> str:
    """No sentence-level motion — the pill animates per active word."""
    return ""


def neon_animation(fs: int, duration: int = 150) -> str:
    """No sentence-level motion — the glow pulses per active word."""
    return ""


def luxury_animation(fs: int, duration: int = 220) -> str:
    """Luxury Shimmer & Rise entrance: Opacity fade + subtle letter tracking expand + upward drift."""
    return (
        rf"\alpha&HFF&\fsp6.0"
        rf"\t(0,{duration},\alpha&H00&\fsp1.5)"
    )


ANIMATION_BUILDERS: dict[str, Callable[..., str]] = {
    "impact": impact_animation,
    "creator": creator_animation,
    "cinema": cinema_animation,
    "focus": focus_animation,
    "neon": neon_animation,
    "luxury": luxury_animation,
}


# ── Active-word effects (one per preset) ─────────────────────────────────────
def _wrap(active_prefix: str, ctx: WordCtx, active_suffix: str) -> str:
    """Wrap the active word with a prefix (entering highlight) and a suffix
    (restoring the inactive style for the following words on the same line)."""
    return (
        rf"{{{active_prefix}{ctx.highlight_tag}}}{ctx.word}"
        rf"{{{active_suffix}{ctx.normal_tag}}}"
    )


def impact_word_effect(ctx: WordCtx) -> str:
    """Punchy squash/stretch overshoot to 122% then settle to 112%."""
    mid = int(_WORD_ANIM_MS * 0.55)
    prefix = (
        rf"\fscx100\fscy100"
        rf"\t(0,{mid},\fscx122\fscy122)"
        rf"\t({mid},{_WORD_ANIM_MS},\fscx112\fscy112)"
    )
    suffix = r"\fscx100\fscy100"
    return _wrap(prefix, ctx, suffix)


def creator_word_effect(ctx: WordCtx) -> str:
    """Smooth cyan highlight reveal with scale pop (108% -> 104%)."""
    mid = int(140 * 0.5)
    prefix = (
        rf"\fscx100\fscy100\alpha&H60&"
        rf"\t(0,{mid},\fscx108\fscy108\alpha&H00&)"
        rf"\t({mid},140,\fscx104\fscy104)"
    )
    suffix = r"\fscx100\fscy100\alpha&H00&"
    return _wrap(prefix, ctx, suffix)


def cinema_word_effect(ctx: WordCtx) -> str:
    """Opacity-only reveal of the soft highlight color. No scaling."""
    prefix = rf"\alpha&H50&\t(0,120,\alpha&H00&)"
    suffix = r"\alpha&H00&"
    return _wrap(prefix, ctx, suffix)


def focus_word_effect(ctx: WordCtx) -> str:
    """Draw a growing rounded pill behind the active word (Apple-keynote feel).

    Implemented with separate ``\\xbord`` (horizontal padding) and ``\\ybord`` (vertical padding)
    along with ``\\blur`` to soften corners, animating the scale 94% -> 106% -> 100%.
    """
    pill = hex_to_ass_color(ctx.pill_color_hex)
    active = hex_to_ass_color(ctx.highlight_color_hex)
    normal = hex_to_ass_color(ctx.normal_color_hex)
    pill_xbord = max(1, int(24 * SCALE_FACTOR))
    pill_ybord = max(1, int(14 * SCALE_FACTOR))
    mid = int(140 * 0.55)
    prefix = (
        rf"\c&H{active.b:02X}{active.g:02X}{active.r:02X}&"
        rf"\3c&H{pill.b:02X}{pill.g:02X}{pill.r:02X}&\xbord{pill_xbord}\ybord{pill_ybord}\blur3\shad0"
        rf"\fscx94\fscy94"
        rf"\t(0,{mid},\fscx106\fscy106)"
        rf"\t({mid},140,\fscx100\fscy100)"
    )
    suffix = (
        rf"\c&H{normal.b:02X}{normal.g:02X}{normal.r:02X}&"
        rf"\3c&H{ctx.stroke_c.b:02X}{ctx.stroke_c.g:02X}{ctx.stroke_c.r:02X}&"
        rf"\xbord{ctx.stroke_bord}\ybord{ctx.stroke_bord}\blur0\fscx100\fscy100"
    )
    return rf"{{{prefix}}}{ctx.word}{{{suffix}}}"


def neon_word_effect(ctx: WordCtx) -> str:
    """Pulsing pink neon glow with a white text core, vibrant thick border/shadow glow, and scale pop."""
    glow = hex_to_ass_color(ctx.highlight_color_hex)
    mid = int(150 * 0.5)
    
    xbord_init = max(2.0, 4.0 * SCALE_FACTOR)
    ybord_init = max(2.0, 4.0 * SCALE_FACTOR)
    blur_init = int(10 * SCALE_FACTOR)
    
    xbord_mid = max(3.0, 6.0 * SCALE_FACTOR)
    ybord_mid = max(3.0, 6.0 * SCALE_FACTOR)
    blur_mid = int(14 * SCALE_FACTOR)
    
    xbord_settle = max(2.0, 4.5 * SCALE_FACTOR)
    ybord_settle = max(2.0, 4.5 * SCALE_FACTOR)
    blur_settle = int(10 * SCALE_FACTOR)

    prefix = (
        rf"\c&HFFFFFF&"
        rf"\3c&H{glow.b:02X}{glow.g:02X}{glow.r:02X}&"
        rf"\4c&H{glow.b:02X}{glow.g:02X}{glow.r:02X}&"
        rf"\4a&H00&"
        rf"\xbord{xbord_init:.1f}\ybord{ybord_init:.1f}\blur{blur_init}"
        rf"\fscx100\fscy100"
        rf"\t(0,{mid},\xbord{xbord_mid:.1f}\ybord{ybord_mid:.1f}\blur{blur_mid}\fscx112\fscy112)"
        rf"\t({mid},150,\xbord{xbord_settle:.1f}\ybord{ybord_settle:.1f}\blur{blur_settle}\fscx106\fscy106)"
    )
    
    normal_c = hex_to_ass_color(ctx.normal_color_hex)
    suffix = (
        rf"\c&H{normal_c.b:02X}{normal_c.g:02X}{normal_c.r:02X}&"
        rf"\3c&H{ctx.stroke_c.b:02X}{ctx.stroke_c.g:02X}{ctx.stroke_c.r:02X}&"
        rf"\4c&H{ctx.stroke_c.b:02X}{ctx.stroke_c.g:02X}{ctx.stroke_c.r:02X}&"
        rf"\4a&H20&"
        rf"\xbord{ctx.stroke_bord}\ybord{ctx.stroke_bord}\blur3\fscx100\fscy100"
    )
    return rf"{{{prefix}}}{ctx.word}{{{suffix}}}"


def luxury_word_effect(ctx: WordCtx) -> str:
    """Luxury Shimmer & Rise active word effect: sharp metallic gold, tracking expansion, crisp dark border, scale pop (106% -> 102%)."""
    dur = 160
    mid = int(dur * 0.5)
    gold = hex_to_ass_color(ctx.highlight_color_hex)
    
    prefix = (
        rf"\c&H{gold.b:02X}{gold.g:02X}{gold.r:02X}&"
        rf"\3c&H{ctx.stroke_c.b:02X}{ctx.stroke_c.g:02X}{ctx.stroke_c.r:02X}&"
        rf"\blur0\fscx100\fscy100\fsp{ctx.default_fsp:.1f}"
        rf"\t(0,{mid},\fscx106\fscy106\fsp{ctx.default_fsp + 3.0:.1f})"
        rf"\t({mid},{dur},\fscx102\fscy102\fsp{ctx.default_fsp + 1.5:.1f})"
    )
    
    normal_c = hex_to_ass_color(ctx.normal_color_hex)
    suffix = (
        rf"\c&H{normal_c.b:02X}{normal_c.g:02X}{normal_c.r:02X}&"
        rf"\3c&H{ctx.stroke_c.b:02X}{ctx.stroke_c.g:02X}{ctx.stroke_c.r:02X}&"
        rf"\blur0\fscx100\fscy100\fsp{ctx.default_fsp:.1f}"
    )
    return rf"{{{prefix}}}{ctx.word}{{{suffix}}}"


WORD_EFFECTS: dict[str, Callable[[WordCtx], str]] = {
    "impact": impact_word_effect,
    "creator": creator_word_effect,
    "cinema": cinema_word_effect,
    "focus": focus_word_effect,
    "neon": neon_word_effect,
    "luxury": luxury_word_effect,
}

# Presets that anchor to a bottom baseline (all five use bottom-center).
_BOTTOM_ANCHOR = frozenset(ANIMATION_BUILDERS.keys())


# ─────────────────────────────────────────────────────────────────────────────
# Styling / transcript helpers (unchanged public behavior)
# ─────────────────────────────────────────────────────────────────────────────
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

    if overrides["shadow_depth"] is not None:
        shadow = overrides["shadow_depth"]
    if overrides["position_y"] is not None:
        marginv = int((1.0 - overrides["position_y"]) * V_HEIGHT)

    style = pysubs2.SSAStyle()
    style.fontname = resolve_font_name(fontname)
    style.fontsize = int(fontsize * SCALE_FACTOR)
    style.bold = bool(base.get("bold", True))
    style.italic = overrides.get("italic") or False
    style.primarycolor = primarycolor
    style.outlinecolor = outlinecolor
    style.outline = outline * SCALE_FACTOR
    style.shadow = shadow * SCALE_FACTOR
    style.backcolor = backcolor
    style.borderstyle = base.get("borderstyle", 1)
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
    if preset not in _BOTTOM_ANCHOR:
        return None
    if position_y is not None:
        raw = int(position_y * V_HEIGHT)
        return int(raw + fs / 2.0)
    margin = 150 if preset == "impact" else 130
    return V_HEIGHT - int(margin * SCALE_FACTOR)


# ─────────────────────────────────────────────────────────────────────────────
# Event emission
# ─────────────────────────────────────────────────────────────────────────────
def build_animation(
    preset: str, fs: int, shadow_tag: str, *, animate: bool, y: int | None = None, word_idx: int = 0
) -> str:
    """Build the sentence-level tag block: position, shadow, entrance, fontsize."""
    tags: list[str] = []
    if y is not None:
        if preset == "creator":
            tags.append(rf"\pos({CX},{y})\t(0,120,\pos({CX},{y-12}))")
        else:
            tags.append(rf"\pos({CX},{y})")
    tags.append(shadow_tag)
    if animate:
        builder = ANIMATION_BUILDERS.get(preset, ANIMATION_BUILDERS[DEFAULT_PRESET])
        entrance = builder(fs)
        if entrance:
            tags.append(entrance)
    tags.append(rf"\fs{fs}")
    return "{" + "".join(tags) + "}"


def build_word_line(
    phrase_group: list[dict],
    active_idx: int,
    preset: str,
    ctx_base: WordCtx,
) -> str:
    """Render a phrase line where ``active_idx`` is styled via the preset's
    active-word effect and every other word uses the inactive style."""
    effect = WORD_EFFECTS.get(preset, WORD_EFFECTS[DEFAULT_PRESET])
    parts: list[str] = []
    for w_idx, w in enumerate(phrase_group):
        if w_idx != active_idx:
            parts.append(w["word"])
            continue
        ctx = WordCtx(
            word=w["word"],
            fs=ctx_base.fs,
            highlight_tag=ctx_base.highlight_tag,
            normal_tag=ctx_base.normal_tag,
            highlight_color_hex=ctx_base.highlight_color_hex,
            normal_color_hex=ctx_base.normal_color_hex,
            stroke_c=ctx_base.stroke_c,
            stroke_bord=ctx_base.stroke_bord,
            pill_color_hex=ctx_base.pill_color_hex,
            default_fsp=ctx_base.default_fsp,
        )
        parts.append(effect(ctx))
    extra_space = max(1, int(ctx_base.fs * 0.04))
    sep = f"{{\\fsp{ctx_base.default_fsp + extra_space}}} {{\\fsp{ctx_base.default_fsp}}}"
    return sep.join(parts)


def _chunk_into_phrases(
    words: list[dict], max_words: int = 3, max_chars: int = 28
) -> list[list[dict]]:
    """Group words into natural semantic phrases or short clauses respecting
    both word caps and character ceilings.

    Respects:
      1. Hard caps of max_words (bounded 2-4) and max_chars (bounded 18-28).
      2. Natural semantic breaks on punctuation ('.', ',', '!', '?', ';', ':', '—', '-').
      3. Minimum phrase speech duration target so phrases aren't micro-fragmented.
      4. Speaker / layout boundaries.
    """
    max_words = max(2, min(4, max_words))
    groups: list[list[dict]] = []
    current_group: list[dict] = []

    for w in words:
        word_text = (w.get("word") or "").strip()

        # Check boundary condition with existing group (layout or speaker mismatch)
        if current_group:
            same_layout = w.get("layout") == current_group[0].get("layout")
            same_speaker = w.get("speaker") == current_group[0].get("speaker")
            if not (same_layout and same_speaker):
                groups.append(current_group)
                current_group = []

        # Predict candidate character length
        cand_words = current_group + [w]
        cand_char_len = sum(len((x.get("word") or "").strip()) for x in cand_words) + (len(cand_words) - 1)

        # Hard ceiling check
        if current_group and (len(cand_words) > max_words or cand_char_len > max_chars):
            groups.append(current_group)
            current_group = [w]
            continue

        current_group.append(w)

        # Check punctuation on the current word
        has_clause_punct = any(word_text.endswith(p) for p in (",", ";", ":", "—", "-"))
        has_sentence_punct = any(word_text.endswith(p) for p in (".", "!", "?"))
        
        group_dur = current_group[-1]["end"] - current_group[0]["start"]

        if len(current_group) >= max_words:
            groups.append(current_group)
            current_group = []
        elif has_sentence_punct and len(current_group) >= 1:
            groups.append(current_group)
            current_group = []
        elif has_clause_punct and len(current_group) >= 2 and group_dur >= 0.5:
            groups.append(current_group)
            current_group = []

    if current_group:
        # Merge trailing single word if previous group has capacity
        if len(current_group) == 1 and groups and len(groups[-1]) < max_words:
            prev_layout = groups[-1][0].get("layout")
            prev_speaker = groups[-1][0].get("speaker")
            curr_layout = current_group[0].get("layout")
            curr_speaker = current_group[0].get("speaker")
            prev_char_len = sum(len((x.get("word") or "").strip()) for x in groups[-1]) + len(groups[-1]) + len(word_text)
            if prev_layout == curr_layout and prev_speaker == curr_speaker and prev_char_len <= max_chars:
                groups[-1].append(current_group[0])
                current_group = []
        if current_group:
            groups.append(current_group)

    return groups


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
    pill_color_hex: Optional[str] = None,
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
        pos_y = 0.68

    y = _resolve_y_anchor(preset, pos_y, fs)

    wh_val = template.get("word_highlight")
    if wh_val is None:
        wh_val = template.get("word_level_highlight")
    if wh_val is None:
        word_highlight = base.get("word_highlight_default", True)
    else:
        word_highlight = bool(wh_val)

    if not word_highlight:
        # Emit a single, clean subtitle block for the phrase group
        phrase_text = " ".join(w["word"] for w in phrase_group)
        prefix = build_animation(
            preset,
            fs,
            shadow_tag,
            animate=True,
            y=y,
            word_idx=0,
        )
        add(p_start, p_end, prefix + phrase_text)
        return

    normal_color = template.get("font_color") or base["primary"]
    stroke_c = hex_to_ass_color(
        base["outlinecolor"]
        if overrides["stroke_color"] in (None, "transparent")
        else overrides["stroke_color"]
    )
    stroke_bord = (
        max(0, int(float(base["outline"]) * SCALE_FACTOR))
        if overrides["stroke_width"] in (None, 0)
        else int(float(overrides["stroke_width"]) * SCALE_FACTOR)
    )

    ctx_base = WordCtx(
        word="",
        fs=fs,
        highlight_tag=ass_color_override(h_color_hex),
        normal_tag=ass_color_override(normal_color),
        highlight_color_hex=h_color_hex,
        normal_color_hex=normal_color,
        stroke_c=stroke_c,
        stroke_bord=stroke_bord,
        pill_color_hex=pill_color_hex or base.get("pillcolor", "#FFE500"),
        default_fsp=float(template.get("letter_spacing", 0.0) or 0.0),
    )

    MIN_WORD_DURATION_S = 0.05  # Minimum 50ms highlight step to stay tight with fast speech without artificial lag
    MAX_WORD_HIGHLIGHT_S = 0.45  # Maximum 450ms active highlight per word to prevent silence bleed during pauses

    for idx in range(len(phrase_group)):
        word = phrase_group[idx]
        start = word["start"]
        raw_word_end = word.get("end", start + 0.3)

        if idx < len(phrase_group) - 1:
            next_start = phrase_group[idx + 1]["start"]
            # Active word highlight ends when next word begins or after MAX_WORD_HIGHLIGHT_S
            end = min(next_start, max(start + MIN_WORD_DURATION_S, min(raw_word_end, start + MAX_WORD_HIGHLIGHT_S)))
            if end <= start:
                end = min(next_start, start + 0.1)
        else:
            end = min(p_end, max(start + MIN_WORD_DURATION_S, min(raw_word_end, start + MAX_WORD_HIGHLIGHT_S)))

        if end <= start:
            end = start + 0.1

        line = build_word_line(phrase_group, idx, preset, ctx_base)
        prefix = build_animation(
            preset,
            fs,
            shadow_tag,
            animate=(idx == 0),
            y=y,
            word_idx=idx,
        )
        add(start, end, prefix + line)


def _select_shadow_tag(preset: str, no_shadow: bool) -> str:
    if no_shadow:
        return _NO_SHADOW_TAG
    if preset == "neon":
        return _NEON_SHADOW_TAG
    if preset == "cinema":
        return r"\xshad1.5\yshad1.5\blur5\4a&H30&"
    return _SHADOW_TAG


def generate_ass(
    transcript, styling, output_path: str, crop_mode: str = "reframe"
) -> None:
    """Generate an ASS subtitle file from ``transcript`` + ``styling``."""
    import pysubs2

    template = _styling_to_dict(styling)
    user_pos_y = _tpl(template, "position_y", "positionY")
    if user_pos_y is None:
        if crop_mode in ("split", "course"):
            template["position_y"] = 0.50
        elif crop_mode == "letterbox":
            template["position_y"] = 0.66
        elif crop_mode in ("reframe", "single", "auto"):
            template["position_y"] = 0.68

    if crop_mode == "letterbox":
        for snake, camel in (
            ("font_size", "fontSize"),
            ("stroke_width", "strokeWidth"),
            ("shadow_depth", "shadowDepth"),
        ):
            val = _tpl(template, snake, camel)
            if val is not None:
                template[snake] = template[camel] = float(val)

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
    subs.styles["Default"] = _build_style(base, overrides, template)

    raw_items = _flatten_transcript(transcript)
    do_upper = template.get("uppercase") or preset in ALWAYS_UPPERCASE

    sound_event_re = re.compile(r"\[.*?\]|\(.*?\)")
    words = []
    for item in raw_items:
        raw_word = item.get("punctuated_word") or item.get("word", "")
        cleaned_word = sound_event_re.sub("", raw_word)
        cleaned_word = re.sub(r"\s+", " ", cleaned_word).strip()
        if not cleaned_word:
            continue
        word_text = cleaned_word.upper() if do_upper else cleaned_word
        words.append(
            {
                "word": word_text,
                "start": item.get("start", 0.0),
                "end": item.get("end", 0.0),
                "speaker": item.get("speaker", "speaker_1") or "speaker_1",
                "layout": item.get("layout"),
            }
        )

    if not words:
        subs.save(output_path)
        logger.info("Saved empty ASS to %s", output_path)
        return

    # Auto-normalize timestamps if absolute video timeline timestamps (> 10s start offset) are passed
    first_start = words[0]["start"]
    if first_start > 10.0:
        logger.info("Normalizing transcript word timestamps from absolute start %.2fs -> 0.0s", first_start)
        for w in words:
            w["start"] = max(0.0, w["start"] - first_start)
            w["end"] = max(0.0, w["end"] - first_start)

    words_per_phrase = template.get("max_words") or base.get("preferred_words") or 3
    words_per_phrase = max(2, min(4, int(words_per_phrase)))
    max_chars = template.get("max_chars") or base.get("max_chars_per_line") or 28

    # Highlight color: user override wins, otherwise the preset's own base color.
    h_color_hex = template.get("highlight_color") or base["highlightcolor"]
    no_shadow = overrides.get("shadow") is False or overrides.get("shadow_depth") == 0.0

    groups = _chunk_into_phrases(words, max_words=words_per_phrase, max_chars=int(max_chars))

    MIN_GROUP_DURATION_S = float(template.get("min_group_duration", 0.8))

    multi_speaker_val = template.get("multi_speaker_colors")
    if multi_speaker_val is None:
        multi_speaker_val = template.get("speaker_colors")
    enable_multi_speaker = bool(multi_speaker_val)

    unique_speakers = list(dict.fromkeys(w.get("speaker", "speaker_1") for w in words))
    multi_speaker = enable_multi_speaker and len(unique_speakers) > 1

    for g_idx, group in enumerate(groups):
        if not group:
            continue

        spk = group[0].get("speaker", "speaker_1")
        if multi_speaker and spk in unique_speakers:
            spk_idx = unique_speakers.index(spk)
            group_h_color = SPEAKER_HIGHLIGHT_PALETTES.get(preset, SPEAKER_HIGHLIGHT_PALETTES["impact"])[spk_idx % 4]
            group_pill_color = (
                SPEAKER_PILL_PALETTES.get(preset, [base.get("pillcolor")])[spk_idx % 4]
                if base.get("pillcolor")
                else base.get("pillcolor")
            )
        else:
            group_h_color = h_color_hex
            group_pill_color = base.get("pillcolor")

        p_start = group[0]["start"]
        p_end_raw = group[-1]["end"]

        # Calculate next group start if available
        next_group_start = (
            groups[g_idx + 1][0]["start"]
            if (g_idx + 1 < len(groups) and groups[g_idx + 1])
            else None
        )

        # Enforce minimum display duration threshold per subtitle block (at least 0.8s)
        target_end = p_start + MIN_GROUP_DURATION_S
        if next_group_start is not None and next_group_start > p_start:
            p_end = max(p_end_raw, min(target_end, next_group_start))
        else:
            p_end = max(p_end_raw, target_end)

        if p_end <= p_start:
            continue

        fs = _safe_event_fontsize(group, subs.styles["Default"].fontsize)
        s_tag = _select_shadow_tag(preset, no_shadow)

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
            group_h_color,
            s_tag,
            crop_mode,
            pill_color_hex=group_pill_color,
        )

    subs.save(output_path)
    logger.info("Saved ASS to %s with %d events", output_path, len(subs.events))


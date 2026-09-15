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
from typing import Callable, Iterable, Optional

import pysubs2

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
    "hormozi": ["#FFE600", "#00FF66", "#FF1E56", "#00F0FF"],
    "growth": ["#00FF66", "#FFE600", "#00F0FF", "#FF1E56"],
    "coral": ["#FF1E56", "#FFE600", "#00FF66", "#00F0FF"],
    "sticker": ["#FFE600", "#00FF66", "#FF1E56", "#00F0FF"],
    "minimal": ["#FFFFFF", "#00F0FF", "#FFE600", "#38BDF8"],
    "creator": ["#00F0FF", "#FFE500", "#FF007A", "#A855F7"],
    "cinema": ["#FFB800", "#00F0FF", "#F43F5E", "#38BDF8"],
    "focus": ["#0A0A0A", "#0A0A0A", "#0A0A0A", "#0A0A0A"],
    "badge": ["#0A0A0A", "#1E3A8A", "#831843", "#064E3B"],
    "neon": ["#FF007A", "#00F0FF", "#FFE500", "#A855F7"],
    "luxury": ["#FFD700", "#00F0FF", "#F43F5E", "#38BDF8"],
    "podcast": ["#38BDF8", "#FBBF24", "#34D399", "#F472B6"],
    "bobby": ["#fcbb42", "#00FF66", "#FF1E56", "#00F0FF"],

    "tom": ["#FFFFFF", "#FFFFFF", "#FFFFFF", "#FFFFFF"],
    "casey": ["#FFFFFF", "#FFFFFF", "#FFFFFF", "#FFFFFF"],
    "fred": ["#28ae67", "#FFE600", "#FF1E56", "#00F0FF"],
    "sara": ["#FFFFFF", "#FFFFFF", "#FFFFFF", "#FFFFFF"],
    "billy": ["#FFFFFF", "#FFFFFF", "#FFFFFF", "#FFFFFF"],
    "unbox": ["#FFFFFF", "#FFFFFF", "#FFFFFF", "#FFFFFF"],
    "aliabdlal": ["#f06c3f", "#3B82F6", "#10B981", "#8B5CF6"],
}

SPEAKER_PILL_PALETTES: dict[str, list[str]] = {
    "focus": ["#FFE600", "#00F0FF", "#FF007A", "#34D399"],
    "badge": ["#FFFFFF", "#F3F4F6", "#EFF6FF", "#FDF2F8"],
    "tom": ["#DC2626", "#2563EB", "#7C3AED", "#059669"],
    "sara": ["#FF5722", "#0284C7", "#7C3AED", "#10B981"],
    "unbox": ["#D946EF", "#06B6D4", "#F59E0B", "#10B981"],
}

# ── Canvas geometry ──────────────────────────────────────────────────────────
V_WIDTH, V_HEIGHT = 1080, 1920
SCALE_FACTOR = V_HEIGHT / 1920.0
CX, CY = V_WIDTH // 2, V_HEIGHT // 2
_MAX_SAFE_WIDTH = 840.0

# ── Shadow tags (Studio diffused ambient shadows) ───────────────────────────
_SHADOW_TAG = r"\xshad0\yshad3.5\blur6\4a&H35&"
_NO_SHADOW_TAG = r"\xshad0\yshad0\blur0"
_NEON_SHADOW_TAG = r"\xshad0\yshad0\blur4\4a&H00&"

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


# ── Sentence entrance animations (all static & stable for zero flicker) ──────
def stable_animation(fs: int, duration: int = 0) -> str:
    """Zero jitter / zero squash / zero alpha fade — text is immediately solid & crisp."""
    return ""


ANIMATION_BUILDERS: dict[str, Callable[..., str]] = {
    "impact": stable_animation,
    "hormozi": stable_animation,
    "growth": stable_animation,
    "coral": stable_animation,
    "sticker": stable_animation,
    "minimal": stable_animation,
    "creator": stable_animation,
    "cinema": stable_animation,
    "focus": stable_animation,
    "badge": stable_animation,
    "neon": stable_animation,
    "luxury": stable_animation,
    "podcast": stable_animation,
    # Klap presets
    "bobby": stable_animation,
    "tom": stable_animation,
    "casey": stable_animation,
    "fred": stable_animation,
    "sara": stable_animation,
    "billy": stable_animation,
    "unbox": stable_animation,
    "aliabdlal": stable_animation,
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
    """Snappy micro-pop for high-energy short-form video hooks."""
    return (
        rf"{{\fscx92\fscy92\t(0,65,\fscx112\fscy112)\t(65,130,\fscx100\fscy100){ctx.highlight_tag}}}"
        rf"{ctx.word}"
        rf"{{\fscx100\fscy100{ctx.normal_tag}}}"
    )


def clean_impact_word_effect(ctx: WordCtx) -> str:
    """Clean canary-yellow active word emphasis without bounce or jitter."""
    return rf"{{{ctx.highlight_tag}}}{ctx.word}{{{ctx.normal_tag}}}"


def creator_word_effect(ctx: WordCtx) -> str:
    """Smooth cyan highlight reveal with zero jitter and clean locked baseline."""
    return rf"{{{ctx.highlight_tag}}}{ctx.word}{{{ctx.normal_tag}}}"


def cinema_word_effect(ctx: WordCtx) -> str:
    """Clean reveal of the soft highlight color with zero flashing."""
    return rf"{{{ctx.highlight_tag}}}{ctx.word}{{{ctx.normal_tag}}}"


def focus_word_effect(ctx: WordCtx) -> str:
    """High-contrast Keynote active word highlight with clean contrast and zero horizontal displacement."""
    return rf"{{{ctx.highlight_tag}}}{ctx.word}{{{ctx.normal_tag}}}"


def neon_word_effect(ctx: WordCtx) -> str:
    """Synthwave dual-tone neon: active word surges with white core and intense hot-magenta bloom."""
    glow = hex_to_ass_color(ctx.highlight_color_hex)
    normal_c = hex_to_ass_color(ctx.normal_color_hex)
    prefix = (
        rf"\c&HFFFFFF&"
        rf"\3c&H{glow.b:02X}{glow.g:02X}{glow.r:02X}&"
        rf"\4c&H{glow.b:02X}{glow.g:02X}{glow.r:02X}&"
        rf"\bord6\xshad0\yshad0\fscx114\fscy114\blur16\t(0,120,\fscx106\fscy106\blur10)"
    )
    suffix = (
        rf"\c&H{normal_c.b:02X}{normal_c.g:02X}{normal_c.r:02X}&"
        rf"\3c&H{ctx.stroke_c.b:02X}{ctx.stroke_c.g:02X}{ctx.stroke_c.r:02X}&"
        rf"\4c&H{normal_c.b:02X}{normal_c.g:02X}{normal_c.r:02X}&"
        rf"\bord3\xshad0\yshad0\blur4\fscx100\fscy100"
    )
    return rf"{{{prefix}}}{ctx.word}{{{suffix}}}"


def depth_tilt_word_effect(ctx: WordCtx) -> str:
    """3D depth tilt along X-axis complementing 3D extrusion text."""
    return (
        rf"{{\frx55\fscy40\t(0,130,\frx0\fscy100){ctx.highlight_tag}}}"
        rf"{ctx.word}"
        rf"{{\frx0\fscy100{ctx.normal_tag}}}"
    )


def luxury_word_effect(ctx: WordCtx) -> str:
    """Luxury metallic gold highlight with zero jitter."""
    gold = hex_to_ass_color(ctx.highlight_color_hex)
    prefix = rf"\c&H{gold.b:02X}{gold.g:02X}{gold.r:02X}&"
    normal_c = hex_to_ass_color(ctx.normal_color_hex)
    suffix = rf"\c&H{normal_c.b:02X}{normal_c.g:02X}{normal_c.r:02X}&"
    return rf"{{{prefix}}}{ctx.word}{{{suffix}}}"


def badge_word_effect(ctx: WordCtx) -> str:
    """Clean badge active word: high-contrast bold white against dimmed muted gray inactive words."""
    active = hex_to_ass_color(ctx.highlight_color_hex)
    normal = hex_to_ass_color(ctx.normal_color_hex)
    prefix = rf"\c&H{active.b:02X}{active.g:02X}{active.r:02X}&"
    suffix = rf"\c&H{normal.b:02X}{normal.g:02X}{normal.r:02X}&"
    return rf"{{{prefix}}}{ctx.word}{{{suffix}}}"


def podcast_word_effect(ctx: WordCtx) -> str:
    """Conversational podcast word highlight with clean highlight transition and zero horizontal jitter."""
    return rf"{{{ctx.highlight_tag}}}{ctx.word}{{{ctx.normal_tag}}}"


def aliabdlal_word_effect(ctx: WordCtx) -> str:
    """Ali Abdaal signature: Highlighter sweep (Dynamic Karaoke Wipe)."""
    return rf"{{\kf{max(1, int(len(ctx.word) * 8))}}}{ctx.word}"


WORD_EFFECTS: dict[str, Callable[[WordCtx], str]] = {
    "impact": clean_impact_word_effect,
    "hormozi": impact_word_effect,
    "growth": impact_word_effect,
    "coral": impact_word_effect,
    "sticker": impact_word_effect,
    "minimal": badge_word_effect,
    "creator": creator_word_effect,
    "cinema": cinema_word_effect,
    "focus": focus_word_effect,
    "badge": badge_word_effect,
    "neon": neon_word_effect,
    "luxury": luxury_word_effect,
    "podcast": podcast_word_effect,
    # Klap presets
    "bobby": impact_word_effect,
    "tom": impact_word_effect,
    "casey": depth_tilt_word_effect,
    "fred": impact_word_effect,
    "sara": focus_word_effect,
    "billy": cinema_word_effect,
    "unbox": depth_tilt_word_effect,
    "aliabdlal": aliabdlal_word_effect,
}

# Presets that anchor to a bottom baseline (all use bottom-center).
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
        if isinstance(nested, list):
            block_layout = item_dict.get("layout")
            for w in nested:
                if isinstance(w, dict):
                    w_copy = dict(w)
                    if block_layout and not w_copy.get("layout"):
                        w_copy["layout"] = block_layout
                    raw_items.append(w_copy)
                else:
                    raw_items.append(w)
        else:
            raw_items.append(item_dict)
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


def _build_style(base: dict, overrides: dict, template: dict, preset: str = ""):
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
    style.italic = overrides.get("italic") if overrides.get("italic") is not None else bool(base.get("italic", False))
    style.primarycolor = primarycolor
    style.outlinecolor = hex_to_ass_color(base["outlinecolor"]) if base.get("borderstyle") == 3 else outlinecolor
    style.outline = 0.0 if base.get("borderstyle") == 3 else (outline * SCALE_FACTOR)
    style.shadow = 0.0 if base.get("borderstyle") == 3 else (shadow * SCALE_FACTOR)
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
    if preset == "aliabdlal":
        # In ASS karaoke: SecondaryColour is unsung base color, PrimaryColour is sung highlight color
        h_color = (
            overrides.get("highlight_color")
            or template.get("highlight_color")
            or template.get("highlightcolor")
            or base.get("highlightcolor", "#f06c3f")
        )
        style.primarycolor = hex_to_ass_color(h_color)
        style.secondarycolor = primarycolor
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
    preset: str, fs: int, shadow_tag: str, *, animate: bool = False, y: int | None = None, word_idx: int = 0
) -> str:
    """Build the sentence-level tag block: position, shadow, fontsize."""
    tags: list[str] = []
    if y is not None:
        tags.append(rf"\pos({CX},{y})")
    if preset == "impact":
        tags.append(r"\frz-3.5")
    tags.append(shadow_tag)
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
    if preset in ("badge", "hormozi"):
        default_active = "#FFB800" if preset == "hormozi" else "#111111"
        default_normal = "#FFFFFF" if preset == "hormozi" else "#A0A0A8"
        active_col = hex_to_ass_color(ctx_base.highlight_color_hex or default_active)
        normal_col = hex_to_ass_color(ctx_base.normal_color_hex or default_normal)
        active_tag = rf"\c&H{active_col.b:02X}{active_col.g:02X}{active_col.r:02X}&"
        normal_tag = rf"\c&H{normal_col.b:02X}{normal_col.g:02X}{normal_col.r:02X}&"
        spoken = " ".join(phrase_group[i]["word"] for i in range(active_idx + 1))
        upcoming = " ".join(phrase_group[i]["word"] for i in range(active_idx + 1, len(phrase_group)))
        if upcoming:
            return rf"{{{active_tag}}}{spoken} {{{normal_tag}}}{upcoming}"
        return rf"{{{active_tag}}}{spoken}"

    has_pill = bool(ctx_base.pill_color_hex and preset in ("unbox", "sara", "focus"))
    has_highlight = has_pill or bool(
        ctx_base.highlight_color_hex
        and ctx_base.normal_color_hex
        and ctx_base.highlight_color_hex.upper() != ctx_base.normal_color_hex.upper()
    )
    if not has_highlight:
        return " ".join(w["word"] for w in phrase_group)

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
    res = " ".join(parts)
    if active_idx > 0 and ctx_base.normal_tag:
        res = f"{{{ctx_base.normal_tag}}}{res}"
    return res


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
    max_words = max(2, min(5, max_words))
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


# ── Dynamic Layout Caption Positioning Map ────────────────────────────────────
# Standardizes graceful subtitle vertical anchors across all video layout formats:
# - split / panel: Centered on the horizontal divider band (y = 0.50)
# - screencast / presentation: Below the code editor / slide deck (y = 0.84)
# - gaming: Below central gameplay card, avoiding crosshairs & streamer PiP (y = 0.84)
# - letterbox: Clean lower blurred region (y = 0.72)
# - reframe / single / passthrough: Standard lower-third safe zone (y = 0.72)
LAYOUT_DEFAULT_POS_Y: dict[str, float] = {
    "split": 0.50,
    "panel": 0.50,
    "screencast": 0.46,
    "presentation": 0.46,
    "course": 0.46,
    "tutorial": 0.46,
    "gaming": 0.84,
    "game": 0.84,
    "action": 0.84,
    "letterbox": 0.76,
    "reframe": 0.65,
    "single": 0.65,
    "auto": 0.65,
    "passthrough": 0.65,
    "vertical_native": 0.65,
}



def resolve_layout_pos_y(layout_mode: str | None, user_override: float | None = None) -> float:
    """Resolve graceful caption Y-anchor position (0.0 - 1.0) based on layout type."""
    if user_override is not None:
        return max(0.10, min(float(user_override), 0.92))
    mode = (layout_mode or "reframe").lower().strip()
    return LAYOUT_DEFAULT_POS_Y.get(mode, 0.65)


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

    is_3d = bool(base.get("extrusion_3d") or template.get("extrusion_3d"))
    stroke_c = hex_to_ass_color(
        base["outlinecolor"]
        if overrides["stroke_color"] in (None, "transparent")
        else overrides["stroke_color"]
    )
    depth_fill_tag = rf"\c&H{stroke_c.b:02X}{stroke_c.g:02X}{stroke_c.r:02X}&"

    def add(start: float, end: float, text: str) -> None:
        if is_3d:
            pos_match = re.search(r"\\pos\((\d+),(\d+)\)", text)
            if pos_match:
                px, py = int(pos_match.group(1)), int(pos_match.group(2))
                clean_text_for_depth = re.sub(r"\\c&H[0-9A-Fa-f]+&", lambda m: depth_fill_tag, text)
                clean_text_for_depth = re.sub(
                    r"\\xshad\d+(\.\d+)?\\yshad\d+(\.\d+)?\\blur\d+(\.\d+)?",
                    lambda m: r"\xshad0\yshad0\blur0",
                    clean_text_for_depth,
                )
                for offset_y in [8, 6, 4, 2]:
                    layer_text = clean_text_for_depth.replace(f"\\pos({px},{py})", f"\\pos({px},{py + offset_y})")
                    subs.events.append(
                        pysubs2.SSAEvent(
                            start=pysubs2.make_time(s=start),
                            end=pysubs2.make_time(s=end),
                            text=layer_text,
                            style="Default",
                            layer=0,
                        )
                    )
            top_text = re.sub(
                r"\\xshad\d+(\.\d+)?\\yshad\d+(\.\d+)?\\blur\d+(\.\d+)?",
                lambda m: r"\xshad0\yshad0\blur0",
                text,
            )
            subs.events.append(
                pysubs2.SSAEvent(
                    start=pysubs2.make_time(s=start),
                    end=pysubs2.make_time(s=end),
                    text=top_text,
                    style="Default",
                    layer=1,
                )
            )
        else:
            subs.events.append(
                pysubs2.SSAEvent(
                    start=pysubs2.make_time(s=start),
                    end=pysubs2.make_time(s=end),
                    text=text,
                    style="Default",
                    layer=0,
                )
            )

    phrase_layout = global_crop_mode
    layouts_in_group = [w.get("layout") for w in phrase_group if w.get("layout")]
    if layouts_in_group:
        phrase_layout = layouts_in_group[0]

    user_pos_y = overrides.get("position_y")
    if user_pos_y is None and preset == "billy":
        pos_y = 0.18
    else:
        pos_y = resolve_layout_pos_y(phrase_layout, user_pos_y)
    y = _resolve_y_anchor(preset, pos_y, fs)

    normal_color = template.get("font_color") or base["primary"]
    has_pill = bool(base.get("pillcolor") or pill_color_hex)
    has_highlight = has_pill or bool(
        h_color_hex
        and normal_color
        and h_color_hex.upper() != normal_color.upper()
    )

    wh_val = template.get("word_highlight")
    if wh_val is None:
        wh_val = template.get("word_level_highlight")
    if wh_val is None:
        word_highlight = base.get("word_highlight_default", True)
    else:
        word_highlight = bool(wh_val)

    if not word_highlight or not has_highlight:
        # Emit a single, clean subtitle block for the phrase group (no word-level flicker or scaling)
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

    if preset == "aliabdlal":
        # Highlighter sweep (Dynamic Karaoke Wipe): single continuous phrase event with \kf sweeps
        karaoke_parts: list[str] = []
        for idx, w in enumerate(phrase_group):
            if idx == 0 and w["start"] > p_start:
                lead_cs = max(0, int((w["start"] - p_start) * 100))
                if lead_cs > 0:
                    karaoke_parts.append(rf"{{\k{lead_cs}}}")

            w_end = w["end"]
            if idx < len(phrase_group) - 1:
                next_start = phrase_group[idx + 1]["start"]
                if next_start > w["start"]:
                    w_end = min(w_end, next_start)

            dur_cs = max(1, int((w_end - w["start"]) * 100))
            karaoke_parts.append(rf"{{\kf{dur_cs}}}{w['word']}")

            if idx < len(phrase_group) - 1:
                next_start = phrase_group[idx + 1]["start"]
                gap_cs = int((next_start - w_end) * 100)
                if gap_cs > 0:
                    karaoke_parts.append(rf"{{\k{gap_cs}}} ")
                else:
                    karaoke_parts.append(" ")

        k_line = "".join(karaoke_parts)
        h_col = hex_to_ass_color(h_color_hex)
        norm_col = hex_to_ass_color(normal_color)
        color_tags = rf"\1c&H{h_col.b:02X}{h_col.g:02X}{h_col.r:02X}&\2c&H{norm_col.b:02X}{norm_col.g:02X}{norm_col.r:02X}&"
        prefix = build_animation(
            preset,
            fs,
            shadow_tag,
            animate=True,
            y=y,
            word_idx=0,
        )
        if prefix.endswith("}"):
            prefix = prefix[:-1] + color_tags + "}"
        else:
            prefix = prefix + "{" + color_tags + "}"
        add(p_start, p_end, prefix + k_line)
        return
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

    if preset == "badge":
        pill_c = hex_to_ass_color(pill_color_hex or base.get("pillcolor", "#FFFFFF"))
        pill_bgr = f"{pill_c.b:02X}{pill_c.g:02X}{pill_c.r:02X}"
        phrase_plain = " ".join(w["word"] for w in phrase_group)
        xbord = max(1, int(30 * SCALE_FACTOR))
        ybord = max(1, int(14 * SCALE_FACTOR))

        # Layer 0: Background box for the whole phrase (like unbox, but for the entire phrase with roundedness and no shadow)
        subs.events.append(
            pysubs2.SSAEvent(
                start=pysubs2.make_time(s=p_start),
                end=pysubs2.make_time(s=p_end),
                text=rf"{{\pos({CX},{y})\an2\blur2\1a&HFF&\3a&H00&\3c&H{pill_bgr}&\xbord{xbord}\ybord{ybord}\shad0}}{phrase_plain}",
                style="BoxStyle",
                layer=0,
            )
        )

        # Layer 1: Top crisp text with cumulative progressive highlight (no shadow)
        for idx in range(len(phrase_group)):
            word = phrase_group[idx]
            start = p_start if idx == 0 else word["start"]
            if idx < len(phrase_group) - 1:
                end = phrase_group[idx + 1]["start"]
            else:
                end = p_end

            if end <= start:
                end = start + 0.05

            line = build_word_line(phrase_group, idx, preset, ctx_base)
            subs.events.append(
                pysubs2.SSAEvent(
                    start=pysubs2.make_time(s=start),
                    end=pysubs2.make_time(s=end),
                    text=rf"{{\pos({CX},{y})\an2\blur0\shad0}}{line}",
                    style="Default",
                    layer=1,
                )
            )
        return

    if preset in ("unbox", "sara"):
        pill_default = "#e13a06" if preset == "sara" else "#e004fe"
        pill_c = hex_to_ass_color(pill_color_hex or base.get("pillcolor", pill_default))
        pill_bgr = f"{pill_c.b:02X}{pill_c.g:02X}{pill_c.r:02X}"
        phrase_plain = " ".join(w["word"] for w in phrase_group)
        pill_pad = (base.get("animation_metadata") or {}).get("pill_padding", {})
        pad_x = pill_pad.get("x", 20)
        pad_y = pill_pad.get("y", 10)
        xbord = max(1, int(pad_x * SCALE_FACTOR))
        ybord = max(1, int(pad_y * SCALE_FACTOR))

        for idx in range(len(phrase_group)):
            word = phrase_group[idx]
            start = p_start if idx == 0 else word["start"]
            if idx < len(phrase_group) - 1:
                end = phrase_group[idx + 1]["start"]
            else:
                end = p_end

            if end <= start:
                end = start + 0.05

            # Build box layers (inactive words alpha=FF, active word alpha=00)
            box_words = []
            for w_idx, w in enumerate(phrase_group):
                word_text = w["word"]
                if w_idx == idx:
                    box_words.append(rf"{{\alpha&H00&}}{word_text}{{\alpha&HFF&}}")
                else:
                    box_words.append(rf"{{\alpha&HFF&}}{word_text}")
            box_line = " ".join(box_words)

            # Layer 0: Box shadow (3D drop for the pill matching 3D text extrusion)
            subs.events.append(
                pysubs2.SSAEvent(
                    start=pysubs2.make_time(s=start),
                    end=pysubs2.make_time(s=end),
                    text=rf"{{\pos({CX},{y+5})\an2\blur1\alpha&HFF&\3c&H000000&\c&H000000&\xbord{xbord}\ybord{ybord}}}{box_line}",
                    style="BoxStyle",
                    layer=0,
                )
            )
            # Layer 1: Box fill with pill color
            subs.events.append(
                pysubs2.SSAEvent(
                    start=pysubs2.make_time(s=start),
                    end=pysubs2.make_time(s=end),
                    text=rf"{{\pos({CX},{y})\an2\blur1\alpha&HFF&\3c&H{pill_bgr}&\c&H{pill_bgr}&\xbord{xbord}\ybord{ybord}}}{box_line}",
                    style="BoxStyle",
                    layer=1,
                )
            )

        # Layer 2: 3D text extrusion (offsets 8, 6, 4, 2) continuous for whole phrase (zero blink)
        for dy in [8, 6, 4, 2]:
            subs.events.append(
                pysubs2.SSAEvent(
                    start=pysubs2.make_time(s=p_start),
                    end=pysubs2.make_time(s=p_end),
                    text=rf"{{\pos({CX},{y+dy})\an2\xshad0\yshad0\blur0\c&H000000&\3c&H000000&\bord{stroke_bord}}}{phrase_plain}",
                    style="Default",
                    layer=2,
                )
            )
        # Layer 3: Top text layer continuous for whole phrase (zero blink)
        subs.events.append(
            pysubs2.SSAEvent(
                start=pysubs2.make_time(s=p_start),
                end=pysubs2.make_time(s=p_end),
                text=rf"{{\pos({CX},{y})\an2\xshad0\yshad0\blur0\c&HFFFFFF&\3c&H000000&\bord{stroke_bord}}}{phrase_plain}",
                style="Default",
                layer=3,
            )
        )
        return

    for idx in range(len(phrase_group)):
        word = phrase_group[idx]
        start = p_start if idx == 0 else word["start"]
        if idx < len(phrase_group) - 1:
            end = phrase_group[idx + 1]["start"]
        else:
            end = p_end

        if end <= start:
            end = start + 0.05

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
    if no_shadow or preset == "badge":
        return _NO_SHADOW_TAG
    if preset == "neon":
        return _NEON_SHADOW_TAG
    if preset == "impact":
        return r"\xshad1.8\yshad2.2\blur3\4a&H35&"
    if preset == "hormozi":
        return r"\xshad1.2\yshad2.2\blur2.5\4a&H35&"
    if preset == "cinema":
        return r"\xshad1.5\yshad1.5\blur5\4a&H30&"
    if preset == "sticker":
        return r"\xshad0\yshad0\blur5\4c&HFFFFFF&\4a&H00&"
    if preset == "minimal":
        return r"\xshad0\yshad2.5\blur4\4a&H40&"
    if preset == "casey":
        return r"\xshad0\yshad3.5\blur5\4a&H25&"
    if preset == "billy":
        return r"\xshad0\yshad2.5\blur4\4a&H30&"
    if preset == "aliabdlal":
        return r"\xshad0\yshad3.5\blur6\4c&H000000&\4a&H35&"
    return _SHADOW_TAG


def generate_ass(
    transcript, styling, output_path: str, crop_mode: str = "reframe"
) -> None:
    """Generate an ASS subtitle file from ``transcript`` + ``styling``."""
    import pysubs2

    template = _styling_to_dict(styling)
    preset = normalize_preset(
        template.get("preset")
        or template.get("presetName")
        or template.get("animation")
        or "none"
    )

    user_pos_y = _tpl(template, "position_y", "positionY")
    if user_pos_y is None and preset == "billy":
        template["position_y"] = 0.18


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
    # Dynamic layout typography scaling: gracefully scale down for dense multi-panel layouts
    if overrides.get("fontsize") is None:
        layout_scale_map = {
            "split": 0.90,
            "panel": 0.90,
            "screencast": 0.88,
            "presentation": 0.88,
            "letterbox": 0.92,
        }
        dominant_crop = crop_mode
        if transcript:
            layouts = [
                w.get("layout")
                for b in transcript
                if isinstance(b, dict)
                for w in b.get("words", [])
                if isinstance(w, dict) and w.get("layout")
            ]
            if layouts:
                from collections import Counter
                dominant_crop = Counter(layouts).most_common(1)[0][0]
        scale_mod = layout_scale_map.get((dominant_crop or "").lower(), 1.0)
        base["fontsize"] = int(base["fontsize"] * scale_mod)

    subs.styles["Default"] = _build_style(base, overrides, template, preset=preset)
    if preset in ("unbox", "sara", "badge") or base.get("pillcolor"):
        box_style = _build_style(base, overrides, template, preset=preset)
        box_style.borderstyle = 3
        pill_val = (
            template.get("pill_color")
            or template.get("pillColor")
            or template.get("badgeBg")
            or template.get("badge_bg")
            or base.get("pillcolor")
            or ("#e13a06" if preset == "sara" else "#e004fe")
        )
        pill_c = hex_to_ass_color(pill_val)
        box_style.outlinecolor = pill_c
        box_style.primarycolor = pill_c
        box_style.backcolor = pill_c
        box_style.outline = 0.0
        box_style.shadow = 0.0
        subs.styles["BoxStyle"] = box_style

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
    words_per_phrase = max(2, min(5, int(words_per_phrase)))
    max_chars = template.get("max_chars") or base.get("max_chars_per_line") or 28

    # Highlight color: user override wins, otherwise the preset's own base color.
    h_color_hex = template.get("highlight_color") or base["highlightcolor"]
    no_shadow = overrides.get("shadow") is False or overrides.get("shadow_depth") == 0.0

    groups = _chunk_into_phrases(words, max_words=words_per_phrase, max_chars=int(max_chars))

    MIN_GROUP_DURATION_S = float(template.get("min_group_duration", 0.8))

    multi_speaker_val = template.get("multi_speaker_colors")
    if multi_speaker_val is None:
        multi_speaker_val = template.get("speaker_colors")
    enable_multi_speaker = True if multi_speaker_val is None else bool(multi_speaker_val)

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
            group_pill_color = (
                template.get("pill_color")
                or template.get("pillColor")
                or template.get("badgeBg")
                or template.get("badge_bg")
                or base.get("pillcolor")
            )

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


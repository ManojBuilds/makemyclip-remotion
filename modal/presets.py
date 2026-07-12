"""Caption preset normalization and per-preset base style configuration.

Presets define the *base* visual identity (font, size, outline, alignment, etc.).
User-supplied styling fields override these defaults inside ``ass_builder``.

Canonical preset list (4 premium presets, matching target audiences):
  hormozi, neon-glow, opus, simple
"""

from __future__ import annotations

# Presets that always uppercase their text regardless of the user setting.
ALWAYS_UPPERCASE = {"hormozi", "neon-glow"}


def normalize_preset(preset_str: str) -> str:
    """Normalize a free-form animation/preset name into a canonical preset id."""
    if not preset_str:
        return "hormozi"
    p = preset_str.lower()
    if (
        "hormozi" in p
        or "drop-in" in p
        or "pop-up" in p
        or "beast" in p
        or "overshoot" in p
        or "sticker" in p
    ):
        return "hormozi"
    if "neon" in p or "glow" in p or "flicker" in p:
        return "neon-glow"
    if (
        "opus" in p
        or "viral" in p
        or "spring-pop" in p
        or "popline" in p
        or "underline" in p
        or "slide-up" in p
    ):
        return "opus"
    if (
        "simple" in p
        or "podcast" in p
        or "smooth-fade" in p
        or "box-highlight" in p
        or "box-fade" in p
        or "frosted" in p
    ):
        return "simple"
    return "hormozi"


# Per-preset base style. These are the values the renderer falls back to when
# the user-supplied styling does not override a particular field.
#
# Field meanings:
#   fontname:     fontconfig family
#   fontsize:     reference size (pre-scale)
#   primary:      text fill color
#   outlinecolor: stroke color
#   outline:      stroke width (pre-scale)
#   shadow:       drop-shadow depth
#   backcolor:    optional back-fill, ``(hex, alpha)`` or ``None``
#   secondary:    karaoke / fill-from color
#   alignment:    libass numpad alignment (2=bottom-center, 5=middle-center)
#   marginv:      vertical margin in px (ignored when alignment=5 with marginv=0)
PRESET_STYLES: dict[str, dict] = {
    # ── Hormozi ───────────────────────────────────────────────────────────────
    # Best for: Solo Content Creators & Social Media Agencies. High energy, bold, and punchy.
    # Color Trend 2026: Warm Eggshell White (#FFFDF9) text with a soft Obsidian (#0F0F11) matte outline.
    "hormozi": {
        "fontname": "Bernoru Black Ultra Expanded",
        "fontsize": 48,
        "primary": "#FFFDF9",
        "outlinecolor": "#0F0F11",
        "outline": 5,
        "shadow": 4,
        "backcolor": None,
        "alignment": 2,
        "marginv": 135,
    },
    # ── Neon Glow ─────────────────────────────────────────────────────────────
    # Best for: Twitch Streamers & Gaming Creators. Vibrant pink glow and heavy shadow.
    # Color Trend 2026: Ice White (#FFFFFF) text with a Cyberpunk Magenta (#FF007F) glow stroke.
    "neon-glow": {
        "fontname": "Roxborough CF",
        "fontsize": 68,
        "primary": "#FFFFFF",
        "outlinecolor": "#FF007F",
        "outline": 3,
        "shadow": 10,
        "backcolor": ("#FF007F", 255),
        "alignment": 2,
        "marginv": 120,
    },
    # # ── Opus ──────────────────────────────────────────────────────────────────
    # # Best for: Podcasters & Interview-based Creators. Clean, professional sans-serif.
    # # Color Trend 2026: Premium Cinematic Platinum (#F5F5F7) with a soft Charcoal (#1C1C1E) outline.
    "opus": {
        "fontname": "SF Pro Display Heavy",
        "fontsize": 48,
        "primary": "#000000",
        "outlinecolor": "#FFDC00",
        "outline": 10,
        "shadow": 0,
        "backcolor": ("#FFDC00", 255),
        "borderstyle": 3,
        "border_radius": 8,
        "padding_x": 16,
        "padding_y": 8,
        "alignment": 2,
        "marginv": 120,
    },
    # # ── Simple ────────────────────────────────────────────────────────────────
    # # Best for: SaaS Founders & B2B Marketers. Minimalist, sleek, and brand-safe.
    # # Color Trend 2026: Crisp White (#FFFFFF) text with a fine Zinc/Graphite (#18181B) outline.
    "simple": {
        "fontname": "Space Grotesk Bold",
        "fontsize": 56,
        "primary": "#FFFFFF",
        "outlinecolor": "#18181B",
        "outline": 1.5,
        "shadow": 1,
        "backcolor": None,
        "alignment": 2,
        "marginv": 115,
    },
}

# Default fallback preset
DEFAULT_PRESET_STYLE = {
    "fontname": "Bernoru Black Ultra Expanded",
    "fontsize": 68,
    "primary": "#FFFDF9",
    "outlinecolor": "#0F0F11",
    "outline": 5,
    "shadow": 4,
    "backcolor": None,
    "alignment": 2,
    "marginv": 135,
}


def get_preset_style(preset: str) -> dict:
    """Return a copy of the base style dict for ``preset``."""
    return dict(PRESET_STYLES.get(preset, DEFAULT_PRESET_STYLE))

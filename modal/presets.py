"""Caption preset normalization and per-preset base style configuration.

The system exposes exactly FIVE premium presets, each optimized to look and feel like
a completely different market-leading product:

  1. impact  – TikTok / Shorts / Reels. Anton, white text, yellow active word,
               thick black outline, punchy squash-and-stretch. **Default preset.**
  2. creator – Modern YouTubers / tech / education. Space Grotesk Bold, white text,
               cyan highlight, smooth fade-in + upward slide.
  3. cinema  – Podcasts / interviews / storytelling. Roxborough CF, off-white,
               soft-yellow highlight, hairline outline, opacity-only fade.
  4. focus   – Flagship. Animated rounded highlight pill behind the active word
               (Apple-keynote feel); inactive words white, active word black.
  5. neon    – Gaming / streaming / AI / cyberpunk. Bebas Neue, white text, pink neon
               glow that pulses (blur + subtle scale), vibrant outline.

Presets define the *base* visual identity. User-supplied styling fields override 
these defaults inside ``ass_builder``.
"""

from __future__ import annotations

from typing import TypedDict, Optional, Dict, Tuple, FrozenSet

DEFAULT_PRESET = "impact"

# Presets that always uppercase their text regardless of user settings.
ALWAYS_UPPERCASE: FrozenSet[str] = frozenset({"impact", "neon"})

# ── Alias resolution ─────────────────────────────────────────────────────────
PRESET_ALIASES: Dict[str, Tuple[str, ...]] = {
    "impact": (
        "impact",
        "hormozi",
        "beast",
        "sticker",
        "money",
        "drop-in",
        "pop-up",
        "overshoot",
    ),
    "creator": (
        "creator",
        "opus",
        "viral",
        "popline",
        "spring-pop",
        "slide-up",
        "underline",
        "youtube",
    ),
    "cinema": (
        "cinema",
        "simple",
        "podcast",
        "interview",
        "story",
        "smooth-fade",
    ),
    "focus": (
        "focus",
        "box-highlight",
        "box-fade",
        "boxed",
        "pill",
        "keynote",
        "kelly",
    ),
    "neon": (
        "neon",
        "neon-glow",
        "glow",
        "flicker",
        "gaming",
        "cyberpunk",
    ),
    "luxury": (
        "luxury",
        "typewriter",
        "typewriter_fade",
        "typewriter-fade",
        "playfair",
        "cream",
        "gold",
    ),
}


def hex_to_ass_abgr(hex_str: Optional[str], alpha_hex: str = "00") -> str:
    """Convert a standard CSS hex color (#RGB, #RRGGBB, or #RRGGBBAA) 
    into strict native ASS ABGR hex format: &HAA_BB_GG_RR.
    """
    if not hex_str or hex_str.lower() == "transparent":
        return "&HFF000000"  # Fully transparent black in ASS
    
    clean = hex_str.lstrip("#")
    
    # Expand 3-digit shorthand hex (#RGB -> #RRGGBB)
    if len(clean) == 3:
        clean = "".join([c * 2 for c in clean])
        
    try:
        if len(clean) == 8:
            # #RRGGBBAA -> Convert CSS Alpha (255 opaque) to ASS Alpha (0 opaque)
            r, g, b, a = clean[0:2], clean[2:4], clean[4:6], clean[6:8]
            ass_alpha_int = 255 - int(a, 16)
            alpha_hex = f"{max(0, min(255, ass_alpha_int)):02X}"
        elif len(clean) == 6:
            r, g, b = clean[0:2], clean[2:4], clean[4:6]
        else:
            r, g, b = "FF", "FF", "FF"
    except ValueError:
        # Fallback safeguard on malformed color inputs
        r, g, b = "FF", "FF", "FF"
        
    return f"&H{alpha_hex.upper()}{b.upper()}{g.upper()}{r.upper()}"


class AnimationMetadata(TypedDict):
    animation_type: str
    scale_active: float
    pill_enabled: bool
    pill_padding: Dict[str, int]
    pill_blur: int
    glow_enabled: bool
    glow_blur: int
    sentence_entrance: str


class PresetStyle(TypedDict):
    fontname: str
    fontsize: int
    bold: bool
    uppercase: bool
    primary: str
    highlightcolor: str
    outlinecolor: str
    shadowcolor: str
    pillcolor: Optional[str]
    ass_primary: str
    ass_highlight: str
    ass_outline: str
    ass_shadow: str
    ass_pill: Optional[str]
    outline: float
    shadow: float
    backcolor: Optional[Tuple[str, int]]
    alignment: int
    marginv: int
    preferred_words: int
    max_chars_per_line: int
    animation_metadata: AnimationMetadata


def normalize_preset(preset_str: Optional[str]) -> str:
    """Normalize a free-form animation/preset name into a canonical preset id securely."""
    if not preset_str:
        return DEFAULT_PRESET
    p = preset_str.strip().lower()
    if p in PRESET_ALIASES:
        return p
    for canonical, aliases in PRESET_ALIASES.items():
        if any(alias in p for alias in aliases):
            return canonical
    return DEFAULT_PRESET


# ── Base styles (Optimized for 1080x1920 Vertical Video) ─────────────────────
PRESET_STYLES: Dict[str, PresetStyle] = {
    # ── 1. Impact ─────────────────────────────────────────────────────────────
    # TikTok / Shorts / Reels. Heavy Anton, white with a punchy yellow active
    # word and a thick black outline. 
    "impact": {
        "fontname": "Anton",
        "fontsize": 120,
        "bold": True,
        "uppercase": True,
        "primary": "#FFFFFF",
        "highlightcolor": "#FFE500",
        "outlinecolor": "#000000",
        "shadowcolor": "#000000",
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#FFE500", "00"),
        "ass_outline": hex_to_ass_abgr("#000000", "00"),
        "ass_shadow": hex_to_ass_abgr("#000000", "20"),
        "ass_pill": None,
        "outline": 6.0,
        "shadow": 3.0,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,  # Safely above platform UI overlays
        "preferred_words": 2,
        "max_chars_per_line": 18,
        "animation_metadata": {
            "animation_type": "squash_stretch",
            "scale_active": 1.12,
            "pill_enabled": False,
            "pill_padding": {"x": 0, "y": 0},
            "pill_blur": 0,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "squash",
        },
    },
    # ── 2. Creator ────────────────────────────────────────────────────────────
    # Modern YouTubers / tech / education. Space Grotesk Bold, clean cyan highlight.
    "creator": {
        "fontname": "Space Grotesk",
        "fontsize": 76,
        "bold": True,
        "uppercase": False,
        "primary": "#FFFFFF",
        "highlightcolor": "#22D3EE",
        "outlinecolor": "#000000",
        "shadowcolor": "#000000",
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#22D3EE", "00"),
        "ass_outline": hex_to_ass_abgr("#000000", "00"),
        "ass_shadow": hex_to_ass_abgr("#000000", "40"),
        "ass_pill": None,
        "outline": 1.0,
        "shadow": 4.0,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 4,
        "max_chars_per_line": 26,
        "animation_metadata": {
            "animation_type": "slide_up_fade",
            "scale_active": 1.05,
            "pill_enabled": False,
            "pill_padding": {"x": 0, "y": 0},
            "pill_blur": 0,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "slide_up",
        },
    },
    # ── 3. Cinema ──────────────────────────────────────────────────────────────
    # Podcasts / interviews / storytelling. Roxborough CF serif, soft yellow highlight.
    "cinema": {
        "fontname": "Roxborough CF",
        "fontsize": 74,
        "bold": True,
        "uppercase": False,
        "primary": "#FFFFFF",
        "highlightcolor": "#FFC83B",
        "outlinecolor": "#000000",
        "shadowcolor": "#000000",
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#FFC83B", "00"),
        "ass_outline": hex_to_ass_abgr("#000000", "00"),
        "ass_shadow": hex_to_ass_abgr("#000000", "30"),
        "ass_pill": None,
        "outline": 0.5,
        "shadow": 3.0,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 4,
        "max_chars_per_line": 28,
        "animation_metadata": {
            "animation_type": "opacity_fade",
            "scale_active": 1.00,
            "pill_enabled": False,
            "pill_padding": {"x": 0, "y": 0},
            "pill_blur": 0,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "fade",
        },
    },
    # ── 4. Focus (flagship) ─────────────────────────────────────────────────────
    # Animated rounded highlight pill. Inactive words white, active word black on a yellow pill.
    "focus": {
        "fontname": "SF Pro Display Bold",
        "fontsize": 66,
        "bold": True,
        "uppercase": False,
        "primary": "#FFFFFF",
        "highlightcolor": "#0A0A0A",
        "outlinecolor": "#000000",
        "shadowcolor": "#000000",
        "pillcolor": "#FFE500",
        "ass_primary": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#0A0A0A", "00"),
        "ass_outline": hex_to_ass_abgr("#000000", "00"),
        "ass_shadow": hex_to_ass_abgr("#000000", "20"),
        "ass_pill": hex_to_ass_abgr("#FFE500", "00"),
        "outline": 1.5,
        "shadow": 2.0,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 4,
        "max_chars_per_line": 26,
        "animation_metadata": {
            "animation_type": "pill_grow",
            "scale_active": 1.00,
            "pill_enabled": True,
            "pill_padding": {"x": 22, "y": 12},
            "pill_blur": 2,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "none",
        },
    },
    # ── 5. Neon ──────────────────────────────────────────────────────────────────
    # Gaming / streaming / AI / cyberpunk. Bebas Neue, pulsing pink neon glow.
    "neon": {
        "fontname": "Bebas Neue",
        "fontsize": 90,
        "bold": True,
        "uppercase": True,
        "primary": "#FFFFFF",
        "highlightcolor": "#FF2A85",
        "outlinecolor": "#FF0055",
        "shadowcolor": "#FF0055",
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#FF2A85", "00"),
        "ass_outline": hex_to_ass_abgr("#FF0055", "00"),
        "ass_shadow": hex_to_ass_abgr("#FF0055", "10"),
        "ass_pill": None,
        "outline": 1.5,
        "shadow": 8.0,
        "backcolor": ("#FF0055", 255),
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 2,
        "max_chars_per_line": 18,
        "animation_metadata": {
            "animation_type": "neon_pulse",
            "scale_active": 1.08,
            "pill_enabled": False,
            "pill_padding": {"x": 0, "y": 0},
            "pill_blur": 0,
            "glow_enabled": True,
            "glow_blur": 8,
            "sentence_entrance": "none",
        },
    },
    # ── 6. Luxury ────────────────────────────────────────────────────────────────
    # Elegant / editorial. Playfair Display, warm cream inactive words, metallic gold active word.
    "luxury": {
        "fontname": "Playfair Display",
        "fontsize": 74,
        "bold": True,
        "uppercase": False,
        "primary": "#FAF9F6",
        "highlightcolor": "#F3E5AB",
        "outlinecolor": "#2C1D11",
        "shadowcolor": "#120B05",
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#FAF9F6", "00"),
        "ass_highlight": hex_to_ass_abgr("#F3E5AB", "00"),
        "ass_outline": hex_to_ass_abgr("#2C1D11", "00"),
        "ass_shadow": hex_to_ass_abgr("#120B05", "20"),
        "ass_pill": None,
        "outline": 1.2,
        "shadow": 4.5,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 4,
        "max_chars_per_line": 28,
        "animation_metadata": {
            "animation_type": "shimmer_rise",
            "scale_active": 1.06,
            "pill_enabled": False,
            "pill_padding": {"x": 0, "y": 0},
            "pill_blur": 0,
            "glow_enabled": True,
            "glow_blur": 4,
            "sentence_entrance": "shimmer_fade",
        },
    },
}

DEFAULT_PRESET_STYLE: PresetStyle = dict(PRESET_STYLES[DEFAULT_PRESET])


def get_preset_style(preset: str) -> PresetStyle:
    """Return a safe dictionary copy of the base style for a given normalized preset."""
    normalized = normalize_preset(preset)
    return dict(PRESET_STYLES.get(normalized, DEFAULT_PRESET_STYLE))
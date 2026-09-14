"""Caption preset normalization and per-preset base style configuration.

The system exposes SEVEN premium presets, each optimized to look and feel like
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
  6. luxury  – Editorial / fashion / quotes. Playfair Display, alabaster cream text,
               metallic gold active word, shimmer & rise tracking expansion.
  7. badge   – Clean Card / Badge style (Vizard.ai / modern minimalist). Rounded white
               container box with generous X/Y padding; inactive words dimmed in soft muted gray,
               active word in bold high-contrast black.

Presets define the *base* visual identity. User-supplied styling fields override 
these defaults inside ``ass_builder``.
"""

from __future__ import annotations

from typing import TypedDict, Optional, Dict, Tuple, FrozenSet

DEFAULT_PRESET = "impact"

# Presets that always uppercase their text regardless of user settings.
ALWAYS_UPPERCASE: FrozenSet[str] = frozenset(
    {"impact", "neon", "growth", "coral", "sticker", "tom", "casey", "unbox"}
)

# ── Alias resolution ─────────────────────────────────────────────────────────
PRESET_ALIASES: Dict[str, Tuple[str, ...]] = {
    "hormozi": (
        "hormozi",
        "slant",
        "italic",
        "viral_italic",
        "fast_pace",
        "alex",
    ),
    "growth": (
        "growth",
        "scale",
        "finance",
        "money",
        "green",
        "lime",
        "crypto",
    ),
    "coral": (
        "coral",
        "red",
        "hottake",
        "warning",
        "drama",
        "urgent",
    ),
    "sticker": (
        "sticker",
        "double_border",
        "cutout",
        "popout",
        "indeed",
    ),
    "minimal": (
        "minimal",
        "klap",
        "dimmed",
        "subtle",
        "lex",
        "conversational",
    ),
    "impact": (
        "impact",
        "beast",
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
        "story",
        "smooth-fade",
        "film",
        "documentary",
    ),
    "podcast": (
        "podcast",
        "interview",
        "talk",
        "montserrat",
        "huberman",
        "rogan",
        "diary",
    ),
    "focus": (
        "focus",
        "box-highlight",
        "box-fade",
        "pill",
        "keynote",
        "kelly",
    ),
    "badge": (
        "badge",
        "card",
        "box",
        "boxed",
        "vizard",
        "pill_box",
        "minimal_box",
        "clean_box",
        "container",
        "white_box",
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
    "bobby": (
        "bobby",
        "althoff",
        "bobbi",
        "klap_bobby",
    ),
    "tom": (
        "tom",
        "holland",
        "red_pill",
        "klap_tom",
    ),
    "casey": (
        "casey",
        "neistat",
        "orange_outline",
        "klap_casey",
    ),
    "fred": (
        "fred",
        "garyvee",
        "green_word",
        "klap_fred",
    ),
    "sara": (
        "sara",
        "dietschy",
        "orange_pill",
        "klap_sara",
    ),
    "billy": (
        "billy",
        "billie",
        "eilish",
        "purple_outline",
        "top_subtitle",
        "klap_billy",
    ),
    "unbox": (
        "unbox",
        "therapy",
        "magenta_pill",
        "fuchsia_pill",
        "klap_unbox",
    ),
    "aliabdlal": (
        "aliabdlal",
        "aliabdaal",
        "ali",
        "abdaal",
        "ali_abdaal",
        "ali-abdaal",
        "ali_abdlal",
        "ali-abdlal",
        "recoleta",
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


class PresetStyle(TypedDict, total=False):
    fontname: str
    fontsize: int
    bold: bool
    italic: bool
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
    borderstyle: Optional[int]
    alignment: int
    marginv: int
    preferred_words: int
    max_chars_per_line: int
    word_highlight_default: bool
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


# ── Base styles (Optimized for 1080x1920 Vertical Video & Multi-Layouts) ──────
PRESET_STYLES: Dict[str, PresetStyle] = {
    # ── 1. Impact ─────────────────────────────────────────────────────────────
    # Punchy Anton bold, high-contrast white with vibrant canary-yellow active highlight,
    # crisp black outline, subtle shadow, and -3.5° counter-clockwise tilt.
    "impact": {
        "fontname": "Anton",
        "fontsize": 118,
        "bold": True,
        "italic": False,
        "uppercase": True,
        "primary": "#FFFFFF",
        "highlightcolor": "#FFE600",
        "outlinecolor": "#000000",
        "shadowcolor": "#000000",
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#FFE600", "00"),
        "ass_outline": hex_to_ass_abgr("#000000", "00"),
        "ass_shadow": hex_to_ass_abgr("#000000", "35"),
        "ass_pill": None,
        "outline": 5.2,
        "shadow": 2.8,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 3,
        "max_chars_per_line": 20,
        "word_highlight_default": True,
        "animation_metadata": {
            "animation_type": "none",
            "scale_active": 1.00,
            "pill_enabled": False,
            "pill_padding": {"x": 0, "y": 0},
            "pill_blur": 0,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "none",
        },
    },
    # ── 1b. Hormozi (Official YouTube Shorts Italic) ──────────────────────────
    # Alex Hormozi signature YouTube Shorts subtitle: Poppins ExtraBold with forward italic slant,
    # natural sentence case, pure white base, and progressive golden yellow cumulative highlight.
    "hormozi": {
        "fontname": "Poppins ExtraBold",
        "fontsize": 98,
        "bold": True,
        "italic": True,
        "uppercase": False,
        "primary": "#FFFFFF",
        "highlightcolor": "#FFB800",
        "outlinecolor": "#000000",
        "shadowcolor": "#000000",
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#FFB800", "00"),
        "ass_outline": hex_to_ass_abgr("#000000", "00"),
        "ass_shadow": hex_to_ass_abgr("#000000", "35"),
        "ass_pill": None,
        "outline": 3.8,
        "shadow": 2.6,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 5,
        "max_chars_per_line": 26,
        "word_highlight_default": True,
        "animation_metadata": {
            "animation_type": "cumulative_karaoke",
            "scale_active": 1.00,
            "pill_enabled": False,
            "pill_padding": {"x": 0, "y": 0},
            "pill_blur": 0,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "none",
        },
    },
    # ── 1c. Growth / Finance (HiClip SCALE / Klap Business) ─────────────────
    # Heavy Archivo Black with vibrant Electric Lime Green active highlight.
    "growth": {
        "fontname": "Archivo Black",
        "fontsize": 78,
        "bold": True,
        "italic": False,
        "uppercase": True,
        "primary": "#FFFFFF",
        "highlightcolor": "#00FF66",
        "outlinecolor": "#000000",
        "shadowcolor": "#000000",
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#00FF66", "00"),
        "ass_outline": hex_to_ass_abgr("#000000", "00"),
        "ass_shadow": hex_to_ass_abgr("#000000", "30"),
        "ass_pill": None,
        "outline": 3.4,
        "shadow": 3.5,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 2,
        "max_chars_per_line": 20,
        "word_highlight_default": True,
        "animation_metadata": {
            "animation_type": "squash_stretch",
            "scale_active": 1.00,
            "pill_enabled": False,
            "pill_padding": {"x": 0, "y": 0},
            "pill_blur": 0,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "squash",
        },
    },
    # ── 1d. Coral / Hot Take (HiClip NICE Signature) ────────────────────────
    # Sora ExtraBold with high-energy Neon Coral / Crimson active word.
    "coral": {
        "fontname": "Sora ExtraBold",
        "fontsize": 80,
        "bold": True,
        "italic": False,
        "uppercase": True,
        "primary": "#FFFFFF",
        "highlightcolor": "#FF1E56",
        "outlinecolor": "#000000",
        "shadowcolor": "#000000",
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#FF1E56", "00"),
        "ass_outline": hex_to_ass_abgr("#000000", "00"),
        "ass_shadow": hex_to_ass_abgr("#000000", "30"),
        "ass_pill": None,
        "outline": 3.6,
        "shadow": 3.5,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 2,
        "max_chars_per_line": 18,
        "word_highlight_default": True,
        "animation_metadata": {
            "animation_type": "squash_stretch",
            "scale_active": 1.00,
            "pill_enabled": False,
            "pill_padding": {"x": 0, "y": 0},
            "pill_blur": 0,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "squash",
        },
    },
    # ── 1e. Sticker / Double-Border (HiClip INDEED Signature) ───────────────
    # White core with black outline and secondary white sticker cut-out halo.
    "sticker": {
        "fontname": "Montserrat",
        "fontsize": 78,
        "bold": True,
        "italic": False,
        "uppercase": True,
        "primary": "#FFFFFF",
        "highlightcolor": "#FFE600",
        "outlinecolor": "#000000",
        "shadowcolor": "#FFFFFF",
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#FFE600", "00"),
        "ass_outline": hex_to_ass_abgr("#000000", "00"),
        "ass_shadow": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_pill": None,
        "outline": 3.6,
        "shadow": 4.0,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 2,
        "max_chars_per_line": 20,
        "word_highlight_default": True,
        "animation_metadata": {
            "animation_type": "squash_stretch",
            "scale_active": 1.00,
            "pill_enabled": False,
            "pill_padding": {"x": 0, "y": 0},
            "pill_blur": 0,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "squash",
        },
    },
    # ── 1f. Minimal / Dimmed (Klap.app Signature Style) ─────────────────────
    # Dimmed slate gray inactive words (#94A3B8) with pure crisp white active word.
    "minimal": {
        "fontname": "Inter",
        "fontsize": 76,
        "bold": True,
        "italic": False,
        "uppercase": False,
        "primary": "#94A3B8",
        "highlightcolor": "#FFFFFF",
        "outlinecolor": "#0C0C10",
        "shadowcolor": "#000000",
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#94A3B8", "00"),
        "ass_highlight": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_outline": hex_to_ass_abgr("#0C0C10", "00"),
        "ass_shadow": hex_to_ass_abgr("#000000", "30"),
        "ass_pill": None,
        "outline": 1.8,
        "shadow": 3.0,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 3,
        "max_chars_per_line": 26,
        "word_highlight_default": True,
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
    # ── 2. Creator ────────────────────────────────────────────────────────────
    # Modern YouTubers / tech / education. Space Grotesk Bold, electric cyber cyan highlight.
    "creator": {
        "fontname": "Space Grotesk",
        "fontsize": 78,
        "bold": True,
        "uppercase": False,
        "primary": "#FFFFFF",
        "highlightcolor": "#00F0FF",
        "outlinecolor": "#0A0A12",
        "shadowcolor": "#000000",
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#00F0FF", "00"),
        "ass_outline": hex_to_ass_abgr("#0A0A12", "00"),
        "ass_shadow": hex_to_ass_abgr("#000000", "35"),
        "ass_pill": None,
        "outline": 3.2,
        "shadow": 3.5,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 3,
        "max_chars_per_line": 24,
        "word_highlight_default": True,
        "animation_metadata": {
            "animation_type": "slide_up_fade",
            "scale_active": 1.00,
            "pill_enabled": False,
            "pill_padding": {"x": 0, "y": 0},
            "pill_blur": 0,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "slide_up",
        },
    },
    # ── 3. Cinema ──────────────────────────────────────────────────────────────
    # A24 / Netflix / documentary / podcasts. DM Sans Bold, clean off-white text,
    # subtle soft drop-shadow, immersive phrase-level crossfade (true cinema film subtitle).
    "cinema": {
        "fontname": "DM Sans",
        "fontsize": 66,
        "bold": True,
        "uppercase": False,
        "primary": "#F4F4F6",
        "highlightcolor": "#F4F4F6",
        "outlinecolor": "#0C0C10",
        "shadowcolor": "#000000",
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#F4F4F6", "00"),
        "ass_highlight": hex_to_ass_abgr("#F4F4F6", "00"),
        "ass_outline": hex_to_ass_abgr("#0C0C10", "00"),
        "ass_shadow": hex_to_ass_abgr("#000000", "35"),
        "ass_pill": None,
        "outline": 2.0,
        "shadow": 3.0,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 4,
        "max_chars_per_line": 32,
        "word_highlight_default": False,
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
    # Animated rounded highlight pill (Apple Keynote feel). SF Pro Display, inactive words white, active word on yellow pill.
    "focus": {
        "fontname": "SF Pro Display",
        "fontsize": 76,
        "bold": True,
        "uppercase": False,
        "primary": "#FFFFFF",
        "highlightcolor": "#FFE600",
        "outlinecolor": "#000000",
        "shadowcolor": "#000000",
        "pillcolor": "#FFE600",
        "ass_primary": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#FFE600", "00"),
        "ass_outline": hex_to_ass_abgr("#000000", "00"),
        "ass_shadow": hex_to_ass_abgr("#000000", "20"),
        "ass_pill": hex_to_ass_abgr("#FFE600", "00"),
        "outline": 3.6,
        "shadow": 4.0,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 3,
        "max_chars_per_line": 24,
        "word_highlight_default": True,
        "animation_metadata": {
            "animation_type": "pill_grow",
            "scale_active": 1.00,
            "pill_enabled": True,
            "pill_padding": {"x": 24, "y": 12},
            "pill_blur": 2,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "none",
        },
    },
    # ── 5. Neon (Synthwave Dual-Tone Cyberpunk) ──────────────────────────────────
    # Gaming / streaming / AI / cyberpunk. Montserrat Black, Synthwave dual-tone neon:
    # glowing cyan ambient text, active word detonating in pure white core with hot magenta bloom.
    "neon": {
        "fontname": "Montserrat Black",
        "fontsize": 78,
        "bold": True,
        "uppercase": True,
        "primary": "#00FFFF",
        "highlightcolor": "#FF007F",
        "outlinecolor": "#003080",
        "shadowcolor": "#00FFFF",
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#00FFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#FF007F", "00"),
        "ass_outline": hex_to_ass_abgr("#003080", "00"),
        "ass_shadow": hex_to_ass_abgr("#00FFFF", "00"),
        "ass_pill": None,
        "outline": 3.0,
        "shadow": 4.0,
        "backcolor": ("#00FFFF", 0),
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 3,
        "max_chars_per_line": 22,
        "word_highlight_default": True,
        "animation_metadata": {
            "animation_type": "neon_surge",
            "scale_active": 1.14,
            "pill_enabled": False,
            "pill_padding": {"x": 0, "y": 0},
            "pill_blur": 0,
            "glow_enabled": True,
            "glow_blur": 16,
            "sentence_entrance": "none",
        },
    },
    # ── 6. Luxury ────────────────────────────────────────────────────────────────
    # Elegant / editorial. Playfair Display, luxury alabaster cream text, metallic champagne gold active word.
    "luxury": {
        "fontname": "Playfair Display",
        "fontsize": 76,
        "bold": True,
        "uppercase": False,
        "primary": "#FFFDF8",
        "highlightcolor": "#FFD700",
        "outlinecolor": "#140B07",
        "shadowcolor": "#080402",
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#FFFDF8", "00"),
        "ass_highlight": hex_to_ass_abgr("#FFD700", "00"),
        "ass_outline": hex_to_ass_abgr("#140B07", "00"),
        "ass_shadow": hex_to_ass_abgr("#080402", "20"),
        "ass_pill": None,
        "outline": 3.2,
        "shadow": 4.5,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 4,
        "max_chars_per_line": 28,
        "word_highlight_default": False,
        "animation_metadata": {
            "animation_type": "shimmer_rise",
            "scale_active": 1.06,
            "pill_enabled": False,
            "pill_padding": {"x": 0, "y": 0},
            "pill_blur": 0,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "shimmer_fade",
        },
    },
    # ── 7. Badge (Modern White Pill Card / Progressive) ───────────────────────
    # Clean Card / Badge style (2026 modern minimalist). Poppins font.
    # Solid white rounded pill card with soft drop shadow; spoken words in high-contrast
    # bold charcoal black, upcoming inactive words in soft muted grey.
    "badge": {
        "fontname": "Poppins",
        "fontsize": 68,
        "bold": True,
        "uppercase": False,
        "primary": "#A0A0A8",
        "highlightcolor": "#111111",
        "outlinecolor": "#FFFFFF",
        "shadowcolor": "#000000",
        "pillcolor": "#FFFFFF",
        "ass_primary": hex_to_ass_abgr("#A0A0A8", "00"),
        "ass_highlight": hex_to_ass_abgr("#111111", "00"),
        "ass_outline": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_shadow": hex_to_ass_abgr("#000000", "00"),
        "ass_pill": hex_to_ass_abgr("#FFFFFF", "00"),
        "outline": 0.0,
        "shadow": 0.0,
        "backcolor": ("#FFFFFF", 0),
        "borderstyle": 3,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 4,
        "max_chars_per_line": 26,
        "word_highlight_default": True,
        "animation_metadata": {
            "animation_type": "badge_pill",
            "scale_active": 1.00,
            "pill_enabled": True,
            "pill_padding": {"x": 32, "y": 14},
            "pill_blur": 2,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "fade",
        },
    },
    # ── 8. Podcast ────────────────────────────────────────────────────────────
    # Modern podcast / interview / conversational clips (Huberman / Joe Rogan / Diary of a CEO style).
    # Manrope conversational typography, crisp solid white text with a bold, defined black outline and natural sentence casing.
    "podcast": {
        "fontname": "Manrope",
        "fontsize": 74,
        "bold": True,
        "uppercase": False,
        "primary": "#FFFFFF",
        "highlightcolor": "#FFE600",
        "outlinecolor": "#000000",
        "shadowcolor": "#000000",
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#FFE600", "00"),
        "ass_outline": hex_to_ass_abgr("#000000", "00"),
        "ass_shadow": hex_to_ass_abgr("#000000", "25"),
        "ass_pill": None,
        "outline": 3.4,
        "shadow": 3.0,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 3,
        "max_chars_per_line": 24,
        "word_highlight_default": True,
        "animation_metadata": {
            "animation_type": "pop_fade",
            "scale_active": 1.00,
            "pill_enabled": False,
            "pill_padding": {"x": 0, "y": 0},
            "pill_blur": 0,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "fade",
        },
    },
    # ── 9. Bobby (Klap Bobbi Althoff Style) ───────────────────────────────────
    # Lowercase, clean geometric bold font with cyber yellow word highlight and thick black outline.
    "bobby": {
        "fontname": "Poppins ExtraBold",
        "fontsize": 84,
        "bold": True,
        "uppercase": False,
        "primary": "#fbf0d2",
        "highlightcolor": "#fcbb42",
        "outlinecolor": "#000000",
        "shadowcolor": None,
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#fbf0d2", "00"),
        "ass_highlight": hex_to_ass_abgr("#fcbb42", "00"),
        "ass_outline": hex_to_ass_abgr("#000000", "00"),
        "ass_shadow": hex_to_ass_abgr("#000000", "FF"),
        "ass_pill": None,
        "outline": 5.0,
        "shadow": 0.0,
        "extrusion_3d": True,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 3,
        "max_chars_per_line": 22,
        "word_highlight_default": True,
        "animation_metadata": {
            "animation_type": "squash_stretch",
            "scale_active": 1.00,
            "pill_enabled": False,
            "pill_padding": {"x": 0, "y": 0},
            "pill_blur": 0,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "squash",
            "extrusion_3d": True,
        },
    },
    # ── 10. Tom (Klap Tom Holland Style) ──────────────────────────────────────
    # ALL CAPS Archivo Black with deep crimson outline (#a1193d) and pure white text.
    "tom": {
        "fontname": "Archivo Black",
        "fontsize": 88,
        "bold": True,
        "uppercase": True,
        "primary": "#FFFFFF",
        "highlightcolor": "#FFFFFF",
        "outlinecolor": "#a1193d",
        "shadowcolor": None,
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_outline": hex_to_ass_abgr("#a1193d", "00"),
        "ass_shadow": hex_to_ass_abgr("#a1193d", "FF"),
        "ass_pill": None,
        "outline": 5.0,
        "shadow": 0.0,
        "extrusion_3d": True,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 3,
        "max_chars_per_line": 20,
        "word_highlight_default": False,
        "animation_metadata": {
            "animation_type": "squash_stretch",
            "scale_active": 1.00,
            "pill_enabled": False,
            "pill_padding": {"x": 0, "y": 0},
            "pill_blur": 0,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "squash",
            "extrusion_3d": True,
        },
    },
    # ── 11. Casey (Klap Casey Neistat Style) ──────────────────────────────────
    # ALL CAPS, heavy bold font with thick electric neon orange outline (#ed7500) and 3D extrusion.
    "casey": {
        "fontname": "THE BOLD FONT",
        "fontsize": 98,
        "bold": True,
        "uppercase": True,
        "primary": "#FFFFFF",
        "highlightcolor": "#FFFFFF",
        "outlinecolor": "#ed7500",
        "shadowcolor": None,
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_outline": hex_to_ass_abgr("#ed7500", "00"),
        "ass_shadow": hex_to_ass_abgr("#ed7500", "FF"),
        "ass_pill": None,
        "outline": 7.5,
        "shadow": 0.0,
        "extrusion_3d": True,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 2,
        "max_chars_per_line": 18,
        "word_highlight_default": False,
        "animation_metadata": {
            "animation_type": "squash_stretch",
            "scale_active": 1.00,
            "pill_enabled": False,
            "pill_padding": {"x": 0, "y": 0},
            "pill_blur": 0,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "squash",
            "extrusion_3d": True,
        },
    },
    # ── 12. Fred (Klap GaryVee / Fred Style) ──────────────────────────────────
    # Natural Cabin Bold with rich emerald green active word highlight (#28ae67) and 3D black outline.
    "fred": {
        "fontname": "Cabin",
        "fontsize": 84,
        "bold": True,
        "uppercase": False,
        "primary": "#FFFFFF",
        "highlightcolor": "#28ae67",
        "outlinecolor": "#000000",
        "shadowcolor": None,
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#28ae67", "00"),
        "ass_outline": hex_to_ass_abgr("#000000", "00"),
        "ass_shadow": hex_to_ass_abgr("#000000", "FF"),
        "ass_pill": None,
        "outline": 5.0,
        "shadow": 0.0,
        "extrusion_3d": True,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 3,
        "max_chars_per_line": 22,
        "word_highlight_default": True,
        "animation_metadata": {
            "animation_type": "squash_stretch",
            "scale_active": 1.00,
            "pill_enabled": False,
            "pill_padding": {"x": 0, "y": 0},
            "pill_blur": 0,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "squash",
            "extrusion_3d": True,
        },
    },
    # ── 13. Sara (Klap Sara Dietschy Style) ───────────────────────────────────
    # Plus Jakarta Sans ExtraBold with burnt orange active word pill (#e13a06), black outline & 3D extrusion.
    "sara": {
        "fontname": "Plus Jakarta Sans ExtraBold",
        "fontsize": 84,
        "bold": True,
        "uppercase": False,
        "primary": "#FFFFFF",
        "highlightcolor": "#FFFFFF",
        "outlinecolor": "#000000",
        "shadowcolor": None,
        "pillcolor": "#e13a06",
        "ass_primary": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_outline": hex_to_ass_abgr("#000000", "00"),
        "ass_shadow": hex_to_ass_abgr("#000000", "FF"),
        "ass_pill": hex_to_ass_abgr("#e13a06", "00"),
        "outline": 5.0,
        "shadow": 0.0,
        "extrusion_3d": True,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 3,
        "max_chars_per_line": 22,
        "word_highlight_default": True,
        "animation_metadata": {
            "animation_type": "squash_stretch",
            "scale_active": 1.00,
            "pill_enabled": True,
            "pill_padding": {"x": 20, "y": 10},
            "pill_blur": 0,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "squash",
            "extrusion_3d": True,
        },
    },
    # ── 14. Billy (Klap Billie Eilish Style) ──────────────────────────────────
    # Top-positioned subtitle (above head), lowercase with deep purple 3D outline (#56417c) and off-white text.
    "billy": {
        "fontname": "Poppins ExtraBold",
        "fontsize": 126,
        "bold": True,
        "uppercase": False,
        "primary": "#fbfcfb",
        "highlightcolor": "#fbfcfb",
        "outlinecolor": "#56417c",
        "shadowcolor": None,
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#fbfcfb", "00"),
        "ass_highlight": hex_to_ass_abgr("#fbfcfb", "00"),
        "ass_outline": hex_to_ass_abgr("#56417c", "00"),
        "ass_shadow": hex_to_ass_abgr("#56417c", "FF"),
        "ass_pill": None,
        "outline": 5.0,
        "shadow": 0.0,
        "backcolor": None,
        "alignment": 8,
        "marginv": 300,
        "preferred_words": 2,
        "max_chars_per_line": 18,
        "word_highlight_default": False,
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
    # ── 15. Unbox (Klap Unbox Therapy Style) ──────────────────────────────────
    # ALL CAPS Montserrat ExtraBold with neon magenta / fuchsia active word pill, black outline & 3D extrusion.
    "unbox": {
        "fontname": "Montserrat ExtraBold",
        "fontsize": 86,
        "bold": True,
        "uppercase": True,
        "primary": "#FFFFFF",
        "highlightcolor": "#FFFFFF",
        "outlinecolor": "#000000",
        "shadowcolor": None,
        "pillcolor": "#e004fe",
        "ass_primary": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_outline": hex_to_ass_abgr("#000000", "00"),
        "ass_shadow": hex_to_ass_abgr("#000000", "FF"),
        "ass_pill": hex_to_ass_abgr("#e004fe", "00"),
        "outline": 5.0,
        "shadow": 0.0,
        "extrusion_3d": True,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 2,
        "max_chars_per_line": 18,
        "word_highlight_default": True,
        "animation_metadata": {
            "animation_type": "squash_stretch",
            "scale_active": 1.00,
            "pill_enabled": True,
            "pill_padding": {"x": 20, "y": 10},
            "pill_blur": 0,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "squash",
            "extrusion_3d": True,
        },
    },
    # ── 16. Ali Abdaal (Editorial Clean / Recoleta) ───────────────────────────
    # Signature Ali Abdaal style: Recoleta font, pure white text (#FFFFFF), vibrant
    # terracotta / burnt orange active word (#f06c3f) with dynamic highlighter sweep,
    # no harsh outline, soft drop shadow, big editorial typography.
    "aliabdlal": {
        "fontname": "Recoleta",
        "fontsize": 120,
        "bold": True,
        "uppercase": False,
        "primary": "#FFFFFF",
        "highlightcolor": "#f06c3f",
        "outlinecolor": "#000000",
        "shadowcolor": "#000000",
        "pillcolor": None,
        "ass_primary": hex_to_ass_abgr("#FFFFFF", "00"),
        "ass_highlight": hex_to_ass_abgr("#f06c3f", "00"),
        "ass_outline": hex_to_ass_abgr("#000000", "00"),
        "ass_shadow": hex_to_ass_abgr("#000000", "35"),
        "ass_pill": None,
        "outline": 3.6,
        "shadow": 4.0,
        "backcolor": None,
        "alignment": 2,
        "marginv": 320,
        "preferred_words": 2,
        "max_chars_per_line": 20,
        "word_highlight_default": True,
        "animation_metadata": {
            "animation_type": "highlighter_sweep",
            "scale_active": 1.0,
            "pill_enabled": False,
            "pill_padding": {"x": 0, "y": 0},
            "pill_blur": 0,
            "glow_enabled": False,
            "glow_blur": 0,
            "sentence_entrance": "stable",
        },
    },
}

DEFAULT_PRESET_STYLE: PresetStyle = dict(PRESET_STYLES[DEFAULT_PRESET])


def get_preset_style(preset: str) -> PresetStyle:
    """Return a safe dictionary copy of the base style for a given normalized preset."""
    normalized = normalize_preset(preset)
    return dict(PRESET_STYLES.get(normalized, DEFAULT_PRESET_STYLE))
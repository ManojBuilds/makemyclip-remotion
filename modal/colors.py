"""ASS subtitle color helpers.

ASS uses BGR byte order with an inverted alpha channel (0 = opaque, 255 = transparent).
"""

from __future__ import annotations


def hex_to_ass_color(hex_color, alpha: int = 0):
    """Convert a CSS-style hex color (#RRGGBB or #RRGGBBAA) into a pysubs2.Color.

    Returns fully-transparent black for ``None`` / ``"transparent"`` so the
    caller can pass styling-template values directly without pre-processing.
    """
    import pysubs2

    if hex_color is None or hex_color == "transparent":
        return pysubs2.Color(0, 0, 0, 255)  # fully transparent

    h = hex_color.replace("#", "")
    r, g, b = 255, 255, 255
    a = alpha
    if len(h) >= 6:
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
    if len(h) == 8:
        # 8-char hex includes CSS-style alpha. Convert CSS alpha (255=opaque)
        # to ASS alpha (0=opaque).
        a_hex = int(h[6:8], 16)
        a = 255 - a_hex
    return pysubs2.Color(r, g, b, a)


def ass_color_override(hex_color) -> str:
    """Return an inline ASS ``\\c&HBBGGRR&`` color-override tag for ``hex_color``."""
    c = hex_to_ass_color(hex_color)
    return f"\\c&H{c.b:02X}{c.g:02X}{c.r:02X}&"

"""Font name resolution.

Frontend-supplied font names (often filenames like `Anton-Regular`) are mapped
to the actual font-family name registered with fontconfig inside the container.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("makemyclip.fonts")

# Map user-facing names (filename / friendly form) → fontconfig family name
FONT_NAME_MAP: dict[str, str] = {
    # SF Pro Display Bold / Heavy
    "SF Pro Display Bold": "SF Pro Display",
    "SF-Pro-Display-Bold": "SF Pro Display",
    "SF Pro Display Heavy": "SF Pro Display",
    "SF-Pro-Display-Heavy": "SF Pro Display",
    "SF Pro Display": "SF Pro Display",

    # Montserrat
    "Montserrat-Variable-wght": "Montserrat",
    "Montserrat-Regular": "Montserrat",
    "Montserrat": "Montserrat",
    "Montserrat SemiBold": "Montserrat",
    "Montserrat-SemiBold": "Montserrat",
    "Montserrat ExtraBold": "Montserrat",
    "Montserrat-ExtraBold": "Montserrat",
    "Montserrat Black": "Montserrat",
    "Montserrat-Black": "Montserrat",

    # Anton
    "Anton-Regular": "Anton",
    "Anton": "Anton",

    # Inter
    "Inter": "Inter",
    "Inter SemiBold": "Inter",
    "Inter-SemiBold": "Inter",
    "Inter Medium": "Inter",
    "Inter-Medium": "Inter",

    # Bangers
    "Bangers-Regular": "Bangers",
    "Bangers": "Bangers",

    # Bernoru
    "Bernoru Black Ultra Expanded": "Bernoru",
    "bernoru-blackultraexpanded": "Bernoru",
    "Bernoru": "Bernoru",

    # Horizon
    "Horizon": "Horizon",
    "Horizon Bold": "Horizon",
    "Horizon-Bold": "Horizon",
    "Horizon Outlined": "Horizon",
    "Horizon_Outlined": "Horizon",

    # Space Grotesk
    "Space Grotesk Bold": "Space Grotesk",
    "SpaceGrotesk-Bold": "Space Grotesk",
    "Space Grotesk": "Space Grotesk",

    # Cooper Hewitt
    "Cooper Hewitt": "Cooper Hewitt",
    "Cooper Hewitt Heavy": "Cooper Hewitt",
    "CooperHewitt-Heavy": "Cooper Hewitt",

    # Geist
    "Geist": "Geist",
    "Geist SemiBold": "Geist",
    "Geist-SemiBold": "Geist",

    # Impact
    "Impact": "Impact",
    "impact": "Impact",

    # Bebas Neue
    "Bebas Neue": "Bebas Neue",
    "Bebas-Neue": "Bebas Neue",
    "Bebas": "Bebas Neue",

    # Roxborough CF (Note: Metatags in this font specify family as "ø")
    "Roxborough CF": "ø",
    "Roxborough-CF": "ø",
    "Roxborough": "ø",
    "roxborough-cf-regular WebFont": "ø",

    # Playfair Display
    "Playfair Display": "Playfair Display",
    "Playfair-Display": "Playfair Display",
    "PlayfairDisplay": "Playfair Display",
    "Playfair Display Bold": "Playfair Display",
    "Playfair-Display-Bold": "Playfair Display",
    "Playfair": "Playfair Display",

    # Telegraf
    "Telegraf": "Telegraf",
    "Telegraf Regular": "Telegraf",
    "Telegraf-Regular": "Telegraf",
    "telegraf": "Telegraf",
}


def resolve_font_name(font_name: str) -> str:
    """Resolve user-facing font name to the actual fontconfig family name."""
    resolved = FONT_NAME_MAP.get(font_name, font_name)
    if resolved != font_name:
        logger.debug("Font resolve: '%s' → '%s'", font_name, resolved)
    return resolved

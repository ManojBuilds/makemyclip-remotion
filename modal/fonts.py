"""Font name resolution.

Frontend-supplied font names (often filenames like `Anton-Regular`) are mapped
to the actual font-family name registered with fontconfig inside the container.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("makemyclip.fonts")

# Map user-facing names (filename / friendly form) → fontconfig family name
FONT_NAME_MAP: dict[str, str] = {
        # Sora
    "Sora": "Sora",
    "Sora-Regular": "Sora",
    "Sora SemiBold": "Sora",
    "Sora-SemiBold": "Sora",
    "Sora Bold": "Sora",
    "Sora-Bold": "Sora",
    "Sora ExtraBold": "Sora ExtraBold",
    "Sora-ExtraBold": "Sora ExtraBold",

    # Manrope
    "Manrope": "Manrope",
    "Manrope-Regular": "Manrope",
    "Manrope Medium": "Manrope",
    "Manrope-Medium": "Manrope",
    "Manrope SemiBold": "Manrope",
    "Manrope-SemiBold": "Manrope",
    "Manrope Bold": "Manrope",
    "Manrope-Bold": "Manrope",
    "Manrope ExtraBold": "Manrope ExtraBold",
    "Manrope-ExtraBold": "Manrope ExtraBold",

    # Plus Jakarta Sans
    "Plus Jakarta Sans": "Plus Jakarta Sans",
    "PlusJakartaSans": "Plus Jakarta Sans",
    "Plus Jakarta Sans Regular": "Plus Jakarta Sans",
    "PlusJakartaSans-Regular": "Plus Jakarta Sans",
    "Plus Jakarta Sans SemiBold": "Plus Jakarta Sans",
    "PlusJakartaSans-SemiBold": "Plus Jakarta Sans",
    "Plus Jakarta Sans Bold": "Plus Jakarta Sans",
    "PlusJakartaSans-Bold": "Plus Jakarta Sans",
    "Plus Jakarta Sans ExtraBold": "Plus Jakarta Sans ExtraBold",
    "PlusJakartaSans-ExtraBold": "Plus Jakarta Sans ExtraBold",

    # DM Sans
    "DM Sans": "DM Sans",
    "DMSans": "DM Sans",
    "DM Sans Regular": "DM Sans",
    "DMSans-Regular": "DM Sans",
    "DM Sans Medium": "DM Sans",
    "DMSans-Medium": "DM Sans",
    "DM Sans SemiBold": "DM Sans",
    "DMSans-SemiBold": "DM Sans",
    "DM Sans Bold": "DM Sans",
    "DMSans-Bold": "DM Sans",

    # Archivo Black
    "Archivo Black": "Archivo Black",
    "Archivo-Black": "Archivo Black",
    "ArchivoBlack": "Archivo Black",

        # Cabin
    "Cabin": "Cabin",
    "Cabin-Regular": "Cabin",
    "Cabin Medium": "Cabin",
    "Cabin-Medium": "Cabin",
    "Cabin SemiBold": "Cabin",
    "Cabin-SemiBold": "Cabin",
    "Cabin Bold": "Cabin",
    "Cabin-Bold": "Cabin",
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
    "Montserrat SemiBold": "Montserrat SemiBold",
    "Montserrat-SemiBold": "Montserrat SemiBold",
    "Montserrat ExtraBold": "Montserrat ExtraBold",
    "Montserrat-ExtraBold": "Montserrat ExtraBold",
    "Montserrat Black": "Montserrat Black",
    "Montserrat-Black": "Montserrat Black",

    # Anton
    "Anton-Regular": "Anton",
    "Anton": "Anton",

    # Inter
    "Inter": "Inter",
    "Inter SemiBold": "Inter SemiBold",
    "Inter-SemiBold": "Inter SemiBold",
    "Inter Medium": "Inter Medium",
    "Inter-Medium": "Inter Medium",

    # Poppins
    "Poppins": "Poppins",
    "Poppins Bold": "Poppins",
    "Poppins-Bold": "Poppins",
    "Poppins ExtraBold": "Poppins ExtraBold",
    "Poppins-ExtraBold": "Poppins ExtraBold",
    "Poppins Black": "Poppins Black",
    "Poppins-Black": "Poppins Black",
    "Poppins SemiBold": "Poppins",
    "Poppins-SemiBold": "Poppins",
    "Poppins Light": "Poppins Light",
    "Poppins-Light": "Poppins Light",

    # The Bold Font
    "THE BOLD FONT": "THE BOLD FONT",
    "The Bold Font": "THE BOLD FONT",
    "TheBoldFont": "THE BOLD FONT",
    "THEBOLDFONT-FREEVERSION": "THE BOLD FONT",

    # TikTok Sans
    "TikTok Sans": "TikTok Sans",
    "TikTokSans": "TikTok Sans",
    "TikTokSans-Bold": "TikTok Sans",
    "TikTokSans-SemiBold": "TikTok Sans",
    "TikTokSans-Medium": "TikTok Sans",

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

    # Recoleta
    "Recoleta": "Recoleta",
    "recoleta": "Recoleta",
    "Recoleta Regular": "Recoleta",
    "Recoleta-Regular": "Recoleta",
    "Recoleta DEMO": "Recoleta",
    "Recoleta-DEMO": "Recoleta",
    "Recoleta Regular DEMO": "Recoleta",
    "recoleta-regulardemo": "Recoleta",
    "recoleta-regulardemo.otf": "Recoleta",
    "Recoleta-RegularDEMO": "Recoleta",
}


def resolve_font_name(font_name: str) -> str:
    """Resolve user-facing font name to the actual fontconfig family name."""
    resolved = FONT_NAME_MAP.get(font_name, font_name)
    if resolved != font_name:
        logger.debug("Font resolve: '%s' → '%s'", font_name, resolved)
    return resolved

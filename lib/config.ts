export const PLAN_LIMITS = {
  free: {
    maxDurationSeconds: 600, // 10 minutes
    label: "10 minutes",
    monthlyCreditsMinutes: 10,
  },
  creator: {
    maxDurationSeconds: 3600, // 60 minutes (1 hour)
    label: "60 minutes",
    monthlyCreditsMinutes: 600,
  },
  power: {
    maxDurationSeconds: 7200, // 120 minutes (2 hours)
    label: "2 hours",
    monthlyCreditsMinutes: 2000,
  },
} as const;

export type PlanName = keyof typeof PLAN_LIMITS;

export function getPlanLimit(planName?: string) {
  const normalized = (planName || "free").trim().toLowerCase() as PlanName;
  return PLAN_LIMITS[normalized] || PLAN_LIMITS.free;
}

export const LANGUAGES = [
  { name: "Global English", code: "en" },
  { name: "Australian English", code: "en_au" },
  { name: "British English", code: "en_uk" },
  { name: "US English", code: "en_us" },
  { name: "Spanish", code: "es" },
  { name: "French", code: "fr" },
  { name: "German", code: "de" },
  { name: "Italian", code: "it" },
  { name: "Portuguese", code: "pt" },
  { name: "Dutch", code: "nl" },
  { name: "Hindi", code: "hi" },
  { name: "Japanese", code: "ja" },
  { name: "Chinese", code: "zh" },
  { name: "Finnish", code: "fi" },
  { name: "Korean", code: "ko" },
  { name: "Polish", code: "pl" },
  { name: "Russian", code: "ru" },
  { name: "Turkish", code: "tr" },
  { name: "Ukrainian", code: "uk" },
  { name: "Vietnamese", code: "vi" },
  { name: "Afrikaans", code: "af" },
  { name: "Albanian", code: "sq" },
  { name: "Amharic", code: "am" },
  { name: "Arabic", code: "ar" },
  { name: "Armenian", code: "hy" },
  { name: "Assamese", code: "as" },
  { name: "Azerbaijani", code: "az" },
  { name: "Basque", code: "eu" },
  { name: "Belarusian", code: "be" },
  { name: "Bengali", code: "bn" },
  { name: "Bosnian", code: "bs" },
  { name: "Bulgarian", code: "bg" },
  { name: "Catalan", code: "ca" },
  { name: "Croatian", code: "hr" },
  { name: "Czech", code: "cs" },
  { name: "Danish", code: "da" },
  { name: "Estonian", code: "et" },
  { name: "Galician", code: "gl" },
  { name: "Georgian", code: "ka" },
  { name: "Greek", code: "el" },
  { name: "Gujarati", code: "gu" },
  { name: "Haitian", code: "ht" },
  { name: "Hausa", code: "ha" },
  { name: "Hawaiian", code: "haw" },
  { name: "Hebrew", code: "he" },
  { name: "Hungarian", code: "hu" },
  { name: "Icelandic", code: "is" },
  { name: "Indonesian", code: "id" },
  { name: "Javanese", code: "jw" },
  { name: "Kannada", code: "kn" },
  { name: "Kazakh", code: "kk" },
  { name: "Lao", code: "lo" },
  { name: "Latin", code: "la" },
  { name: "Latvian", code: "lv" },
  { name: "Lithuanian", code: "lt" },
  { name: "Luxembourgish", code: "lb" },
  { name: "Macedonian", code: "mk" },
  { name: "Malagasy", code: "mg" },
  { name: "Malay", code: "ms" },
  { name: "Malayalam", code: "ml" },
  { name: "Maltese", code: "mt" },
  { name: "Maori", code: "mi" },
  { name: "Marathi", code: "mr" },
  { name: "Mongolian", code: "mn" },
  { name: "Nepali", code: "ne" },
  { name: "Norwegian", code: "no" },
  { name: "Panjabi", code: "pa" },
  { name: "Pashto", code: "ps" },
  { name: "Persian", code: "fa" },
  { name: "Romanian", code: "ro" },
  { name: "Serbian", code: "sr" },
  { name: "Shona", code: "sn" },
  { name: "Sindhi", code: "sd" },
  { name: "Sinhala", code: "si" },
  { name: "Slovak", code: "sk" },
  { name: "Slovenian", code: "sl" },
  { name: "Somali", code: "so" },
  { name: "Sundanese", code: "su" },
  { name: "Swahili", code: "sw" },
  { name: "Swedish", code: "sv" },
  { name: "Tagalog", code: "tl" },
  { name: "Tajik", code: "tg" },
  { name: "Tamil", code: "ta" },
  { name: "Telugu", code: "te" },
  { name: "Urdu", code: "ur" },
  { name: "Uzbek", code: "uz" },
  { name: "Welsh", code: "cy" },
  { name: "Yiddish", code: "yi" },
  { name: "Yoruba", code: "yo" },
]

// Animated WebP preview paths from R2 (3s loops on black background)
export const PREVIEW_IMAGES: Record<string, string> = {
  simple:
    "https://pub-dab84dec13074258806f788a00943c46.r2.dev/previews/black_template_simple.webp",
  beast:
    "https://pub-dab84dec13074258806f788a00943c46.r2.dev/previews/black_template_beast.webp",
  popline:
    "https://pub-dab84dec13074258806f788a00943c46.r2.dev/previews/black_template_popline.webp",
  hormozi:
    "https://pub-dab84dec13074258806f788a00943c46.r2.dev/previews/black_template_hormozi.webp",
  "box-highlight":
    "https://pub-dab84dec13074258806f788a00943c46.r2.dev/previews/black_template_box-highlight.webp",
  "neon-glow":
    "https://pub-dab84dec13074258806f788a00943c46.r2.dev/previews/black_template_neon-glow.webp",
  opus: "https://pub-dab84dec13074258806f788a00943c46.r2.dev/previews/black_template_opus.webp",
  sticker:
    "https://pub-dab84dec13074258806f788a00943c46.r2.dev/previews/black_template_sticker.webp",
}
export type CaptionPreset =
  | "hormozi"
  | "impact"
  | "growth"
  | "coral"
  | "minimal"
  | "sticker"
  | "creator"
  | "cinema"
  | "focus"
  | "badge"
  | "neon"
  | "luxury"
  | "podcast"
  | "bobby"
  | "tom"
  | "casey"
  | "fred"
  | "sara"
  | "billy"
  | "unbox"
  | "aliabdlal"

export interface CaptionPreviewStyle {
  fontFamily: string
  italic?: boolean
  primaryColor: string
  highlightColor: string
  words: [string, string, string] | [string, string]
  activeWordIndex: number
  isUppercase?: boolean
  strokeColor?: string
  badgeBg?: string
  glowColor?: string
  hasDoubleBorder?: boolean
}

export interface CaptionTemplate {
  name: string
  preset: CaptionPreset
  wordHighlightDefault: boolean
  word_highlight?: boolean
  tag?: string
  description?: string
  preview: CaptionPreviewStyle
}

// Single source of truth — kept in sync with modal/presets.py
export const CAPTION_TEMPLATES: Record<string, CaptionTemplate> = {
  aliabdlal: {
    name: "Ali Abdaal",
    preset: "aliabdlal",
    wordHighlightDefault: true,
    tag: "Editorial",
    description: "Recoleta Serif, burnt orange highlight, slide-up animation",
    preview: {
      fontFamily: "'Recoleta', serif",
      italic: false,
      primaryColor: "#FFFFFF",
      highlightColor: "#f06c3f",
      words: ["productive", "deep", "work"],
      activeWordIndex: 1,
      isUppercase: false,
      strokeColor: "#000000",
    },
  },
  unbox: {
    name: "Unbox",
    preset: "unbox",
    wordHighlightDefault: true,
    tag: "Magenta Pill",
    description: "ALL CAPS Montserrat ExtraBold with neon magenta fuchsia active word capsule",
    preview: {
      fontFamily: "'Montserrat', sans-serif",
      italic: false,
      primaryColor: "#FFFFFF",
      highlightColor: "#FFFFFF",
      words: ["CREATE", "PRESSURE", "THAT"],
      activeWordIndex: 1,
      isUppercase: true,
      strokeColor: "#000000",
      badgeBg: "#e004fe",
    },
  },
  billy: {
    name: "Billy",
    preset: "billy",
    wordHighlightDefault: false,
    tag: "Top Purple",
    description: "Top-placed subtitle in Poppins ExtraBold with bold deep purple outline",
    preview: {
      fontFamily: "'Poppins', sans-serif",
      italic: false,
      primaryColor: "#fbfcfb",
      highlightColor: "#fbfcfb",
      words: ["when someone", "doesn't", "want"],
      activeWordIndex: 1,
      isUppercase: false,
      strokeColor: "#56417c",
    },
  },
  sara: {
    name: "Sara",
    preset: "sara",
    wordHighlightDefault: true,
    tag: "Orange Pill",
    description: "Plus Jakarta Sans ExtraBold with burnt orange capsule, black outline & 3D extrusion",
    preview: {
      fontFamily: "'Plus Jakarta Sans', sans-serif",
      italic: false,
      primaryColor: "#FFFFFF",
      highlightColor: "#FFFFFF",
      words: ["Because", "it's", "really the"],
      activeWordIndex: 1,
      isUppercase: false,
      strokeColor: "#000000",
      badgeBg: "#e13a06",
    },
  },
  fred: {
    name: "Fred",
    preset: "fred",
    wordHighlightDefault: true,
    tag: "Emerald Green",
    description: "Natural Cabin Bold with rich emerald green active word highlight and 3D black outline",
    preview: {
      fontFamily: "'Cabin', sans-serif",
      italic: false,
      primaryColor: "#FFFFFF",
      highlightColor: "#28ae67",
      words: ["Every", "time", "he's writing"],
      activeWordIndex: 1,
      isUppercase: false,
      strokeColor: "#000000",
    },
  },
  casey: {
    name: "Casey",
    preset: "casey",
    wordHighlightDefault: false,
    tag: "Orange Stroke",
    description: "ALL CAPS THE BOLD FONT with 3D electric orange outline",
    preview: {
      fontFamily: "'THE BOLD FONT', Impact, sans-serif",
      italic: false,
      primaryColor: "#FFFFFF",
      highlightColor: "#FFFFFF",
      words: ["I WANTED", "TO EXPLAIN", ""],
      activeWordIndex: 1,
      isUppercase: true,
      strokeColor: "#ed7500",
    },
  },
  tom: {
    name: "Tom",
    preset: "tom",
    wordHighlightDefault: true,
    tag: "Crimson Outline",
    description: "ALL CAPS Archivo Black with deep crimson outline and pure white fill",
    preview: {
      fontFamily: "'Archivo Black', sans-serif",
      italic: false,
      primaryColor: "#FFFFFF",
      highlightColor: "#FFFFFF",
      words: ["THE", "ROOM", "AS IF"],
      activeWordIndex: 1,
      isUppercase: true,
      strokeColor: "#a1193d",
    },
  },
  bobby: {
    name: "Bobby",
    preset: "bobby",
    wordHighlightDefault: true,
    tag: "Bobbi",
    description: "Lowercase Poppins ExtraBold with cyber yellow word highlight and black outline",
    preview: {
      fontFamily: "'Poppins', sans-serif",
      italic: false,
      primaryColor: "#fbf0d2",
      highlightColor: "#fcbb42",
      words: ["never", "laughed at", "anybody"],
      activeWordIndex: 0,
      isUppercase: false,
      strokeColor: "#000000",
    },
  },
  podcast: {
    name: "Podcast",
    preset: "podcast",
    wordHighlightDefault: false,
    tag: "Interview",
    description: "Manrope ExtraBold conversational typography for longform audio",
    preview: {
      fontFamily: "'Manrope', sans-serif",
      italic: false,
      primaryColor: "#FFFFFF",
      highlightColor: "#38BDF8",
      words: ["when I heard", "that question", ""],
      activeWordIndex: 1,
      isUppercase: false,
    },
  },
  badge: {
    name: "Badge",
    preset: "badge",
    wordHighlightDefault: true,
    tag: "Clean Card",
    description: "Modern white pill card with high-contrast spoken text",
    preview: {
      fontFamily: "'Poppins', sans-serif",
      italic: false,
      primaryColor: "#A0A0A8",
      highlightColor: "#111111",
      words: ["my top three", "ideas", ""],
      activeWordIndex: 0,
      isUppercase: false,
      badgeBg: "#FFFFFF",
    },
  },
  luxury: {
    name: "Luxury",
    preset: "luxury",
    wordHighlightDefault: false,
    tag: "Editorial",
    description: "Playfair Display with metallic gold shimmer",
    preview: {
      fontFamily: "'Playfair Display', serif",
      italic: false,
      primaryColor: "#F8FAFC",
      highlightColor: "#EAB308",
      words: ["The Art of", "Mastery", ""],
      activeWordIndex: 1,
      isUppercase: false,
    },
  },
  neon: {
    name: "Neon",
    preset: "neon",
    wordHighlightDefault: true,
    tag: "Gaming & AI",
    description: "Synthwave dual-tone cyberpunk with cyan and hot magenta neon bloom",
    preview: {
      fontFamily: "'Montserrat', sans-serif",
      italic: false,
      primaryColor: "#00FFFF",
      highlightColor: "#FF007F",
      words: ["LEVEL", "UNLOCKED", "NOW"],
      activeWordIndex: 1,
      isUppercase: true,
      glowColor: "#FF007F",
    },
  },
  focus: {
    name: "Focus",
    preset: "focus",
    wordHighlightDefault: true,
    tag: "Keynote Pill",
    description: "Rounded yellow capsule behind active word",
    preview: {
      fontFamily: "'Inter', sans-serif",
      italic: false,
      primaryColor: "#FFFFFF",
      highlightColor: "#000000",
      words: ["The one", "formula", "that works"],
      activeWordIndex: 1,
      isUppercase: false,
      badgeBg: "#FFE600",
    },
  },
  cinema: {
    name: "Cinema",
    preset: "cinema",
    wordHighlightDefault: false,
    tag: "Documentary",
    description: "Distinctive editorial serif styling with smooth opacity fade",
    preview: {
      fontFamily: "'Roxborough CF', Georgia, serif",
      italic: false,
      primaryColor: "#E2E8F0",
      highlightColor: "#FDE047",
      words: ["the story of", "freedom", ""],
      activeWordIndex: 1,
      isUppercase: false,
    },
  },
  creator: {
    name: "Creator",
    preset: "creator",
    wordHighlightDefault: true,
    tag: "YouTube Tech",
    description: "Space Grotesk, electric cyan reveal, clean tech feel",
    preview: {
      fontFamily: "'Space Grotesk', sans-serif",
      italic: false,
      primaryColor: "#FFFFFF",
      highlightColor: "#00F0FF",
      words: ["This changes", "EVERYTHING", ""],
      activeWordIndex: 1,
      isUppercase: false,
      strokeColor: "#0A0A12",
    },
  },
  minimal: {
    name: "Minimal",
    preset: "minimal",
    wordHighlightDefault: true,
    tag: "Style",
    description: "Dimmed slate gray inactive words with crisp white active word",
    preview: {
      fontFamily: "'Inter', sans-serif",
      italic: false,
      primaryColor: "#94A3B8",
      highlightColor: "#FFFFFF",
      words: ["the secret", "to focus", "daily"],
      activeWordIndex: 1,
      isUppercase: false,
      strokeColor: "#0F172A",
    },
  },
  sticker: {
    name: "Sticker",
    preset: "sticker",
    wordHighlightDefault: true,
    tag: "Double Border",
    description: "White text, black stroke with secondary white halo cutout",
    preview: {
      fontFamily: "'Montserrat', sans-serif",
      italic: false,
      primaryColor: "#FFFFFF",
      highlightColor: "#FFE600",
      words: ["REAL", "IMPACT", "NOW"],
      activeWordIndex: 1,
      isUppercase: true,
      strokeColor: "#000000",
      hasDoubleBorder: true,
    },
  },
  coral: {
    name: "Coral",
    preset: "coral",
    wordHighlightDefault: true,
    tag: "Hot Take",
    description: "Sora ExtraBold with neon coral crimson active word",
    preview: {
      fontFamily: "'Sora', sans-serif",
      italic: false,
      primaryColor: "#FFFFFF",
      highlightColor: "#FF1E56",
      words: ["STOP", "DOING", "THIS"],
      activeWordIndex: 1,
      isUppercase: true,
      strokeColor: "#000000",
    },
  },
  growth: {
    name: "Growth",
    preset: "growth",
    wordHighlightDefault: true,
    tag: "Finance & Tech",
    description: "Heavy Archivo Black, electric lime green active word",
    preview: {
      fontFamily: "'Archivo Black', sans-serif",
      italic: false,
      primaryColor: "#FFFFFF",
      highlightColor: "#00FF66",
      words: ["SCALE", "REVENUE", "FAST"],
      activeWordIndex: 1,
      isUppercase: true,
      strokeColor: "#000000",
    },
  },
  hormozi: {
    name: "Hormozi",
    preset: "hormozi",
    wordHighlightDefault: true,
    tag: "Viral #1",
    description: "Alex Hormozi signature italic with progressive golden yellow highlight",
    preview: {
      fontFamily: "'Poppins', sans-serif",
      italic: true,
      primaryColor: "#FFFFFF",
      highlightColor: "#FFB800",
      words: ["I have to", "be involved", ""],
      activeWordIndex: 0,
      isUppercase: false,
      strokeColor: "#000000",
    },
  },
  impact: {
    name: "Impact",
    preset: "impact",
    wordHighlightDefault: true,
    tag: "TikTok Classic",
    description: "Anton ALL CAPS with vibrant canary yellow active word and black outline",
    preview: {
      fontFamily: "'Anton', Impact, sans-serif",
      italic: false,
      primaryColor: "#FFFFFF",
      highlightColor: "#FFE600",
      words: ["STOP", "SCROLLING", "NOW"],
      activeWordIndex: 1,
      isUppercase: true,
      strokeColor: "#000000",
    },
  },
}

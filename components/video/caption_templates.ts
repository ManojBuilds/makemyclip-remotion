export type CaptionPreset =
  | "impact"
  | "creator"
  | "cinema"
  | "focus"
  | "neon"
  | "luxury"

export interface CaptionTemplate {
  name: string
  preset: CaptionPreset
  wordHighlightDefault: boolean
}

// Single source of truth — kept in sync with modal/presets.py
export const CAPTION_TEMPLATES: Record<string, CaptionTemplate> = {
  impact: {
    name: "Impact",
    preset: "impact",
    wordHighlightDefault: true,
  },
  creator: {
    name: "Creator",
    preset: "creator",
    wordHighlightDefault: true,
  },
  cinema: {
    name: "Cinema",
    preset: "cinema",
    wordHighlightDefault: false,
  },
  focus: {
    name: "Focus",
    preset: "focus",
    wordHighlightDefault: true,
  },
  neon: {
    name: "Neon",
    preset: "neon",
    wordHighlightDefault: true,
  },
  luxury: {
    name: "Luxury",
    preset: "luxury",
    wordHighlightDefault: false,
  },
}

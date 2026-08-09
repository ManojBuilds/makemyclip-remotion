export type CaptionPreset =
  | "impact"
  | "creator"
  | "cinema"
  | "focus"
  | "neon"

export interface CaptionTemplate {
  name: string
  preset: CaptionPreset
}

// Single source of truth — kept in sync with modal/presets.py
export const CAPTION_TEMPLATES: Record<string, CaptionTemplate> = {
  impact: {
    name: "Impact",
    preset: "impact",
  },
  creator: {
    name: "Creator",
    preset: "creator",
  },
  cinema: {
    name: "Cinema",
    preset: "cinema",
  },
  focus: {
    name: "Focus",
    preset: "focus",
  },
  neon: {
    name: "Neon",
    preset: "neon",
  },
}

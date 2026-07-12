import type { CaptionPreset } from "../captions/presets"

export interface CaptionTemplate {
  name: string
  preset: CaptionPreset
}

// Single source of truth — kept in sync with modal/presets.py
export const CAPTION_TEMPLATES: Record<string, CaptionTemplate> = {
  hormozi: {
    name: "Money Mode",
    preset: "hormozi",
  },
  beast: {
    name: "Hype Beast",
    preset: "beast",
  },
  "box-highlight": {
    name: "Clean Glow",
    preset: "box-highlight",
  },
  simple: {
    name: "Podcast Pro",
    preset: "simple",
  },
  opus: {
    name: "Viral Pop",
    preset: "opus",
  },
  popline: {
    name: "Underline It",
    preset: "popline",
  },
  "neon-glow": {
    name: "Neon Glow",
    preset: "neon-glow",
  },
  sticker: {
    name: "Sticker",
    preset: "sticker",
  },
}

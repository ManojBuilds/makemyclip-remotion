/**
 * Target ~1 quality clip per 4-5 min of content (Opus Clip / Vizard.ai standard).
 * Beyond this rate, the AI scrapes marginal moments and quality drops significantly.
 * Min/max band is kept tight — a wide band encourages filler clips.
 */
export function getTargetClipCount(durationSeconds: number): {
  min: number
  target: number
  max: number
} {
  const m = durationSeconds / 60
  if (m < 3) return { min: 1, target: 1, max: 2 }
  if (m < 5) return { min: 1, target: 2, max: 3 }
  if (m < 10) return { min: 2, target: 3, max: 4 }
  if (m < 15) return { min: 2, target: 4, max: 5 }
  if (m < 20) return { min: 3, target: 5, max: 6 }
  if (m < 30) return { min: 4, target: 6, max: 8 }
  if (m < 45) return { min: 5, target: 8, max: 10 }
  if (m < 60) return { min: 6, target: 10, max: 12 }
  if (m < 90) return { min: 8, target: 12, max: 14 }
  if (m < 150) return { min: 10, target: 15, max: 17 }
  if (m < 240) return { min: 15, target: 22, max: 26 }
  return { min: 22, target: 30, max: 35 }
  // return { min: 1, target: 1, max: 2 }
}

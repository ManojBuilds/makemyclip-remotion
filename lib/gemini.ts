import { GoogleGenAI, Type, Schema } from "@google/genai"
import type { WordTimestamp } from "@/lib/db/schema"
import { applyBoundaryGuardrails } from "./guardrails"
import { getTargetClipCount } from "./clip-utils"

const GEMINI_API_KEY = process.env.GEMINI_API_KEY

if (!GEMINI_API_KEY) {
  console.warn("⚠️  GEMINI_API_KEY is not set – clip analysis will fail.")
}

export const ai = new GoogleGenAI({ apiKey: GEMINI_API_KEY ?? "" })

export type LongFormClipType =
  | "hot_take"
  | "aha_moment"
  | "funny_exchange"
  | "debate"
  | "storytelling"
  | "quotable"
  | "emotional"
  | "mind_blowing_fact"

/**
 * reframe  — AI face-tracking (camera follows active speaker). Best for person-facing content.
 * letterbox — Pillarbox/letterbox crop, no face tracking. Best for screen content, slides, animations, or multi-person panels.
 */
export type CropMode = "reframe" | "letterbox"

export type AIClipSuggestion = {
  title: string
  hookText: string
  startTime: number
  endTime: number
  durationSeconds: number
  viralScore: number
  viralReason: string
  description: string
  hashtags: string
  clipType: LongFormClipType
  speakerDynamic: string
}

export interface VisualAudioMetrics {
  talkNetScore: number
  speechVelocityWPM: number
  speakerSwitchCount: number
  energyLabel: "High" | "Medium" | "Normal"
}

export interface Sentence {
  index: number
  text: string
  start: number
  end: number
  speaker: number | null
  visualMetrics?: VisualAudioMetrics
}

/**
 * Enriches sentence objects with Words-Per-Minute (WPM) speech velocity,
 * TalkNet audio-visual speech confidence from analysis.json, and energy labels.
 */
export function enrichSentencesWithMetrics(
  sentences: Sentence[],
  analysisJson?: any
): Sentence[] {
  if (!sentences || sentences.length === 0) return []

  const fps =
    Number(analysisJson?.fps) ||
    Number(analysisJson?.video_info?.fps) ||
    25.0
  const tracks = Array.isArray(analysisJson?.tracks) ? analysisJson.tracks : []

  return sentences.map((sent, idx) => {
    const wordCount = sent.text.trim().split(/\s+/).length
    const duration = Math.max(0.5, sent.end - sent.start)
    const wpm = Math.round((wordCount / duration) * 60)

    let maxTalkNetScore = 0.5
    if (tracks.length > 0) {
      const startFrame = Math.floor(sent.start * fps)
      const endFrame = Math.ceil(sent.end * fps)
      let foundScores: number[] = []

      for (const track of tracks) {
        const frames: number[] = track.frames || []
        const scores: number[] = track.scores || []

        for (let i = 0; i < frames.length; i++) {
          if (frames[i] >= startFrame && frames[i] <= endFrame) {
            if (typeof scores[i] === "number" && !isNaN(scores[i])) {
              foundScores.push(scores[i])
            }
          }
        }
      }

      if (foundScores.length > 0) {
        maxTalkNetScore = Math.max(...foundScores)
      }
    }

    let switches = 0
    for (let i = Math.max(0, idx - 3); i <= Math.min(sentences.length - 2, idx + 3); i++) {
      if (
        sentences[i].speaker !== null &&
        sentences[i + 1].speaker !== null &&
        sentences[i].speaker !== sentences[i + 1].speaker
      ) {
        switches++
      }
    }

    let energyLabel: "High" | "Medium" | "Normal" = "Normal"
    if (wpm >= 210 || maxTalkNetScore >= 0.75 || switches >= 2) {
      energyLabel = "High"
    } else if (wpm < 110 && maxTalkNetScore < 0.35) {
      energyLabel = "Medium"
    }

    return {
      ...sent,
      visualMetrics: {
        talkNetScore: Number(maxTalkNetScore.toFixed(2)),
        speechVelocityWPM: wpm,
        speakerSwitchCount: switches,
        energyLabel,
      },
    }
  })
}

const MIN_CLIP_SECONDS = 10
const MAX_CLIP_SECONDS = 60
// YouTube Shorts now supports clips up to 3 minutes; this cap is currently tuned for short punchy clips. Revisit deliberately if longer story-arc clips (e.g. storytelling clipType) are desired — this would need a per-clipType max rather than one global constant.

// Cooldown to avoid hitting rate-limited or unavailable models repeatedly
const modelCooldowns = new Map<string, number>()
const COOLDOWN_DURATION_MS = 5 * 60 * 1000 // 5 minutes

// Models to try in order — Pro/Flash first for best quality, then lite fallbacks.
const MODELS = [
  "gemini-3.5-flash",
  "gemini-2.5-pro",
  "gemini-2.5-flash",
  "gemini-2.0-flash",
  "gemini-3.1-flash-lite",
  "gemini-2.5-flash-lite",
  "gemini-2.0-flash-lite",
  "gemini-flash-latest",
  "gemini-flash-lite-latest",
]

const MODEL_PRIMARY = MODELS[0]


const CHUNKED_EXTRACTION_THRESHOLD_MINUTES = 25

// ─── Transcript helpers ────────────────────────────────────────────────────

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  const ms = Math.round((seconds % 1) * 100)
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}.${String(ms).padStart(2, "0")}`
}

/**
 * Groups word-level timestamps into sentence/phrase chunks using punctuation,
 * speaker changes, pauses, and a 30-word safety cap.
 */
export function groupWordsIntoSentences(words: WordTimestamp[]): Sentence[] {
  if (words.length === 0) return []

  const sentences: Sentence[] = []
  let currentWords: WordTimestamp[] = []
  let index = 1

  for (let i = 0; i < words.length; i++) {
    const word = words[i]
    const nextWord = words[i + 1]
    currentWords.push(word)

    const clean = word.word.trim()
    const isAbbr =
      /^(Mr|Ms|Mrs|Dr|St|Co|Inc|Ltd|vs|eg|ie|etc|a\.m|p\.m|U\.S|U\.K)\.?$/i.test(
        clean
      )
    const endsSentence = /[.!?]$/.test(clean) && !isAbbr
    const speakerChanged =
      nextWord?.speaker !== undefined &&
      word.speaker !== undefined &&
      nextWord.speaker !== word.speaker
    const longPause = nextWord && nextWord.start - word.end > 1.2
    const tooLong = currentWords.length >= 30
    const isLast = i === words.length - 1

    if (isLast || endsSentence || speakerChanged || longPause || tooLong) {
      sentences.push({
        index,
        text: currentWords.map((w) => w.word).join(" "),
        start: currentWords[0].start,
        end: currentWords[currentWords.length - 1].end,
        speaker: currentWords[0].speaker ?? null,
      })
      index++
      currentWords = []
    }
  }

  return sentences
}

// ─── Clip normalization ────────────────────────────────────────────────────

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v))
}

function snapToWord(
  words: WordTimestamp[],
  t: number,
  dir: "floor" | "ceil"
): number {
  if (words.length === 0) return t
  if (dir === "floor") {
    for (let i = words.length - 1; i >= 0; i--) {
      if (words[i].start <= t) return words[i].start
    }
    return words[0].start
  }
  for (let i = 0; i < words.length; i++) {
    if (words[i].end >= t) return words[i].end
  }
  return words[words.length - 1].end
}

function normalizeClip(
  clip: AIClipSuggestion,
  words: WordTimestamp[],
  totalDuration: number,
  sentences: Sentence[]
): AIClipSuggestion | null {
  const limit =
    Number.isFinite(totalDuration) && totalDuration > 0
      ? totalDuration
      : Infinity

  let s = Number.isFinite(clip.startTime) ? clip.startTime : 0
  let e = Number.isFinite(clip.endTime) ? clip.endTime : s
  if (e < s) [s, e] = [e, s]

  // Clamp then snap both ends
  const snap = (start: number, end: number) => [
    snapToWord(words, clamp(start, 0, limit), "floor"),
    snapToWord(words, clamp(end, 0, limit), "ceil"),
  ]
    ;[s, e] = snap(s, e)

  // Expand if too short using sentence boundaries to prevent mid-sentence/mid-word fragments
  let dur = e - s
  if (dur > 0 && dur < MIN_CLIP_SECONDS && Number.isFinite(limit)) {
    // Find current sentence indices
    let sIdx = sentences.findIndex((sent) => s >= sent.start && s <= sent.end)
    let eIdx = sentences.findIndex((sent) => e >= sent.start && e <= sent.end)

    if (sIdx === -1) {
      sIdx = sentences.findIndex((sent) => sent.start > s) - 1
      if (sIdx < 0) sIdx = 0
    }
    if (eIdx === -1) {
      eIdx = sentences.findIndex((sent) => sent.end > e)
      if (eIdx === -1) eIdx = sentences.length - 1
    }

    // Expand outward sentence by sentence until we hit MIN_CLIP_SECONDS or run out of sentences
    while (
      e - s < MIN_CLIP_SECONDS &&
      (sIdx > 0 || eIdx < sentences.length - 1)
    ) {
      if (
        sIdx > 0 &&
        (eIdx === sentences.length - 1 ||
          s - sentences[sIdx - 1].start < sentences[eIdx + 1].end - e)
      ) {
        sIdx--
        s = sentences[sIdx].start
      } else if (eIdx < sentences.length - 1) {
        eIdx++
        e = sentences[eIdx].end
      } else {
        break
      }
    }
    ;[s, e] = snap(s, e)
    dur = e - s
  }

  if (!Number.isFinite(dur) || dur <= 0) return null

  // Trim if too long
  if (dur > MAX_CLIP_SECONDS && Number.isFinite(limit)) {
    ;[s, e] = snap(s, s + MAX_CLIP_SECONDS)
    dur = e - s
    if (dur <= 0) return null
  }

  return { ...clip, startTime: s, endTime: e, durationSeconds: dur }
}

// ─── Deduplication pass ───────────────────────────────────────────────────

function dedupeOverlappingClips(
  clips: AIClipSuggestion[],
  maxOverlapRatio = 0.5
): AIClipSuggestion[] {
  const kept: AIClipSuggestion[] = []
  for (const clip of clips) {
    const overlapsExisting = kept.some((k) => {
      const overlapStart = Math.max(k.startTime, clip.startTime)
      const overlapEnd = Math.min(k.endTime, clip.endTime)
      const overlap = Math.max(0, overlapEnd - overlapStart)
      const shorterDur = Math.min(k.durationSeconds, clip.durationSeconds)
      return shorterDur > 0 && overlap / shorterDur > maxOverlapRatio
    })
    if (!overlapsExisting) kept.push(clip)
  }
  return kept
}

// ─── Response schema ───────────────────────────────────────────────────────

const responseSchema: Schema = {
  type: Type.ARRAY,
  items: {
    type: Type.OBJECT,
    properties: {
      keyTopicDescription: {
        type: Type.STRING,
        description:
          "Analyze the theme/argument. Explain why this range forms a semantically complete thought.",
      },
      hookEvaluation: {
        type: Type.STRING,
        description:
          "Evaluate the first sentence — why is it a scroll-stopping hook with no filler?",
      },
      resolutionEvaluation: {
        type: Type.STRING,
        description:
          "Evaluate the last sentence — how does it land as a satisfying conclusion or mic-drop?",
      },
      contextBoundaryValidation: {
        type: Type.STRING,
        description:
          "Analyze if the starting sentence (#startSentenceIndex) references any pronouns (he, she, it, that, them), jokes, or topics discussed in the preceding 3 sentences. If it does, explain why you pulled the starting boundary back to include the setup, or confirm it is a 100% clean, self-contained entrance.",
      },
      endBoundaryValidation: {
        type: Type.STRING,
        description:
          "Analyze the 3 sentences immediately following the ending sentence (#endSentenceIndex). Confirm they do not contain a punchline, laugh, reaction, or thematic conclusion that belongs to this clip. If they do, explain why you extended the clip to include them.",
      },
      startSentenceIndex: {
        type: Type.INTEGER,
        description:
          "1-indexed sentence where the clip starts. Must align with a clean hook.",
      },
      endSentenceIndex: {
        type: Type.INTEGER,
        description:
          "1-indexed sentence where the clip ends. Must be >= startSentenceIndex.",
      },
      title: {
        type: Type.STRING,
        description:
          "Curiosity-inducing social title (max 8 words) — teases without spoiling.",
      },
      hookText: {
        type: Type.STRING,
        description:
          "Bold on-screen hook caption (1–3 words) to capture attention in the first 3 seconds.",
      },
      hookStrength: {
        type: Type.INTEGER,
        description: "Score from 1 to 10 evaluating the opening sentence hook strength.",
      },
      quotability: {
        type: Type.INTEGER,
        description: "Score from 1 to 10 evaluating how memorable/shareable the quotes are.",
      },
      emotionalIntensity: {
        type: Type.INTEGER,
        description: "Score from 1 to 10 on the level of emotional response (shock, laughter, empathy, curiosity).",
      },
      standaloneClarity: {
        type: Type.INTEGER,
        description: "Score from 1 to 10 on how well this clip functions as a self-contained story/thought.",
      },
      viralReason: {
        type: Type.STRING,
        description:
          "Why this clip has viral potential — the psychological trigger.",
      },
      description: {
        type: Type.STRING,
        description:
          "A detailed and engaging description of this clip to be used as a social media caption.",
      },
      hashtags: {
        type: Type.STRING,
        description:
          "Recommended hashtags for the clip, separated by spaces (e.g. #podcast #insight #viral).",
      },
      clipType: {
        type: Type.STRING,
        enum: [
          "hot_take",
          "aha_moment",
          "funny_exchange",
          "debate",
          "storytelling",
          "quotable",
          "emotional",
          "mind_blowing_fact",
        ],
        description: "Core category that best represents this clip.",
      },
      speakerDynamic: {
        type: Type.STRING,
        description:
          "Brief description of the speaker interaction (e.g. 'Host pushes back on guest's logic').",
      },
    },
    required: [
      "keyTopicDescription",
      "hookEvaluation",
      "resolutionEvaluation",
      "contextBoundaryValidation",
      "endBoundaryValidation",
      "startSentenceIndex",
      "endSentenceIndex",
      "title",
      "hookText",
      "hookStrength",
      "quotability",
      "emotionalIntensity",
      "standaloneClarity",
      "viralReason",
      "description",
      "hashtags",
      "clipType",
      "speakerDynamic",
    ],
  },
}

// ─── Extraction Helper ────────────────────────────────────────────────────

// ─── Concurrency & Timeline Helpers ──────────────────────────────────────────

async function runWithConcurrency<T, R>(
  items: T[],
  concurrencyLimit: number,
  fn: (item: T, index: number) => Promise<R>
): Promise<PromiseSettledResult<R>[]> {
  const results: PromiseSettledResult<R>[] = new Array(items.length)
  let currentIdx = 0

  const worker = async () => {
    while (currentIdx < items.length) {
      const idx = currentIdx++
      try {
        const res = await fn(items[idx], idx)
        results[idx] = { status: "fulfilled", value: res }
      } catch (err) {
        results[idx] = { status: "rejected", reason: err }
      }
    }
  }

  const workers = Array.from(
    { length: Math.min(concurrencyLimit, items.length) },
    () => worker()
  )
  await Promise.all(workers)
  return results
}

function enforceTimelineDiversity(
  clips: AIClipSuggestion[],
  totalDuration: number,
  maxClips: number
): AIClipSuggestion[] {
  if (clips.length <= maxClips) return clips

  const early: AIClipSuggestion[] = []
  const mid: AIClipSuggestion[] = []
  const late: AIClipSuggestion[] = []

  const t1 = totalDuration / 3
  const t2 = (totalDuration * 2) / 3

  for (const clip of clips) {
    if (clip.startTime < t1) early.push(clip)
    else if (clip.startTime < t2) mid.push(clip)
    else late.push(clip)
  }

  const targetPerBucket = Math.ceil(maxClips / 3)
  const selected: AIClipSuggestion[] = []

  const takeFrom = (bucket: AIClipSuggestion[], count: number) => {
    for (const c of bucket) {
      if (selected.length >= maxClips) break
      if (!selected.includes(c)) {
        selected.push(c)
        count--
        if (count <= 0) break
      }
    }
  }

  takeFrom(early, targetPerBucket)
  takeFrom(mid, targetPerBucket)
  takeFrom(late, targetPerBucket)

  for (const c of clips) {
    if (selected.length >= maxClips) break
    if (!selected.includes(c)) selected.push(c)
  }

  return selected.sort((a, b) => b.viralScore - a.viralScore)
}

// ─── Extraction Helper ────────────────────────────────────────────────────

async function extractClipsInternal(
  sliceSentences: Sentence[],
  words: WordTimestamp[],
  globalSentences: Sentence[],
  clipCount: { min: number; target: number; max: number },
  totalDuration: number,
  videoContext?: string,
  windowLabel = ""
): Promise<AIClipSuggestion[]> {
  const formattedTranscript = sliceSentences
    .map((s, idx) => {
      const energyTag = s.visualMetrics?.energyLabel === "High" ? " [🔥 High Energy]" : ""
      const wpmTag = s.visualMetrics?.speechVelocityWPM ? ` [WPM: ${s.visualMetrics.speechVelocityWPM}]` : ""
      const scoreTag = s.visualMetrics?.talkNetScore ? ` [TalkNet: ${Math.round(s.visualMetrics.talkNetScore * 100)}%]` : ""
      return `[#${idx + 1}] [${formatTime(s.start)}]${energyTag}${wpmTag}${scoreTag} 🗣️ Speaker ${s.speaker !== null && s.speaker !== undefined ? s.speaker : "0"}: "${s.text.trim()}"`
    })
    .join("\n")

  const buildPrompt = (isRetry: boolean, isUnderTargetRetry: boolean) =>
    `
You are a world-class viral short-form content curator (TikTok, YouTube Shorts, Instagram Reels). Your goal is to extract the top ${clipCount.target} most high-performing, engaging clip candidates from this video transcript screenplay.

This works for ANY video type — podcasts, interviews, vlogs, commentary, product reviews, or long-form discussions.
${videoContext ? `\nVIDEO CONTEXT: ${videoContext}` : ""}
Total Duration: ${totalDuration.toFixed(1)}s (${(totalDuration / 60).toFixed(1)} min)
${isRetry ? (isUnderTargetRetry ? `\n⚠️ RETRY: Your previous attempt returned fewer clips than the target — look more carefully across the FULL transcript for additional distinct, high-quality moments you may have missed, especially outside the regions you already selected.\n` : `\n⚠️ RETRY: Previous attempt returned 0 clips. You MUST return at least ${clipCount.min} clip(s). Relax quality standards if needed.\n`) : ""}
OBJECTIVE: Extract exactly ${clipCount.target} clips (min ${clipCount.min}, max ${clipCount.max}) distributed across the full transcript.

VIRAL CRITERIA & EDITORIAL RULES:

1. **SCROLL-STOPPING HOOK (First 3 Seconds)**:
   - The first sentence MUST be an immediate curiosity gap, bold statement, controversial take, or engaging question.
   - REJECT clips starting with filler ("Um", "So basically", "Well", "Like I said").
   - **Multi-Modal Tags**: High-energy tags ([🔥 High Energy], high [WPM: 240+], or high [TalkNet]) mark passionate speech or key moments. Use them to locate top hooks!
   - **Pre-Context Rule**: If sentence #1 uses unexplained pronouns ("he", "she", "it", "that guy"), you MUST pull the start index back to include the setup. Starting mid-thought is invalid.

2. **HIGH-ENERGY SPEAKER DYNAMICS**:
   - Prioritize moments with **active speaker exchanges** (debates, banter, quick back-and-forth reactions) over long static monologues.
   - Look for clear emotional shifts (excitement, laughter, disagreement, realization).

3. **CLEAN MIC-DROP RESOLUTION**:
   - Every clip must conclude cleanly on a strong punchline, resolution, or mic-drop line. Never cut off mid-thought or before the natural emotional reaction ends.

4. **DURATION & DENSITY**:
   - Clip length: ${MIN_CLIP_SECONDS}–${MAX_CLIP_SECONDS} seconds.
   - Each clip must be 100% self-contained so a viewer scrolling past understands the context instantly.

TRANSCRIPT SCREENPLAY:
"""
${formattedTranscript}
"""

Return ONLY a raw JSON array matching the schema. No markdown wrapper.
`.trim()

  let lastError: unknown = null
  let isUnderTargetRetry = false

  for (let attempt = 1; attempt <= 2; attempt++) {
    const prompt = buildPrompt(attempt > 1, isUnderTargetRetry)

    for (const model of MODELS) {
      const now = Date.now()
      if (
        modelCooldowns.has(model) &&
        now - modelCooldowns.get(model)! < COOLDOWN_DURATION_MS
      ) {
        console.log(
          `[analyzeViralMoments]${windowLabel ? ` ${windowLabel}` : ""} Skipping ${model} due to recent failure (cooldown)`
        )
        continue
      }

      try {
        console.log(
          `[analyzeViralMoments]${windowLabel ? ` ${windowLabel}` : ""} Attempt ${attempt} — model: ${model}`
        )

        const response = await ai.models.generateContent({
          model,
          contents: prompt,
          config: {
            responseMimeType: "application/json",
            responseSchema,
            temperature: attempt === 1 ? 0.65 : 0.8,
          },
        })

        if (!response.text) throw new Error("Empty response from Gemini.")

        const rawClips = JSON.parse(response.text) as Array<{
          keyTopicDescription: string
          hookEvaluation: string
          resolutionEvaluation: string
          contextBoundaryValidation: string
          endBoundaryValidation: string
          startSentenceIndex: number
          endSentenceIndex: number
          title: string
          hookText: string
          hookStrength: number
          quotability: number
          emotionalIntensity: number
          standaloneClarity: number
          viralReason: string
          description: string
          hashtags: string
          clipType: LongFormClipType
          speakerDynamic: string
        }>

        if (!rawClips?.length) throw new Error("Gemini returned 0 clips.")

        const mappedClips: AIClipSuggestion[] = []

        for (const raw of rawClips) {
          const localSi = Number(raw.startSentenceIndex)
          const localEi = Number(raw.endSentenceIndex)

          if (isNaN(localSi) || isNaN(localEi)) {
            console.warn(
              `[analyzeViralMoments]${windowLabel ? ` ${windowLabel}` : ""} Invalid indices: start=${raw.startSentenceIndex}, end=${raw.endSentenceIndex}`
            )
            continue
          }

          const sliceSi = Math.max(0, Math.min(sliceSentences.length - 1, localSi - 1))
          const sliceEi = Math.max(sliceSi, Math.min(sliceSentences.length - 1, localEi - 1))

          const globalStartSent = sliceSentences[sliceSi]
          const globalEndSent = sliceSentences[sliceEi]

          const si = globalSentences.indexOf(globalStartSent)
          const ei = globalSentences.indexOf(globalEndSent)

          if (si === -1 || ei === -1) {
            console.warn(
              `[analyzeViralMoments]${windowLabel ? ` ${windowLabel}` : ""} Could not map local indices to global index list`
            )
            continue
          }

          const guarded = applyBoundaryGuardrails(
            globalSentences,
            si,
            ei,
            raw.resolutionEvaluation,
            raw.endBoundaryValidation
          )
          guarded.notes.forEach((n) => console.log(`[Boundary Guardrail] ${n}`))

          const finalSi = guarded.startIdx
          const finalEi = guarded.endIdx

          let viralReasonText = [
            `[Topic] ${raw.keyTopicDescription}`,
            `[Hook] ${raw.hookEvaluation}`,
            `[Resolution] ${raw.resolutionEvaluation}`,
            `[Start Boundary Check] ${raw.contextBoundaryValidation}`,
            `[End Boundary Check] ${raw.endBoundaryValidation}`,
            `[Viral Impact] ${raw.viralReason}`,
          ].join("\n")

          if (finalSi !== si) {
            const oldLabel = `#${si + 1}`
            const newLabel = `#${finalSi + 1}`
            viralReasonText = viralReasonText.replace(
              new RegExp(oldLabel, "g"),
              newLabel
            )
          }
          if (finalEi !== ei) {
            const oldLabel = `#${ei + 1}`
            const newLabel = `#${finalEi + 1}`
            viralReasonText = viralReasonText.replace(
              new RegExp(oldLabel, "g"),
              newLabel
            )
          }

          const globalStart = globalSentences[finalSi]
          const talkNetBonus = (globalStart?.visualMetrics?.talkNetScore ?? 0.5) * 1.0
          const wpmBonus = (globalStart?.visualMetrics?.speechVelocityWPM ?? 150) > 210 ? 0.5 : 0

          const rawHook = Number(raw.hookStrength) || 5
          const rawQuot = Number(raw.quotability) || 5
          const rawEmot = Number(raw.emotionalIntensity) || 5
          const rawClar = Number(raw.standaloneClarity) || 5
          const computedViralScore = Number(
            Math.min(
              10,
              Math.max(
                0,
                rawHook * 0.30 + rawQuot * 0.20 + rawEmot * 0.20 + rawClar * 0.15 + talkNetBonus + wpmBonus
              )
            ).toFixed(1)
          )

          mappedClips.push({
            title: raw.title,
            hookText: raw.hookText,
            startTime: globalSentences[finalSi].start,
            endTime: globalSentences[finalEi].end,
            durationSeconds: globalSentences[finalEi].end - globalSentences[finalSi].start,
            viralScore: computedViralScore,
            viralReason: viralReasonText,
            description: raw.description,
            hashtags: raw.hashtags,
            clipType: raw.clipType,
            speakerDynamic: raw.speakerDynamic,
          })
        }

        const validClips = mappedClips
          .map((clip) => normalizeClip(clip, words, totalDuration, globalSentences))
          .filter((clip): clip is AIClipSuggestion => {
            if (!clip) return false
            if (clip.endTime - clip.startTime < MIN_CLIP_SECONDS) {
              console.warn(
                `[analyzeViralMoments]${windowLabel ? ` ${windowLabel}` : ""} Discarding "${clip.title}" — too short after normalization`
              )
              return false
            }
            return true
          })

        const sortedValid = validClips.sort((a, b) => b.viralScore - a.viralScore)
        const finalClips = dedupeOverlappingClips(sortedValid)
        const droppedCount = sortedValid.length - finalClips.length
        if (droppedCount > 0) {
          console.log(
            `[analyzeViralMoments]${windowLabel ? ` ${windowLabel}` : ""} Dedupe removed ${droppedCount} duplicate clips.`
          )
        }

        if (finalClips.length === 0)
          throw new Error("All clips invalid after normalization.")

        // Soft-threshold check
        const targetThreshold = Math.round(clipCount.target * 0.7)
        if (finalClips.length < targetThreshold) {
          const warningMsg = `Got ${finalClips.length} clips, target was ${clipCount.target} (min acceptable: ${targetThreshold})`
          console.warn(`[analyzeViralMoments]${windowLabel ? ` ${windowLabel}` : ""} ${warningMsg}`)
          if (attempt === 1) {
            isUnderTargetRetry = true
            throw new Error(warningMsg)
          }
        }

        if (finalClips.length < clipCount.min)
          throw new Error(
            `Only ${finalClips.length} valid clip(s) (min: ${clipCount.min}).`
          )

        console.log(
          `[analyzeViralMoments]${windowLabel ? ` ${windowLabel}` : ""} ✅ ${finalClips.length} clips from ${model}`
        )
        return finalClips
      } catch (err) {
        lastError = err
        const msg = err instanceof Error ? err.message : String(err)
        console.warn(
          `⚠️ [analyzeViralMoments]${windowLabel ? ` ${windowLabel}` : ""} Attempt ${attempt}, ${model}: ${msg}`
        )
        if (
          msg.includes("429") ||
          msg.includes("503") ||
          msg.includes("RESOURCE_EXHAUSTED") ||
          msg.includes("UNAVAILABLE") ||
          msg.includes("quota")
        ) {
          console.log(
            `[analyzeViralMoments]${windowLabel ? ` ${windowLabel}` : ""} Putting ${model} on cooldown for 5 minutes.`
          )
          modelCooldowns.set(model, Date.now())
        }
        await new Promise((r) => setTimeout(r, 1000))
      }
    }
  }

  throw lastError || new Error("Failed to extract clips")
}

export async function enrichAssemblyAIClipsWithGemini(
  rawViralClips: any[],
  words: WordTimestamp[]
): Promise<AIClipSuggestion[]> {
  try {
    const candidateSummaries = rawViralClips.map((c: any, i: number) => {
      const s = c.startTime !== undefined ? Number(c.startTime) : (Number(c.start_ms || 0) / 1000.0)
      const e = c.endTime !== undefined ? Number(c.endTime) : (Number(c.end_ms || 0) / 1000.0)
      const cWords = words.filter((w) => w.start >= s && w.end <= e).map((w) => w.word).join(" ")
      return `Clip ${i + 1} (${s.toFixed(1)}s - ${e.toFixed(1)}s):\nHeadline: ${c.headline || c.summary || ""}\nTranscript: ${cWords.slice(0, 600)}`
    }).join("\n\n")

    const prompt = `You are an expert social media editor for TikTok, IG Reels, and YouTube Shorts.
Analyze these pre-extracted viral video clip candidates and return a JSON object matching the schema.
For each candidate clip, generate:
- title: Short, curiosity-inducing clickbait title (max 7 words)
- hookText: Bold 1-3 word scroll-stopping caption for the first 3 seconds
- viralReason: 1 sentence explaining why this clip will go viral
- description: Engaging social media post description
- hashtags: Top 5 space-separated hashtags (e.g. #shorts #viral)
- clipType: one of ["hot_take", "funny_exchange", "quotable", "debate", "aha_moment"]

Candidates:
${candidateSummaries}`

    const enrichmentSchema: Schema = {
      type: Type.OBJECT,
      properties: {
        clips: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              title: { type: Type.STRING },
              hookText: { type: Type.STRING },
              viralReason: { type: Type.STRING },
              description: { type: Type.STRING },
              hashtags: { type: Type.STRING },
              clipType: { type: Type.STRING },
            },
          },
        },
      },
    }

    const response = await ai.models.generateContent({
      model: MODEL_PRIMARY,
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: enrichmentSchema,
        temperature: 0.4,
      },
    })

    const text = response.text
    if (text) {
      const parsed = JSON.parse(text)
      const suggestions: AIClipSuggestion[] = parsed.clips || (Array.isArray(parsed) ? parsed : [])
      if (Array.isArray(suggestions) && suggestions.length > 0) {
        return rawViralClips.map((c: any, i: number) => {
          const gem = suggestions[i] || {}
          const startSec = c.startTime !== undefined ? Number(c.startTime) : (Number(c.start_ms || 0) / 1000.0)
          const endSec = c.endTime !== undefined ? Number(c.endTime) : (Number(c.end_ms || 0) / 1000.0)
          const durSec = Number(c.duration_seconds || (endSec - startSec))
          const rawScore = Number(c.viral_score || c.viralScore || 85.0)
          const normalizedScore = Number(Math.min(10.0, Math.max(1.0, rawScore > 10 ? rawScore / 10.0 : rawScore)).toFixed(1))

          return {
            title: gem.title || c.headline || "Viral Short Highlight",
            hookText: gem.hookText || c.hook_quote || "Watch this",
            startTime: startSec,
            endTime: endSec,
            durationSeconds: durSec,
            viralScore: gem.viralScore || normalizedScore,
            viralReason: gem.viralReason || c.signals?.pacing_note || "High viral potential.",
            description: gem.description || c.summary || "Featured viral short clip.",
            hashtags: gem.hashtags || "#shorts #viral",
            clipType: (gem.clipType || c.clipType || "hot_take") as LongFormClipType,
            speakerDynamic: gem.speakerDynamic || c.signals?.pacing_note || "Speaker exchange",
          }
        })
      }
    }
  } catch (err) {
    console.warn(`[enrichAssemblyAIClipsWithGemini] Gemini enrichment failed, using AssemblyAI defaults:`, err)
  }

  return rawViralClips.map((c: any) => {
    const startSec = c.startTime !== undefined ? Number(c.startTime) : (Number(c.start_ms || 0) / 1000.0)
    const endSec = c.endTime !== undefined ? Number(c.endTime) : (Number(c.end_ms || 0) / 1000.0)
    const durSec = Number(c.duration_seconds || (endSec - startSec))
    const rawScore = Number(c.viral_score || c.viralScore || 85.0)
    const normalizedScore = Number(Math.min(10.0, Math.max(1.0, rawScore > 10 ? rawScore / 10.0 : rawScore)).toFixed(1))
    return {
      title: c.headline || c.title || "Viral Short Highlight",
      hookText: c.hook_quote || c.hookText || "Watch this",
      startTime: startSec,
      endTime: endSec,
      durationSeconds: durSec,
      viralScore: normalizedScore,
      viralReason: c.signals?.pacing_note || c.viralReason || "High viral potential.",
      description: c.summary || c.headline || "Featured viral short clip.",
      hashtags: "#shorts #viral",
      clipType: "hot_take" as LongFormClipType,
      speakerDynamic: c.signals?.pacing_note || "Speaker exchange",
    }
  })
}

// ─── Main export ───────────────────────────────────────────────────────────

/**
 * Analyzes a transcript and returns ranked viral clip suggestions.
 * Exclusively relies on candidate clip boundaries and uses Gemini solely for metadata enrichment.
 */
export async function analyzeViralMoments(
  fullText: string,
  words: WordTimestamp[],
  videoContext?: string,
  analysisJson?: any,
  preScoredViralClips?: any[]
): Promise<AIClipSuggestion[]> {
  let rawViralClips = preScoredViralClips || analysisJson?.viralClips

  if (!Array.isArray(rawViralClips) || rawViralClips.length === 0) {
    if (words && words.length > 0) {
      console.log(`[analyzeViralMoments] No pre-scored AssemblyAI viral clips found. Constructing candidate clip windows...`)
      const totalDuration = words[words.length - 1].end - words[0].start
      const clipLengthSec = 35
      const candidateList: any[] = []
      let currStart = words[0].start

      while (currStart < totalDuration - 10 && candidateList.length < 8) {
        const currEnd = Math.min(currStart + clipLengthSec, words[words.length - 1].end)
        if (currEnd - currStart >= 10) {
          candidateList.push({
            startTime: currStart,
            endTime: currEnd,
            duration_seconds: currEnd - currStart,
            viral_score: 85,
            headline: "Viral Short Highlight",
          })
        }
        currStart += clipLengthSec - 5
      }
      rawViralClips = candidateList
    } else {
      return []
    }
  }

  console.log(`[analyzeViralMoments] Using ONLY Gemini metadata enrichment for ${rawViralClips.length} candidate clips...`)
  const enriched = await enrichAssemblyAIClipsWithGemini(rawViralClips, words)
  return enriched.sort((a, b) => b.viralScore - a.viralScore)
}


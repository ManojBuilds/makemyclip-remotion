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
  clipType: LongFormClipType
  speakerDynamic: string
  cropMode?: "reframe" | "letterbox" | "split" | "course" | "auto"
}

export interface Sentence {
  index: number
  text: string
  start: number
  end: number
  speaker: number | null
}

const MIN_CLIP_SECONDS = 10
const MAX_CLIP_SECONDS = 60

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
      viralScore: {
        type: Type.INTEGER,
        description:
          "Predicted virality 1–100 based on emotional resonance, debate, or educational value.",
      },
      viralReason: {
        type: Type.STRING,
        description:
          "Why this clip has viral potential — the psychological trigger.",
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
      "viralScore",
      "viralReason",
      "clipType",
      "speakerDynamic",
    ],
  },
}

// ─── Main export ───────────────────────────────────────────────────────────

/**
 * Analyzes a transcript and returns ranked viral clip suggestions.
 */
export async function analyzeViralMoments(
  fullText: string,
  words: WordTimestamp[],
  videoContext?: string
): Promise<AIClipSuggestion[]> {
  const sentences = groupWordsIntoSentences(words)
  const totalDuration =
    words.length > 0 ? words[words.length - 1].end - words[0].start : 0
  const clipCount = getTargetClipCount(totalDuration)

  console.log(
    `[analyzeViralMoments] Duration: ${totalDuration.toFixed(1)}s | Sentences: ${sentences.length} | Target clips: ${clipCount.target}`
  )

  const formattedTranscript = sentences
    .map(
      (s) =>
        `[#${s.index}] [${formatTime(s.start)} / ${s.start.toFixed(2)}s] Speaker ${s.speaker ?? "?"}: ${s.text}`
    )
    .join("\n")

  const buildPrompt = (isRetry: boolean) =>
    `
You are an expert short-form video editor. Your job is to scan a video transcript and extract the most engaging, shareable clips optimized for TikTok, YouTube Shorts, and Instagram Reels.

This works for ANY video type — podcasts, interviews, tutorials, vlogs, lectures, commentary, product reviews, or any spoken content.
${videoContext ? `\nVIDEO CONTEXT: ${videoContext}` : ""}
Total Duration: ${totalDuration.toFixed(1)}s (${(totalDuration / 60).toFixed(1)} min)
${isRetry ? `\n⚠️ RETRY: Previous attempt returned 0 clips. You MUST return at least ${clipCount.min} clip(s). Relax quality standards if needed.\n` : ""}
OBJECTIVE: Extract exactly ${clipCount.target} clips (min ${clipCount.min}, max ${clipCount.max}) distributed across the full transcript.

EDITORIAL RULES FOR BOUNDARIES & QUALITY:
1. **Complete thought**: Every clip must stand alone — it needs a clear beginning (hook/setup), middle (development), and end (conclusion, payoff, or mic-drop). Never cut off mid-idea.
2. **Never Cut Off Setup & Pre-Context (Pre-Context Rule)**:
   - If the starting sentence refers to something, someone, or an event mentioned immediately prior (e.g., using pronouns like "he", "she", "it", "that", "them", or referring to "the Hulk", "that joke"), you MUST pull the starting sentence back to the beginning of the setup or question. Starting mid-topic is a failure.
3. **Handle Fumbles & False Starts Intentionally (Comedy Setup Rule)**:
   - In podcasts/interviews, if a speaker fumbles a joke, says "cut that shit", "I said it backwards", or has a false start, do not start the clip AFTER the fumble if it leaves a confusing/awkward fragment of the recovery. Either include the entire fumble/recovery sequence (which is highly engaging and funny), or start BEFORE the setup began.
4. **Capture the Full Mic-Drop/Resolution (Resolution Rule)**:
   - Never end a clip right before a satisfying final reaction, laugh, or punchline. Check the subsequent sentences: if they contain a strong, natural concluding statement or a hilarious reaction that wraps up the topic (e.g. "the middle finger brings out the best in people" and the follow-up examples like Curtis Blades), you MUST include them by extending the endSentenceIndex to cover that payload fully.
   - **Energy Honesty**: Be accurate about the energy level. Do not exaggerate or label a quiet, awkward, or ambiguous ending line as a "mic-drop" or "high-energy payoff" in the viralReason description. If the payoff is a quiet/awkward button, describe it as a quiet/awkward payoff.
5. **Clean Sentence Entrances & Unanswered Questions**:
   - Ensure the starting sentence is a grammatically clean entrance. Do not start on a prompt question if the guest immediately deflects it, cuts it off, or asks to switch characters. If the question goes unanswered, do NOT use it as the starting sentence or claim it as the hook — start instead directly on the deflection/character switch sentence.
6. **Duration**: ${MIN_CLIP_SECONDS}–${MAX_CLIP_SECONDS} seconds. If the core idea is short, expand the range to include the setup and payoff.
7. **Boundaries**: Start and end exactly on sentence boundaries from the transcript.
8. **Spread**: Distribute clips across the full video — don't cluster them all in the first or last 10 minutes.
9. **Clip types to look for** (not exhaustive — use your judgment):
   - A surprising or controversial opinion
   - A relatable insight or "aha" moment  
   - A compelling story or anecdote
   - A shocking statistic or fact
   - Emotional vulnerability or honest admission
   - A clear, quotable one-liner
   - Debate, disagreement, or pushback
   - A step-by-step explanation of something valuable
   
TRANSCRIPT:
"""
${formattedTranscript}
"""

Return ONLY a raw JSON array matching the schema. No markdown wrapper.
`.trim()

  let lastError: unknown = null

  for (let attempt = 1; attempt <= 2; attempt++) {
    const prompt = buildPrompt(attempt > 1)

    for (const model of MODELS) {
      const now = Date.now()
      if (
        modelCooldowns.has(model) &&
        now - modelCooldowns.get(model)! < COOLDOWN_DURATION_MS
      ) {
        console.log(
          `[analyzeViralMoments] Skipping ${model} due to recent failure (cooldown)`
        )
        continue
      }

      try {
        console.log(
          `[analyzeViralMoments] Attempt ${attempt} — model: ${model}`
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
          viralScore: number
          viralReason: string
          clipType: LongFormClipType
          speakerDynamic: string
        }>

        if (!rawClips?.length) throw new Error("Gemini returned 0 clips.")

        const mappedClips: AIClipSuggestion[] = []

        for (const raw of rawClips) {
          const sIdx = Number(raw.startSentenceIndex)
          const eIdx = Number(raw.endSentenceIndex)

          if (isNaN(sIdx) || isNaN(eIdx)) {
            console.warn(
              `[analyzeViralMoments] Invalid indices: start=${raw.startSentenceIndex}, end=${raw.endSentenceIndex}`
            )
            continue
          }

          const si = Math.max(0, Math.min(sentences.length - 1, sIdx - 1))
          const ei = Math.max(si, Math.min(sentences.length - 1, eIdx - 1))

          const guarded = applyBoundaryGuardrails(
            sentences,
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

          mappedClips.push({
            title: raw.title,
            hookText: raw.hookText,
            startTime: sentences[finalSi].start,
            endTime: sentences[finalEi].end,
            durationSeconds: sentences[finalEi].end - sentences[finalSi].start,
            viralScore: raw.viralScore,
            viralReason: viralReasonText,
            clipType: raw.clipType,
            speakerDynamic: raw.speakerDynamic,
          })
        }

        const validClips = mappedClips
          .map((clip) => normalizeClip(clip, words, totalDuration, sentences))
          .filter((clip): clip is AIClipSuggestion => {
            if (!clip) return false
            if (clip.endTime - clip.startTime < MIN_CLIP_SECONDS) {
              console.warn(
                `[analyzeViralMoments] Discarding "${clip.title}" — too short after normalization`
              )
              return false
            }
            return true
          })

        const finalClips = validClips

        if (finalClips.length === 0)
          throw new Error("All clips invalid after normalization.")
        if (finalClips.length < clipCount.min)
          throw new Error(
            `Only ${finalClips.length} valid clip(s) (min: ${clipCount.min}).`
          )

        console.log(
          `[analyzeViralMoments] ✅ ${finalClips.length} clips from ${model}`
        )
        return finalClips.sort((a, b) => b.viralScore - a.viralScore)
      } catch (err) {
        lastError = err
        const msg = err instanceof Error ? err.message : String(err)
        console.warn(
          `⚠️ [analyzeViralMoments] Attempt ${attempt}, ${model}: ${msg}`
        )
        // If rate limited or unavailable, put on cooldown
        if (
          msg.includes("429") ||
          msg.includes("503") ||
          msg.includes("RESOURCE_EXHAUSTED") ||
          msg.includes("UNAVAILABLE") ||
          msg.includes("quota")
        ) {
          console.log(
            `[analyzeViralMoments] Putting ${model} on cooldown for 5 minutes.`
          )
          modelCooldowns.set(model, Date.now())
        }
        await new Promise((r) => setTimeout(r, 1000))
      }
    }
  }

  // Last-resort fallback: return the whole video as a single clip
  console.warn(
    "⚠️ [analyzeViralMoments] All attempts failed. Returning fallback clip. Error:",
    lastError
  )

  const s = words[0]?.start ?? 0
  const e = words[words.length - 1]?.end ?? 60

  return [
    {
      title: "Featured Highlight",
      hookText: "You need to see this",
      startTime: s,
      endTime: e,
      durationSeconds: Math.max(0, e - s),
      viralScore: 75,
      viralReason: "Covers the key segment of the video.",
      clipType: "aha_moment",
      speakerDynamic: "Key takeaway from the video.",
    },
  ]
}

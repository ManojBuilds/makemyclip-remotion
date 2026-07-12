import { DeepgramClient } from "@deepgram/sdk"
import type { WordTimestamp } from "@/lib/db/schema"

// ─────────────────────────────────────────────
// Deepgram client (singleton)
// ─────────────────────────────────────────────

const DEEPGRAM_API_KEY = process.env.DEEPGRAM_API_KEY

if (!DEEPGRAM_API_KEY) {
  console.warn("⚠️  DEEPGRAM_API_KEY is not set – transcription will fail.")
}

export const deepgram = new DeepgramClient({ apiKey: DEEPGRAM_API_KEY ?? "" })

// ─────────────────────────────────────────────
// Transcription helper
// ─────────────────────────────────────────────

export type TranscriptionResult = {
  fullText: string
  words: WordTimestamp[]
  paragraphs: string[]
}

/**
 * Transcribe a remote audio/video file via Deepgram Nova-3.
 *
 * @param audioUrl  A publicly-accessible (or presigned) URL to the media file.
 * @returns         Parsed transcription with full text, word-level timestamps,
 *                  and paragraph-level segments.
 */
export async function transcribeFromUrl(
  audioUrl: string
): Promise<TranscriptionResult> {
  let response
  try {
    response = await deepgram.listen.v1.media.transcribeUrl({
      url: audioUrl,
      model: "nova-3",
      smart_format: true,
      paragraphs: true,
      diarize: true,
      language: "en",
    })
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error)
    throw new Error(`Deepgram transcription failed: ${message}`)
  }

  if (!("results" in response)) {
    throw new Error(
      "Deepgram returned an accepted response instead of results."
    )
  }

  // ── Extract the primary alternative ──────────────────────
  const results = response.results as unknown as {
    channels?: {
      alternatives?: {
        transcript?: string
        words?: unknown[]
        paragraphs?: { paragraphs?: unknown[] }
      }[]
    }[]
    paragraphs?: unknown[]
  }
  const channel = results?.channels?.[0]
  const alternative = channel?.alternatives?.[0]

  if (!alternative) {
    throw new Error("Deepgram returned no transcription alternatives.")
  }

  // ── Full text ────────────────────────────────────────────
  const fullText = alternative.transcript ?? ""

  // ── Word-level timestamps ────────────────────────────────
  const words: WordTimestamp[] = (
    (alternative.words ?? []) as {
      word: string
      punctuated_word?: string
      start: number
      end: number
      confidence: number
      speaker?: number
    }[]
  ).map((w) => ({
    word: w.punctuated_word ?? w.word,
    start: w.start,
    end: w.end,
    confidence: w.confidence,
    speaker: w.speaker,
  }))

  // ── Paragraphs ───────────────────────────────────────────
  const paragraphs: string[] = []
  const paragraphData = (alternative.paragraphs?.paragraphs ??
    results?.paragraphs) as { sentences?: { text: string }[] }[] | undefined

  if (Array.isArray(paragraphData)) {
    for (const para of paragraphData) {
      // Each paragraph has `sentences` which each have `text`
      if (para.sentences && Array.isArray(para.sentences)) {
        const paraText = para.sentences.map((s) => s.text).join(" ")
        if (paraText) paragraphs.push(paraText)
      }
    }
  }

  // Fallback: if no structured paragraphs, split on double newlines
  if (paragraphs.length === 0 && fullText) {
    paragraphs.push(
      ...fullText
        .split(/\n\n+/)
        .map((p: string) => p.trim())
        .filter(Boolean)
    )
  }

  return { fullText, words, paragraphs }
}

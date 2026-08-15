import type { WordTimestamp } from "@/lib/db/schema"

export type TranscriptionResult = {
  fullText: string
  words: WordTimestamp[]
  paragraphs: string[]
  sentiments?: any[]
  chapters?: any[]
  highlights?: any[]
  viralClips?: any[]
}

/**
 * Transcribe a remote video/audio URL or YouTube link using AssemblyAI via Modal.
 *
 * @param audioUrl  A publicly-accessible (or presigned) R2 URL or a YouTube link.
 * @returns         Parsed transcription with full text, word-level timestamps, paragraphs, AssemblyAI audio intelligence, and pre-scored viral short clips.
 */
export async function transcribeFromUrl(
  audioUrl: string,
  transcribeLanguage?: string,
  translateLanguage?: string
): Promise<TranscriptionResult> {
  const modalUrl = process.env.MODAL_TRANSCRIBE_ENDPOINT
  if (!modalUrl) {
    throw new Error(
      "⚠️ MODAL_TRANSCRIBE_ENDPOINT is not configured in the environment variables."
    )
  }

  console.log(
    `[AssemblyAI] Initiating transcription via Modal worker: ${modalUrl} (lang=${transcribeLanguage}, translate=${translateLanguage})`
  )

  try {
    const response = await fetch(modalUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        video_url: audioUrl,
        transcribe_language: transcribeLanguage || "auto",
        translate_language: translateLanguage || "none",
      }),
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(
        `Modal transcriber failed with status ${response.status}: ${errorText}`
      )
    }

    const data = await response.json()

    // Support standard FastAPI success or direct mapping
    if (data.success === false) {
      throw new Error(
        data.error || "Modal transcriber returned unsuccessful response."
      )
    }

    console.log(`[AssemblyAI] Transcription completed successfully via Modal.`)
    return {
      fullText: data.fullText,
      words: data.words,
      paragraphs: data.paragraphs,
      sentiments: data.sentiments,
      chapters: data.chapters,
      highlights: data.highlights,
      viralClips: data.viralClips,
    }
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error)
    throw new Error(`AssemblyAI transcription failed: ${message}`)
  }
}

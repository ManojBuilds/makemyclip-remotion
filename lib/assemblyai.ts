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
 * Submit transcription job to AssemblyAI via Modal (asynchronous, non-blocking).
 * Takes ~5-20 seconds to download/prepare audio and returns transcriptId immediately.
 */
export async function submitTranscription(
  audioUrl: string,
  transcribeLanguage?: string,
  translateLanguage?: string
): Promise<{ transcriptId: string; status: string }> {
  const modalUrl = process.env.MODAL_TRANSCRIBE_ENDPOINT
  if (!modalUrl) {
    throw new Error(
      "⚠️ MODAL_TRANSCRIBE_ENDPOINT is not configured in the environment variables."
    )
  }

  console.log(
    `[AssemblyAI] Submitting transcription job via Modal worker: ${modalUrl} (lang=${transcribeLanguage}, translate=${translateLanguage})`
  )

  const response = await fetch(modalUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      video_url: audioUrl,
      submit_only: true,
      transcribe_language: transcribeLanguage || "auto",
      translate_language: translateLanguage || "none",
    }),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(
      `Modal submit_transcription failed with status ${response.status}: ${errorText}`
    )
  }

  const data = await response.json()
  if (data.success === false || !data.transcript_id) {
    throw new Error(
      data.error || "Modal transcriber failed to return transcript_id."
    )
  }

  console.log(
    `[AssemblyAI] Transcription job submitted successfully. Transcript ID: ${data.transcript_id} (status: ${data.status})`
  )
  return {
    transcriptId: data.transcript_id,
    status: data.status,
  }
}

/**
 * Check the status of an AssemblyAI transcription directly via REST API.
 * Takes ~100-200ms.
 */
export async function getAssemblyAiStatus(
  transcriptId: string
): Promise<{ status: "queued" | "processing" | "completed" | "error"; error?: string }> {
  const apiKey = process.env.ASSEMBLYAI_API_KEY
  if (!apiKey) {
    throw new Error("⚠️ ASSEMBLYAI_API_KEY is not configured.")
  }

  const response = await fetch(
    `https://api.assemblyai.com/v2/transcript/${transcriptId}`,
    {
      method: "GET",
      headers: {
        authorization: apiKey,
      },
    }
  )

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(
      `AssemblyAI status poll failed with status ${response.status}: ${errorText}`
    )
  }

  const data = await response.json()
  return {
    status: data.status,
    error: data.error,
  }
}

/**
 * Once AssemblyAI is completed, enrich the transcript with speech velocity,
 * acoustic events, viral scoring, and Gemini metadata via Modal.
 * Takes ~5-15 seconds.
 */
export async function enrichTranscript(
  transcriptId: string,
  translateLanguage?: string
): Promise<TranscriptionResult> {
  const modalUrl = process.env.MODAL_TRANSCRIBE_ENDPOINT
  if (!modalUrl) {
    throw new Error(
      "⚠️ MODAL_TRANSCRIBE_ENDPOINT is not configured in the environment variables."
    )
  }

  console.log(
    `[AssemblyAI] Enriching completed transcript ${transcriptId} via Modal worker: ${modalUrl}`
  )

  const response = await fetch(modalUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      transcript_id: transcriptId,
      translate_language: translateLanguage || "none",
    }),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(
      `Modal enrich_transcript failed with status ${response.status}: ${errorText}`
    )
  }

  const data = await response.json()
  if (data.success === false) {
    throw new Error(
      data.error || "Modal transcriber returned unsuccessful response for enrichment."
    )
  }

  console.log(
    `[AssemblyAI] Transcript enriched successfully. Length: ${data.fullText?.length ?? 0}, Clips: ${data.viralClips?.length ?? 0}`
  )
  return {
    fullText: data.fullText,
    words: data.words,
    paragraphs: data.paragraphs,
    sentiments: data.sentiments,
    chapters: data.chapters,
    highlights: data.highlights,
    viralClips: data.viralClips,
  }
}

/**
 * Transcribe a remote video/audio URL or YouTube link using AssemblyAI via Modal.
 * Monolithic fallback method.
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

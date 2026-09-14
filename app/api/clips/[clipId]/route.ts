import { NextResponse } from "next/server"
import { getServerSession } from "@/lib/auth-server"
import { db } from "@/lib/db"
import { clips, transcriptions, WordTimestamp } from "@/lib/db/schema"
import { eq } from "drizzle-orm"
import { inngest } from "@/lib/inngest/client"
import { createId } from "@paralleldrive/cuid2"

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ clipId: string }> }
) {
  try {
    const session = await getServerSession()
    if (!session) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const { clipId } = await params
    const body = await request.json()

    const [clip] = await db.select().from(clips).where(eq(clips.id, clipId))

    if (!clip) {
      return NextResponse.json({ error: "Clip not found" }, { status: 404 })
    }

    const hasStyleChanged =
      (body.captionStyle !== undefined &&
        body.captionStyle !== clip.captionStyle) ||
      (body.wordHighlight !== undefined &&
        body.wordHighlight !== clip.wordHighlight)

    const hasTimeChanged =
      (body.startTime !== undefined && Number(body.startTime) !== clip.startTime) ||
      (body.endTime !== undefined && Number(body.endTime) !== clip.endTime)

    const newStartTime =
      body.startTime !== undefined ? Number(body.startTime) : clip.startTime
    const newEndTime =
      body.endTime !== undefined ? Number(body.endTime) : clip.endTime

    if (hasTimeChanged && newEndTime <= newStartTime + 0.5) {
      return NextResponse.json(
        { error: "Clip duration must be at least 0.5 seconds" },
        { status: 400 }
      )
    }

    const hasCaptionsChanged =
      body.captions !== undefined &&
      Array.isArray(body.captions) &&
      JSON.stringify(body.captions) !== JSON.stringify(clip.captions)

    const updateData: Partial<typeof clips.$inferInsert> = {
      title: body.title !== undefined ? body.title : clip.title,
      captionStyle:
        body.captionStyle !== undefined ? body.captionStyle : clip.captionStyle,
      wordHighlight:
        body.wordHighlight !== undefined ? Boolean(body.wordHighlight) : clip.wordHighlight,
      updatedAt: new Date(),
    }

    const normalizeCaptions = (captionsList: any[]) => {
      const clipCropLayout =
        clip.cropMode && clip.cropMode !== "auto" ? clip.cropMode : undefined
      const existingLayout =
        (clip.captions?.[0] as any)?.layout ||
        (clip.captions?.[0]?.words?.[0] as any)?.layout ||
        clipCropLayout

      return captionsList.map((block: any) => {
        const blockLayout = block.layout || existingLayout
        const words = Array.isArray(block.words)
          ? block.words.map((w: any) => ({
              word: String(w.word || "").replace(/[.,!?]$/, "").toLowerCase(),
              punctuated_word: String(w.punctuated_word || w.word || ""),
              start: Number(w.start) || 0,
              end: Number(w.end) || 0,
              confidence: Number(w.confidence) || 0.99,
              speaker: w.speaker?.toString() || "0",
              layout: w.layout || blockLayout,
            }))
          : []
        const transcriptText = words.map((w: any) => w.punctuated_word).join(" ")
        return {
          id: block.id || createId(),
          transcript: transcriptText || block.transcript || "",
          start: words.length > 0 ? words[0].start : (Number(block.start) || 0),
          end: words.length > 0 ? words[words.length - 1].end : (Number(block.end) || 0),
          confidence: Number(block.confidence) || 0.99,
          channel: Number(block.channel) || 0,
          layout: blockLayout || words[0]?.layout,
          words,
        }
      })
    }

    if (hasTimeChanged) {
      updateData.startTime = newStartTime
      updateData.endTime = newEndTime

      if (hasCaptionsChanged) {
        // User provided custom edited captions for the new time window
        const normalized = normalizeCaptions(body.captions)
        const trimOffset = Math.max(0, newStartTime - clip.startTime)
        const trimmedDuration = Math.max(0.5, newEndTime - newStartTime)

        if (trimOffset > 0 || newEndTime < clip.endTime) {
          // Slice and re-base words relative to trimmed start
          const slicedCaptions = normalized.map((block: any) => {
            const words = block.words
              .filter((w: any) => w.end >= trimOffset && w.start <= trimOffset + trimmedDuration)
              .map((w: any) => ({
                ...w,
                start: Math.max(0, Number((w.start - trimOffset).toFixed(2))),
                end: Math.max(0, Number((w.end - trimOffset).toFixed(2))),
              }))
            return {
              ...block,
              start: words.length > 0 ? words[0].start : 0,
              end: words.length > 0 ? words[words.length - 1].end : trimmedDuration,
              transcript: words.map((w: any) => w.punctuated_word).join(" "),
              words,
            }
          })
          updateData.captions = slicedCaptions as any
        } else {
          updateData.captions = normalized as any
        }
      } else {
        // Slice transcript words for the newly trimmed time range
        const [transcriptionRecord] = await db
          .select()
          .from(transcriptions)
          .where(eq(transcriptions.projectId, clip.projectId))
          .limit(1)

        const defaultLayout =
          (clip.cropMode && clip.cropMode !== "auto" ? clip.cropMode : undefined) ||
          (clip.captions?.[0] as any)?.layout ||
          (clip.captions?.[0]?.words?.[0] as any)?.layout

        if (transcriptionRecord?.words && Array.isArray(transcriptionRecord.words)) {
          const clipWords = (transcriptionRecord.words as WordTimestamp[])
            .filter(
              (w: WordTimestamp) => w.end >= newStartTime && w.start <= newEndTime
            )
            .map((w: WordTimestamp) => ({
              word: w.word.replace(/[.,!?]$/, "").toLowerCase(),
              punctuated_word: w.word,
              start: Math.max(0, w.start - newStartTime),
              end: Math.max(0, w.end - newStartTime),
              confidence: w.confidence || 0.99,
              speaker: w.speaker?.toString() || "0",
              layout: defaultLayout,
            }))

          if (clipWords.length > 0) {
            updateData.captions = [
              {
                id: createId(),
                transcript: clipWords.map((w) => w.punctuated_word).join(" "),
                start: 0,
                end: Math.max(0, newEndTime - newStartTime),
                confidence: 0.99,
                channel: 0,
                layout: defaultLayout,
                words: clipWords,
              },
            ] as any
          }
        }
      }

      updateData.status = "rendering"
      updateData.renderProgress = 0
      updateData.renderStatus = "Re-rendering trimmed clip..."
      updateData.originalVideoUrl = null // Reset so reframer cuts from source video
      updateData.previewVideoUrl = null
      updateData.captionVideoUrl = null
    } else if (hasCaptionsChanged) {
      updateData.captions = normalizeCaptions(body.captions)
      updateData.status = "rendering"
      updateData.renderProgress = 0
      updateData.renderStatus = "Burning updated subtitles..."
      updateData.previewVideoUrl = null
      updateData.captionVideoUrl = null
      // originalVideoUrl remains intact so Modal burner burns fast
    } else if (hasStyleChanged) {
      updateData.status = "rendering"
      updateData.renderProgress = 0
      updateData.renderStatus = "Updating preview..."
      updateData.previewVideoUrl = null
      updateData.captionVideoUrl = null
    }

    const updatedClip = await db
      .update(clips)
      .set(updateData)
      .where(eq(clips.id, clipId))
      .returning()

    if (hasTimeChanged || hasStyleChanged || hasCaptionsChanged) {
      await inngest.send({
        name: "clip.render_requested",
        data: { clipId },
      })
    }

    return NextResponse.json({ clip: updatedClip[0] })
  } catch (error) {
    console.error("Clip update error:", error)
    return NextResponse.json(
      { error: "Failed to update clip" },
      { status: 500 }
    )
  }
}


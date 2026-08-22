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
      body.captionStyle !== undefined &&
      body.captionStyle !== clip.captionStyle

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

    const updateData: Partial<typeof clips.$inferInsert> = {
      title: body.title !== undefined ? body.title : clip.title,
      captionStyle:
        body.captionStyle !== undefined ? body.captionStyle : clip.captionStyle,
      updatedAt: new Date(),
    }

    if (hasTimeChanged) {
      updateData.startTime = newStartTime
      updateData.endTime = newEndTime

      // Slice transcript words for the newly trimmed time range
      const [transcriptionRecord] = await db
        .select()
        .from(transcriptions)
        .where(eq(transcriptions.projectId, clip.projectId))
        .limit(1)

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
              words: clipWords,
            },
          ]
        }
      }

      updateData.status = "rendering"
      updateData.renderProgress = 0
      updateData.renderStatus = "Re-rendering trimmed clip..."
      updateData.originalVideoUrl = null // Reset so reframer cuts from source video
      updateData.previewVideoUrl = null
      updateData.captionVideoUrl = null
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

    if (hasTimeChanged || hasStyleChanged) {
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


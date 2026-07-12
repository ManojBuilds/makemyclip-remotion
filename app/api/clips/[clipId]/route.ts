import { NextResponse } from "next/server"
import { getServerSession } from "@/lib/auth-server"
import { db } from "@/lib/db"
import { clips } from "@/lib/db/schema"
import { eq } from "drizzle-orm"
import { inngest } from "@/lib/inngest/client"

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

    // Verify ownership (optional but recommended: join with projects)
    // For now, we trust the clipId is enough for a prototype,
    // but in production, we should check if project.userId === session.user.id

    const hasStyleChanged =
      body.captionStyle !== undefined &&
      body.captionStyle !== clip.captionStyle

    const updateData: Partial<typeof clips.$inferInsert> = {
      title: body.title !== undefined ? body.title : clip.title,
      captionStyle:
        body.captionStyle !== undefined ? body.captionStyle : clip.captionStyle,
      updatedAt: new Date(),
    }

    if (hasStyleChanged) {
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

    if (hasStyleChanged) {
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

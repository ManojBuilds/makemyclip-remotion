import { NextResponse } from "next/server"
import { getServerSession } from "@/lib/auth-server"
import { db } from "@/lib/db"
import { clips } from "@/lib/db/schema"
import { eq } from "drizzle-orm"

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ projectId: string }> }
) {
  try {
    const session = await getServerSession()
    if (!session) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const { projectId } = await params
    const body = await request.json()

    // Update all clips for this project with the provided styles
    // Note: We don't update hookText or captions as they are clip-specific
    const updatePayload: Partial<typeof clips.$inferInsert> = {
      updatedAt: new Date(),
    }
    if (body.captionStyle !== undefined) {
      updatePayload.captionStyle = body.captionStyle
    }
    if (body.wordHighlight !== undefined) {
      updatePayload.wordHighlight = Boolean(body.wordHighlight)
    }

    await db
      .update(clips)
      .set(updatePayload)
      .where(eq(clips.projectId, projectId))

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error("Bulk update error:", error)
    return NextResponse.json(
      { error: "Failed to apply styles to all clips" },
      { status: 500 }
    )
  }
}

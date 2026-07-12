import { NextResponse } from "next/server"
import { inngest } from "@/lib/inngest/client"
import { db } from "@/lib/db"
import { clips, user } from "@/lib/db/schema"
import { eq } from "drizzle-orm"

export async function POST(req: Request) {
  try {
    const { clipId, styling } = await req.json()

    if (!clipId) {
      return NextResponse.json({ error: "clipId is required" }, { status: 400 })
    }

    // Check if clip exists
    const clip = await db.query.clips.findFirst({
      where: eq(clips.id, clipId),
    })

    if (!clip) {
      return NextResponse.json({ error: "Clip not found" }, { status: 404 })
    }

    // Eagerly set status to rendering
    await db
      .update(clips)
      .set({
        status: "rendering",
        renderProgress: 0,
        renderStatus: "Warming up the engines...",
      })
      .where(eq(clips.id, clipId))

    // Trigger Inngest function
    await inngest.send({
      name: "clip.render_requested",
      data: { clipId, styling },
    })

    return NextResponse.json({
      success: true,
      message: "Render job queued successfully",
    })
  } catch (err: unknown) {
    console.error("Render trigger error:", err)
    const message = err instanceof Error ? err.message : "Internal server error"
    return NextResponse.json({ error: message }, { status: 500 })
  }
}

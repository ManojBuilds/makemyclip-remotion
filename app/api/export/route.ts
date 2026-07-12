import { NextResponse } from "next/server"
import { inngest } from "@/lib/inngest/client"
import { db } from "@/lib/db"
import { clips } from "@/lib/db/schema"
import { eq } from "drizzle-orm"

/**
 * POST /api/export
 * Triggers an on-demand HD export for a clip.
 * The preview is already available — this produces the full 1080p version.
 */
export async function POST(req: Request) {
  try {
    const { clipId } = await req.json()

    if (!clipId) {
      return NextResponse.json({ error: "clipId is required" }, { status: 400 })
    }

    const clip = await db.query.clips.findFirst({
      where: eq(clips.id, clipId),
    })

    if (!clip) {
      return NextResponse.json({ error: "Clip not found" }, { status: 404 })
    }

    if (!clip.originalVideoUrl) {
      return NextResponse.json(
        {
          error:
            "Clip has no reframed video yet. Please wait for processing to complete.",
        },
        { status: 400 }
      )
    }

    // If HD export already exists, return it immediately
    if (clip.captionVideoUrl) {
      return NextResponse.json({
        success: true,
        alreadyExported: true,
        url: clip.captionVideoUrl,
      })
    }

    // Set status to rendering
    await db
      .update(clips)
      .set({
        status: "rendering",
        renderStatus: "Rendering HD export...",
      })
      .where(eq(clips.id, clipId))

    // Trigger Inngest export function
    await inngest.send({
      name: "clip.export_requested",
      data: { clipId },
    })

    return NextResponse.json({
      success: true,
      message: "HD export queued successfully",
    })
  } catch (err: unknown) {
    console.error("Export trigger error:", err)
    const message = err instanceof Error ? err.message : "Internal server error"
    return NextResponse.json({ error: message }, { status: 500 })
  }
}

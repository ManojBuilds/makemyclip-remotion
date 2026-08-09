import { NextResponse } from "next/server"
import { inngest } from "@/lib/inngest/client"
import { db } from "@/lib/db"
import { clips, projects, user } from "@/lib/db/schema"
import { eq } from "drizzle-orm"

/**
 * POST /api/export
 * Triggers an on-demand HD export for a clip.
 * Export quality is plan-gated: free=720p+watermark, paid=1080p clean.
 */
export async function POST(req: Request) {
  try {
    const { clipId } = await req.json()

    if (!clipId) {
      return NextResponse.json({ error: "clipId is required" }, { status: 400 })
    }

    // Fetch clip + user plan in one query
    const [data] = await db
      .select({
        clip: clips,
        userPlan: user.plan,
      })
      .from(clips)
      .innerJoin(projects, eq(clips.projectId, projects.id))
      .innerJoin(user, eq(projects.userId, user.id))
      .where(eq(clips.id, clipId))

    if (!data) {
      return NextResponse.json({ error: "Clip not found" }, { status: 404 })
    }

    const clip = data.clip
    const plan = data.userPlan || "free"

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

    // Trigger Inngest export function with plan info
    await inngest.send({
      name: "clip.export_requested",
      data: { clipId, plan },
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


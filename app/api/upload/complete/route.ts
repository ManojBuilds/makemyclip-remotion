import { NextResponse } from "next/server"
import { getServerSession } from "@/lib/auth-server"
import { db } from "@/lib/db"
import { projects } from "@/lib/db/schema"

export async function POST(request: Request) {
  try {
    const session = await getServerSession()
    if (!session) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const {
      key,
      title,
      duration,
      styling,
      videoFormat,
      transcribeLanguage,
      translateLanguage,
    } = await request.json()

    if (!key || !title) {
      return NextResponse.json(
        { error: "key and title are required" },
        { status: 400 }
      )
    }

    // Verify the key belongs to this user
    if (!key.startsWith(`users/${session.user.id}/`)) {
      return NextResponse.json({ error: "Forbidden" }, { status: 403 })
    }

    // Create the project in the database, persisting chosen caption style
    const [project] = await db
      .insert(projects)
      .values({
        userId: session.user.id,
        title,
        sourceVideoKey: key,
        status: "uploading",
        duration: duration || null,
        videoFormat: videoFormat || "reframe",
        transcribeLanguage: transcribeLanguage || "auto",
        translateLanguage: translateLanguage || "none",
        // Persist caption styling preset name at the project level.
        captionStyle: styling ? (styling.preset || styling.name || "impact") : "impact",
      })
      .returning()

    // Trigger the background processing pipeline
    const { inngest } = await import("@/lib/inngest/client")
    await inngest.send({
      name: "video.uploaded",
      data: {
        projectId: project.id,
        key,
        duration,
      },
    })

    return NextResponse.json({
      projectId: project.id,
    })
  } catch (error) {
    console.error("Upload complete error:", error)
    return NextResponse.json(
      { error: "Failed to create project" },
      { status: 500 }
    )
  }
}

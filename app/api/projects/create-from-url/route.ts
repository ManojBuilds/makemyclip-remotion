import { NextResponse } from "next/server"
import { eq } from "drizzle-orm"
import { db } from "@/lib/db"
import { projects, user } from "@/lib/db/schema"
import { inngest } from "@/lib/inngest/client"
import { getServerSession } from "@/lib/auth-server"
import { normalizeVideoUrl } from "@/lib/youtube"
import { isSupportedVideoUrl } from "@/lib/video-sources"
import { fetchUniversalVideoMetadata } from "@/lib/video-sources-server"
import { getPlanLimit } from "@/lib/config"

export async function POST(req: Request) {
  try {
    const session = await getServerSession()
    if (!session) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const {
      url,
      title: providedTitle,
      duration: providedDuration,
      videoFormat,
      styling,
      transcribeLanguage,
      translateLanguage,
      removeSilence,
      isSingleClip,
      cropMode,
      startTime,
      endTime,
    } = await req.json()

    if (!url || typeof url !== "string") {
      return NextResponse.json({ error: "URL is required" }, { status: 400 })
    }

    const normalizedUrl = normalizeVideoUrl(url)
    if (!isSupportedVideoUrl(normalizedUrl)) {
      return NextResponse.json(
        {
          error: "Invalid video URL",
          message:
            "Unsupported platform. Please provide a valid YouTube, Google Drive, Vimeo, Loom, Twitch, or direct video link.",
        },
        { status: 400 }
      )
    }

    // 1. Fetch metadata (title + duration) only if it wasn't pre-fetched by the client
    //    so we can validate credits and persist the real values on the project record.
    let duration: number
    let finalTitle: string

    if (typeof providedDuration === "number" && providedDuration > 0) {
      duration = providedDuration
      finalTitle =
        (providedTitle && String(providedTitle).trim()) || "Video Project"
      console.log("Reusing client-provided metadata:", { duration, finalTitle })
    } else {
      let metadata
      try {
        metadata = await fetchUniversalVideoMetadata(normalizedUrl)
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to fetch video info."
        return NextResponse.json(
          { error: "Invalid video", message },
          { status: 400 }
        )
      }
      duration = metadata.duration
      console.log("Fetched video metadata:", metadata)
      finalTitle =
        (providedTitle && String(providedTitle).trim()) || metadata.title
    }

    // 2. Credit + plan checks (mirrors /api/upload/presign).
    const { getOrCreateUser } = require("@/lib/user")
    const dbUser = await getOrCreateUser({
      id: session.user.id,
      email: session.user.email,
      name: session.user.name,
    })

    if (!dbUser) {
      return NextResponse.json({ error: "User not found" }, { status: 404 })
    }

    const durationInMinutes = Math.ceil(duration / 60)
    const availableCredits = dbUser.credits ?? 0
    const planConfig = getPlanLimit(dbUser.plan)

    if (duration > planConfig.maxUploadDurationSeconds) {
      return NextResponse.json(
        {
          error: "Plan upload limit exceeded",
          message: `Videos on your ${planConfig.name} plan are limited to ${planConfig.label}. Please upgrade for longer videos.`,
        },
        { status: 403 }
      )
    }

    if (availableCredits < durationInMinutes) {
      return NextResponse.json(
        {
          error: "Insufficient credits",
          message: `This video requires ${durationInMinutes} credits, but you only have ${availableCredits}. Please upgrade your plan.`,
        },
        { status: 403 }
      )
    }

    // 3. Create the project with real metadata.
    const [project] = await db
      .insert(projects)
      .values({
        title: finalTitle,
        userId: session.user.id,
        status: "uploading", // Will transition to processing in Inngest
        sourceVideoKey: normalizedUrl, // Store URL as key (Inngest detects http(s) and skips R2 presigning)
        duration,
        videoFormat: cropMode || videoFormat || "reframe",
        transcribeLanguage: transcribeLanguage || "auto",
        translateLanguage: translateLanguage || "none",
        removeSilence: removeSilence !== undefined ? removeSilence : true,
        isSingleClip: Boolean(isSingleClip),
        clipStartTime: typeof startTime === "number" ? startTime : null,
        clipEndTime: typeof endTime === "number" ? endTime : null,
        ...(styling
          ? {
              captionStyle: styling.preset || styling.name || "impact",
              wordHighlight: styling.word_highlight !== undefined ? Boolean(styling.word_highlight) : true,
            }
          : {}),
      })
      .returning()

    // 4. Trigger Inngest WITH duration so the deduct-credits step runs.
    await inngest.send({
      name: "video.uploaded",
      data: {
        projectId: project.id,
        key: normalizedUrl,
        videoUrl: normalizedUrl,
        title: project.title,
        duration,
        isSingleClip: Boolean(isSingleClip),
        cropMode: cropMode || videoFormat || "auto",
        startTime: typeof startTime === "number" ? startTime : undefined,
        endTime: typeof endTime === "number" ? endTime : undefined,
      },
    })

    return NextResponse.json({
      success: true,
      projectId: project.id,
      title: finalTitle,
      duration,
      durationInMinutes,
    })
  } catch (err: unknown) {
    console.error("Failed to create project from URL:", err)
    const message = err instanceof Error ? err.message : "Internal server error"
    return NextResponse.json({ error: message }, { status: 500 })
  }
}

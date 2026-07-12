import { NextResponse } from "next/server"
import { getServerSession } from "@/lib/auth-server"
import { getUploadPresignedUrl } from "@/lib/r2"
import { createId } from "@paralleldrive/cuid2"
import { db } from "@/lib/db"
import { user } from "@/lib/db/schema"
import { eq } from "drizzle-orm"

const ALLOWED_VIDEO_TYPES = [
  "video/mp4",
  "video/quicktime",
  "video/webm",
  "video/x-msvideo",
  "video/x-matroska",
]

const MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024 // 2GB

export async function POST(request: Request) {
  try {
    const session = await getServerSession()
    if (!session) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const { filename, contentType, fileSize, duration } = await request.json()

    if (!filename || !contentType || typeof duration !== "number") {
      return NextResponse.json(
        { error: "filename, contentType, and duration (seconds) are required" },
        { status: 400 }
      )
    }

    // Check user credits
    const [dbUser] = await db
      .select()
      .from(user)
      .where(eq(user.id, session.user.id))

    if (!dbUser) {
      return NextResponse.json({ error: "User not found" }, { status: 404 })
    }

    const durationInMinutes = Math.ceil(duration / 60)
    const availableCredits = dbUser.credits ?? 0
    const isFree = dbUser.plan === "free"

    // Enforce Free Plan Limits
    if (isFree) {
      if (durationInMinutes > 30) {
        return NextResponse.json(
          {
            error: "Free plan limit",
            message:
              "Videos on the free plan are limited to 30 minutes. Please upgrade for longer videos.",
          },
          { status: 403 }
        )
      }
      const MAX_FREE_SIZE = 500 * 1024 * 1024 // 500MB
      if (fileSize && fileSize > MAX_FREE_SIZE) {
        return NextResponse.json(
          {
            error: "File too large",
            message:
              "Free plan files are limited to 500MB. Please upgrade to upload larger files.",
          },
          { status: 403 }
        )
      }
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

    if (!ALLOWED_VIDEO_TYPES.includes(contentType)) {
      return NextResponse.json(
        { error: "Only video files are allowed (mp4, mov, webm, avi, mkv)" },
        { status: 400 }
      )
    }

    if (fileSize && fileSize > MAX_FILE_SIZE) {
      return NextResponse.json(
        { error: "File size exceeds 2GB limit" },
        { status: 400 }
      )
    }

    // Generate a unique key: users/{userId}/videos/{id}/{original-filename}
    const fileId = createId()
    const ext = filename.split(".").pop() || "mp4"
    const key = `users/${session.user.id}/videos/${fileId}/source.${ext}`

    const presignedUrl = await getUploadPresignedUrl(key, contentType)

    return NextResponse.json({
      presignedUrl,
      key,
      fileId,
    })
  } catch (error) {
    console.error("Presign error:", error)
    return NextResponse.json(
      { error: "Failed to generate upload URL" },
      { status: 500 }
    )
  }
}

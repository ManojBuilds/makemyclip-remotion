import { NextResponse } from "next/server"
import { getServerSession } from "@/lib/auth-server"
import { db } from "@/lib/db"
import { projects, clips } from "@/lib/db/schema"
import { eq, desc } from "drizzle-orm"
import { isHttpUrl } from "@/lib/youtube"
import { getDownloadPresignedUrl } from "@/lib/r2"

const MAX_TITLE_LENGTH = 200

export async function GET(
  request: Request,
  { params }: { params: Promise<{ projectId: string }> }
) {
  try {
    const session = await getServerSession()
    if (!session) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const { projectId } = await params

    const [project] = await db
      .select({
        id: projects.id,
        userId: projects.userId,
        title: projects.title,
        status: projects.status,
        sourceVideoKey: projects.sourceVideoKey,
        createdAt: projects.createdAt,
      })
      .from(projects)
      .where(eq(projects.id, projectId))

    if (!project) {
      return NextResponse.json({ error: "Project not found" }, { status: 404 })
    }

    if (project.userId !== session.user.id) {
      return NextResponse.json({ error: "Forbidden" }, { status: 403 })
    }

    const { searchParams } = new URL(request.url)
    const onlyStatus = searchParams.get("onlyStatus") === "true"

    if (onlyStatus) {
      const [projectClips] = await Promise.all([
        db
          .select({
            id: clips.id,
            status: clips.status,
            renderStatus: clips.renderStatus,
            captionVideoUrl: clips.captionVideoUrl,
          })
          .from(clips)
          .where(eq(clips.projectId, projectId)),
      ])

      return NextResponse.json({
        project: { id: project.id, status: project.status },
        clips: projectClips,
      })
    }

    const [projectClips, videoUrl] = await Promise.all([
      db
        .select({
          id: clips.id,
          title: clips.title,
          hookText: clips.hookText,
          startTime: clips.startTime,
          endTime: clips.endTime,
          viralScore: clips.viralScore,
          viralReason: clips.viralReason,
          clipType: clips.clipType,
          status: clips.status,
          renderStatus: clips.renderStatus,
          originalVideoUrl: clips.originalVideoUrl,
          previewVideoUrl: clips.previewVideoUrl,
          captionVideoUrl: clips.captionVideoUrl,
          thumbnailUrl: clips.thumbnailUrl,
          captionStyle: clips.captionStyle,
        })
        .from(clips)
        .where(eq(clips.projectId, projectId))
        .orderBy(desc(clips.viralScore)),
      project.sourceVideoKey
        ? isHttpUrl(project.sourceVideoKey)
          ? Promise.resolve(project.sourceVideoKey)
          : getDownloadPresignedUrl(project.sourceVideoKey, 3600)
        : Promise.resolve(""),
    ])

    const { userId: _userId, ...projectData } = project
    return NextResponse.json({
      project: { ...projectData, videoUrl },
      clips: projectClips,
    })
  } catch (error) {
    console.error("Project fetch error:", error)
    return NextResponse.json(
      { error: "Failed to fetch project" },
      { status: 500 }
    )
  }
}

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
    const { title } = body ?? {}

    if (typeof title !== "string" || !title.trim()) {
      return NextResponse.json({ error: "Title is required" }, { status: 400 })
    }

    const trimmed = title.trim().slice(0, MAX_TITLE_LENGTH)

    const [existing] = await db
      .select({ id: projects.id, userId: projects.userId })
      .from(projects)
      .where(eq(projects.id, projectId))

    if (!existing) {
      return NextResponse.json({ error: "Project not found" }, { status: 404 })
    }
    if (existing.userId !== session.user.id) {
      return NextResponse.json({ error: "Forbidden" }, { status: 403 })
    }

    const [updated] = await db
      .update(projects)
      .set({ title: trimmed, updatedAt: new Date() })
      .where(eq(projects.id, projectId))
      .returning()

    return NextResponse.json({ project: updated })
  } catch (error) {
    console.error("Project patch error:", error)
    return NextResponse.json(
      { error: "Failed to update project" },
      { status: 500 }
    )
  }
}

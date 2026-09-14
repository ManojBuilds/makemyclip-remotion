import { NextResponse } from "next/server"
import { getServerSession } from "@/lib/auth-server"
import { db } from "@/lib/db"
import { projects, clips } from "@/lib/db/schema"
import { eq, desc, count, sql } from "drizzle-orm"
import { isHttpUrl } from "@/lib/youtube"
import { resolveSourceVideoUrl } from "@/lib/r2"

export async function GET() {
  try {
    const session = await getServerSession()
    if (!session) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const userProjects = await db
      .select({
        id: projects.id,
        title: projects.title,
        status: projects.status,
        duration: projects.duration,
        sourceVideoKey: projects.sourceVideoKey,
        isSingleClip: projects.isSingleClip,
        createdAt: projects.createdAt,
        clipCount: count(clips.id),
        thumbnailUrl: sql<string | null>`min(${clips.thumbnailUrl})`,
      })
      .from(projects)
      .leftJoin(clips, eq(projects.id, clips.projectId))
      .where(eq(projects.userId, session.user.id))
      .groupBy(projects.id)
      .orderBy(desc(projects.createdAt))

    const projectsWithMedia = await Promise.all(
      userProjects.map(async (p) => {
        const isExternal = p.sourceVideoKey ? isHttpUrl(p.sourceVideoKey) : false
        let videoUrl: string | null = null
        if (!isExternal && p.sourceVideoKey) {
          try {
            videoUrl = await resolveSourceVideoUrl(p.sourceVideoKey)
          } catch {
            // ignore video resolution error
          }
        }

        return {
          id: p.id,
          title: p.title,
          status: p.status,
          duration: p.duration,
          sourceUrl: isExternal ? p.sourceVideoKey : null,
          videoUrl,
          thumbnailUrl: p.thumbnailUrl,
          isSingleClip: p.isSingleClip,
          clipCount: Number(p.clipCount),
          createdAt: p.createdAt.toISOString(),
        }
      })
    )

    return NextResponse.json({
      projects: projectsWithMedia,
    })
  } catch (error) {
    console.error("Projects fetch error:", error)
    return NextResponse.json(
      { error: "Failed to fetch projects" },
      { status: 500 }
    )
  }
}

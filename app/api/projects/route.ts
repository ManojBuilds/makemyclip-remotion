import { NextResponse } from "next/server"
import { getServerSession } from "@/lib/auth-server"
import { db } from "@/lib/db"
import { projects, clips } from "@/lib/db/schema"
import { eq, desc, count } from "drizzle-orm"

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
        createdAt: projects.createdAt,
        clipCount: count(clips.id),
      })
      .from(projects)
      .leftJoin(clips, eq(projects.id, clips.projectId))
      .where(eq(projects.userId, session.user.id))
      .groupBy(projects.id)
      .orderBy(desc(projects.createdAt))

    return NextResponse.json({
      projects: userProjects.map((p) => ({
        ...p,
        clipCount: Number(p.clipCount),
        createdAt: p.createdAt.toISOString(),
      })),
    })
  } catch (error) {
    console.error("Projects fetch error:", error)
    return NextResponse.json(
      { error: "Failed to fetch projects" },
      { status: 500 }
    )
  }
}

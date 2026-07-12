"use client"

import { useEffect, useMemo, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ProjectDetailClient } from "./project-detail-client"
import type { Clip, Project } from "@/lib/types"
import { extractYouTubeVideoId, isHttpUrl } from "@/lib/youtube"
import { useDashboardUser } from "@/components/dashboard-context"

type ProjectDetailResponse = {
  project: {
    id: string
    title: string
    status: Project["status"]
    createdAt: string
    videoUrl?: string
    sourceVideoKey?: string | null
    [key: string]: unknown
  }
  clips: Clip[]
  transcription?: unknown
}

export default function ProjectDetailPage() {
  const router = useRouter()
  const params = useParams<{ projectId: string }>()
  const { user, status } = useDashboardUser()
  const projectId = useMemo(() => {
    const value = params?.projectId
    return Array.isArray(value) ? value[0] : value
  }, [params])

  const [project, setProject] = useState<Project | null>(null)
  const [clips, setClips] = useState<Clip[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!projectId) {
      return
    }

    let cancelled = false

    const loadProject = async () => {
      try {
        const projectRes = await fetch(`/api/projects/${projectId}`)
        if (projectRes.status === 401) {
          router.replace("/login")
          return
        }

        if (!projectRes.ok) {
          setError("Project not found.")
          return
        }

        const projectData = (await projectRes.json()) as ProjectDetailResponse
        const sourceKey = projectData.project.sourceVideoKey ?? ""
        const sourceIsExternal = sourceKey ? isHttpUrl(sourceKey) : false
        const youtubeVideoId = sourceIsExternal
          ? extractYouTubeVideoId(sourceKey)
          : null

        if (cancelled) {
          return
        }

        setProject({
          id: projectData.project.id,
          title: projectData.project.title,
          status: projectData.project.status,
          createdAt: projectData.project.createdAt,
          videoUrl: projectData.project.videoUrl ?? "",
          sourceUrl: sourceIsExternal ? sourceKey : null,
          isYouTube: !!youtubeVideoId,
        })
        setClips(projectData.clips)
      } catch (loadError) {
        console.error("Failed to load project detail:", loadError)
        if (!cancelled) {
          setError("Failed to load project.")
        }
      }
    }

    loadProject()

    return () => {
      cancelled = true
    }
  }, [projectId, router])

  if (error) {
    return (
      <div className="flex min-h-[70vh] flex-col items-center justify-center space-y-4 px-4 text-center">
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">
          {error}
        </h2>
        <Button
          onClick={() => router.push("/projects")}
          className="rounded-xl border-0 bg-slate-900 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-800"
        >
          Back to Dashboard
        </Button>
      </div>
    )
  }

  if (status !== "authenticated" || !project || !clips || !user) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <ProjectDetailClient
      userData={{
        credits: user.credits,
        subscriptionStatus: user.subscriptionStatus ?? "inactive",
        plan: user.plan,
      }}
      initialProject={project}
      initialClips={clips}
    />
  )
}

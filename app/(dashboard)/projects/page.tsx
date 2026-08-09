"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Loader2 } from "lucide-react"
import { ProjectsClient } from "./projects-client"
import type { Project } from "@/lib/types"
import { useDashboardUser } from "@/components/dashboard-context"

type ProjectsResponse = {
  projects: Project[]
}

export default function ProjectsPage() {
  const router = useRouter()
  const { user, status } = useDashboardUser()
  const [projects, setProjects] = useState<Project[] | null>(null)

  useEffect(() => {
    let cancelled = false

    const loadData = async () => {
      try {
        const projectsRes = await fetch("/api/projects")
        if (projectsRes.status === 401) {
          window.location.reload()
          return
        }

        if (!projectsRes.ok) {
          throw new Error("Failed to load dashboard data")
        }

        const projectsData = (await projectsRes.json()) as ProjectsResponse

        if (cancelled) {
          return
        }

        setProjects(projectsData.projects)
      } catch (error) {
        console.error("Failed to load projects page:", error)
      }
    }

    loadData()

    return () => {
      cancelled = true
    }
  }, [router])

  if (status !== "authenticated" || !projects) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <ProjectsClient
      projects={projects}
      plan={user?.plan ?? "free"}
      credits={user?.credits ?? 0}
    />
  )
}

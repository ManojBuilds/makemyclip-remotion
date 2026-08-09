"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
import { useUpload } from "@/hooks/use-upload"
import { UnifiedInput } from "@/components/video/unified-input"
import { CaptionTemplate } from "@/components/video/caption_templates"
import { Sparkles, Search, Video } from "lucide-react"
import { ProjectListItem } from "@/components/dashboard/project-list-item"
import { CookingOverlay } from "@/components/dashboard/cooking-overlay"
import type { Project } from "@/lib/types"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

import { UpgradeModal } from "@/components/ui/upgrade-modal"

export function ProjectsClient({
  projects,
  plan,
  credits,
}: {
  projects: Project[]
  plan: string
  credits: number
}) {
  const isFree = plan === "free"
  const router = useRouter()
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isSubmittingUrl, setIsSubmittingUrl] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [upgradeTrigger, setUpgradeTrigger] = useState<string | null>(null)
  const { status, progress, error, upload, reset } = useUpload()

  // Redirect from landing page with pending URL
  useEffect(() => {
    if (typeof window !== "undefined") {
      const pending = sessionStorage.getItem("pending_youtube_url")
      const pendingTranscribe = sessionStorage.getItem(
        "pending_transcribe_language"
      )
      const pendingTranslate = sessionStorage.getItem(
        "pending_translate_language"
      )
      if (pending) {
        sessionStorage.removeItem("pending_youtube_url")
        sessionStorage.removeItem("pending_transcribe_language")
        sessionStorage.removeItem("pending_translate_language")
        handleUrlSubmit(
          pending,
          undefined,
          pendingTranscribe || "auto",
          pendingTranslate || "none"
        )
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleUrlSubmit = async (
    url: string,
    styling?: CaptionTemplate,
    transcribeLanguage?: string,
    translateLanguage?: string,
    duration?: number | null,
    title?: string | null
  ): Promise<boolean> => {
    if (!url) return false
    setIsSubmittingUrl(true)
    try {
      const res = await fetch("/api/projects/create-from-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          styling,
          transcribeLanguage,
          translateLanguage,
          duration,
          title,
        }),
      })
      const data = await res.json()

      if (!res.ok || !data.success) {
        const heading = data?.error || "Couldn't import video"
        const message =
          data?.message ||
          "Please check the URL and try again. The video may be private or unavailable."
        toast.error(heading, { description: message })
        return false
      }

      router.push(`/projects/${data.projectId}`)
      return true
    } catch (err) {
      console.error("URL submission failed:", err)
      toast.error("Network error", {
        description: "Couldn't reach the server. Please try again.",
      })
      return false
    } finally {
      setIsSubmittingUrl(false)
    }
  }

  const handleFileSelect = async (
    file: File,
    styling?: CaptionTemplate,
    transcribeLanguage?: string,
    translateLanguage?: string
  ) => {
    // Pre-check credits on the frontend before starting the upload
    try {
      const duration = await new Promise<number>((resolve, reject) => {
        const video = document.createElement("video")
        video.preload = "metadata"
        video.onloadedmetadata = () => resolve(video.duration)
        video.onerror = () => reject(new Error("Could not read video metadata"))
        video.src = URL.createObjectURL(file)
      })

      const durationInMinutes = Math.ceil(duration / 60)
      if (credits < durationInMinutes) {
        setUpgradeTrigger("processing_limit")
        return
      }
    } catch {
      console.warn("Could not pre-check video duration for credit validation")
    }

    setSelectedFile(file)
    try {
      const projectId = await upload(
        file,
        styling as unknown as Record<string, unknown> | undefined,
        undefined,
        transcribeLanguage,
        translateLanguage
      )
      if (projectId) router.push(`/projects/${projectId}`)
    } catch (err) {
      console.error("Failed to process video:", err)
      const message = err instanceof Error ? err.message : "Upload failed"
      toast.error("Upload failed", { description: message })
    }
  }

  // Redirect from landing page with pending URL
  useEffect(() => {
    if (typeof window !== "undefined") {
      const pending = sessionStorage.getItem("pending_youtube_url")
      const pendingTranscribe = sessionStorage.getItem(
        "pending_transcribe_language"
      )
      const pendingTranslate = sessionStorage.getItem(
        "pending_translate_language"
      )
      if (pending) {
        sessionStorage.removeItem("pending_youtube_url")
        sessionStorage.removeItem("pending_transcribe_language")
        sessionStorage.removeItem("pending_translate_language")
        // eslint-disable-next-line react-hooks/set-state-in-effect
        handleUrlSubmit(
          pending,
          undefined,
          pendingTranscribe || "auto",
          pendingTranslate || "none"
        )
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const isUploading =
    status !== "idle" && status !== "error" && status !== "done"

  const filteredProjects = projects.filter((project) =>
    project.title?.toLowerCase().includes(searchQuery.toLowerCase())
  )
  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 px-4 py-4 sm:space-y-8 sm:px-6 sm:py-8 md:space-y-10 md:py-12">

      {/* 2. UPLOAD FLOW */}
      {!selectedFile && !isUploading && (
        <div className="w-full animate-in duration-300 fade-in">
          <UnifiedInput
            onUrlSubmit={handleUrlSubmit}
            onFileSelect={handleFileSelect}
            isSubmitting={isSubmittingUrl || isUploading}
          />
        </div>
      )}

      {/* Cooking/Uploading state */}
      {isUploading && <CookingOverlay status={status} progress={progress} />}

      {/* 3. Empty State or Projects List */}
      {!selectedFile && !isUploading && (
        <div className="relative space-y-6">
          {projects.length === 0 ? (
            <Card className="mx-auto max-w-lg animate-in border-hairline text-center shadow-sm duration-500 fade-in">
              <CardContent className="flex flex-col items-center pt-10 pb-10 sm:pt-16 sm:pb-16">
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full border border-hairline bg-slate-50 text-slate-400">
                  <Video className="h-5 w-5" />
                </div>
                <h3 className="mb-1.5 text-base font-semibold text-slate-900">
                  Create your first video!
                </h3>
                <p className="max-w-sm text-xs font-medium text-slate-500">
                  Paste a YouTube link or drop a video file above to generate
                  viral clips instantly.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-6">
              {/* Toolbar */}
              <div className="flex flex-col justify-between gap-4 border-b border-hairline pb-4 sm:flex-row sm:items-center">
                <h2 className="flex items-center gap-2 text-xs font-bold tracking-[0.2em] text-slate-400 uppercase">
                  <span>Recent Videos</span>
                  <Badge
                    variant="secondary"
                    className="px-2 py-0.5 font-semibold lowercase"
                  >
                    {filteredProjects.length}{" "}
                    {filteredProjects.length === 1 ? "video" : "videos"}
                  </Badge>
                </h2>
                <div className="relative w-full sm:w-64">
                  <Search className="absolute top-1/2 left-3 z-10 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                  <Input
                    type="text"
                    placeholder="Search videos..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="bg-white pr-8 pl-9"
                  />
                  {searchQuery && (
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      onClick={() => setSearchQuery("")}
                      className="absolute top-1/2 right-2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                    >
                      ×
                    </Button>
                  )}
                </div>
              </div>

              {filteredProjects.length === 0 ? (
                <Card className="border-hairline text-center shadow-sm">
                  <CardContent className="flex flex-col items-center py-12">
                    <p className="text-xs font-medium text-slate-500">
                      No videos match &quot;{searchQuery}&quot;
                    </p>
                    <Button
                      variant="link"
                      size="sm"
                      onClick={() => setSearchQuery("")}
                      className="mt-2 text-xs font-semibold"
                    >
                      Clear search
                    </Button>
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-3">
                  {filteredProjects.map((project) => (
                    <ProjectListItem key={project.id} project={project} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <UpgradeModal
        open={Boolean(upgradeTrigger)}
        onOpenChange={(openState) => {
          if (!openState) setUpgradeTrigger(null)
        }}
        triggerId={upgradeTrigger}
      />
    </div>
  )
}

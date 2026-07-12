"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Sparkles, ArrowLeft, ExternalLink } from "lucide-react"
import { toast } from "sonner"

import { EditableTitle } from "@/components/dashboard/editable-title"
import { ClipCard } from "@/components/video/clip-card"
import { ProcessingSteps } from "@/components/dashboard/processing-steps"
import type { Project, Clip } from "@/lib/types"
import { triggerHDExport } from "@/lib/actions/export"

import { useUserStore } from "@/lib/store/useUserStore"

export function ProjectDetailClient({
  initialProject,
  initialClips,
  userData: _userData,
}: {
  initialProject: Project
  initialClips: Clip[]
  userData: {
    credits: number
    subscriptionStatus: string
    plan: string
  }
}) {
  const router = useRouter()
  const [project, setProject] = useState<Project>(initialProject)
  const [clips, setClips] = useState<Clip[]>(initialClips)
  const [showCaptions, setShowCaptions] = useState<Record<string, boolean>>({})
  const [activePlayingId, setActivePlayingId] = useState<string | null>(null)
  // NOTE: ZIP download UI intentionally disabled for now.
  // const [isDownloadingZip, setIsDownloadingZip] = useState(false);
  const [activeEditClip, setActiveEditClip] = useState<Clip | null>(null)
  const [isSavingStyle, setIsSavingStyle] = useState(false)
  const [autoDownloadClipIds, setAutoDownloadClipIds] = useState<
    Record<string, boolean>
  >({})
  const [downloadingClipId, setDownloadingClipId] = useState<string | null>(
    null
  )
  const [exportingClipIds, setExportingClipIds] = useState<
    Record<string, boolean>
  >({})
  // Refs to avoid stale closures in the polling interval
  const clipsRef = useRef<Clip[]>(clips)
  const autoDownloadRef = useRef<Record<string, boolean>>(autoDownloadClipIds)
  useEffect(() => {
    clipsRef.current = clips
  }, [clips])
  useEffect(() => {
    autoDownloadRef.current = autoDownloadClipIds
  }, [autoDownloadClipIds])
  void _userData

  const formatEta = (seconds: number) => {
    const s = Math.max(0, Math.floor(seconds))
    const mm = String(Math.floor(s / 60)).padStart(2, "0")
    const ss = String(s % 60).padStart(2, "0")
    return `${mm}:${ss}`
  }

  const unfinishedClips = clips.filter(
    (c) =>
      c.status === "rendering" || (!c.previewVideoUrl && !c.originalVideoUrl)
  )
  const unfinishedCount = unfinishedClips.length

  const [countdownSeconds, setCountdownSeconds] = useState(() =>
    unfinishedCount > 0 ? unfinishedCount * 3 * 60 : 0
  )

  useEffect(() => {
    if (countdownSeconds <= 0) return

    const interval = setInterval(() => {
      setCountdownSeconds((prev) => {
        if (prev <= 1) {
          if (unfinishedCount > 0) {
            return unfinishedCount * 3 * 60
          }
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(interval)
  }, [countdownSeconds, unfinishedCount])

  // const handleDownloadZip = async () => {};

  const handleDownloadClick = async (clip: Clip) => {
    // If HD export already exists, open in new tab immediately
    if (clip.captionVideoUrl) {
      window.open(clip.captionVideoUrl, "_blank", "noopener,noreferrer")
      toast.success("Opening clip in new tab!")
      return
    }

    // Otherwise trigger HD export
    const loadingToastId = toast.loading("Queuing HD export...")
    try {
      const data = await triggerHDExport(clip.id)

      // If the export was already done, open in new tab immediately
      if (data.alreadyExported && data.url) {
        toast.dismiss(loadingToastId)
        window.open(data.url, "_blank", "noopener,noreferrer")
        toast.success("Opening clip in new tab!")
        return
      }

      toast.dismiss(loadingToastId)
      toast.success("HD export queued! Will auto-download when ready.")

      setExportingClipIds((prev) => ({ ...prev, [clip.id]: true }))
      setAutoDownloadClipIds((prev) => ({ ...prev, [clip.id]: true }))
    } catch (err) {
      toast.dismiss(loadingToastId)
      console.error("Export trigger error:", err)
      toast.error("Failed to trigger HD export.")
    }
  }

  useEffect(() => {
    let intervalId: NodeJS.Timeout

    const fetchStatus = async () => {
      try {
        const res = await fetch(`/api/projects/${project.id}?onlyStatus=true`)
        if (!res.ok) return
        const data = await res.json()

        // Read latest values from refs to avoid stale closure issues
        const currentClips = clipsRef.current
        const currentAutoDownload = autoDownloadRef.current

        const transitioningToReady = project.status !== "ready" && data.project.status === "ready"

        let finalData = data
        if (transitioningToReady) {
          const fullRes = await fetch(`/api/projects/${project.id}`)
          if (fullRes.ok) {
            finalData = await fullRes.json()
          }
        }

        finalData.clips.forEach((newClip: Clip) => {
          const oldClip = currentClips.find((c) => c.id === newClip.id)
          if (
            oldClip &&
            !oldClip.captionVideoUrl &&
            newClip.captionVideoUrl &&
            currentAutoDownload[newClip.id]
          ) {
            // Mark as handled synchronously via ref to prevent duplicate triggers
            autoDownloadRef.current = { ...autoDownloadRef.current }
            delete autoDownloadRef.current[newClip.id]

            setAutoDownloadClipIds((prev) => {
              const updated = { ...prev }
              delete updated[newClip.id]
              return updated
            })

            setExportingClipIds((prev) => {
              const updated = { ...prev }
              delete updated[newClip.id]
              return updated
            })

            toast.success(`Export ready! Opening: ${oldClip.title}`)
            window.open(
              newClip.captionVideoUrl!,
              "_blank",
              "noopener,noreferrer"
            )
          }
        })

        // Preserve fields the polling endpoint doesn't include (sourceUrl/isYouTube)
        setProject((prev) => {
          if (prev.status !== "ready" && finalData.project.status === "ready") {
            // Fetch updated credits/user info when processing completes
            useUserStore.getState().fetchUser(true)
            if (
              typeof window !== "undefined" &&
              "Notification" in window &&
              Notification.permission === "granted"
            ) {
              new Notification("MakeMyClip", {
                body: `Your clips for "${prev.title || "video"}" are ready!`,
                icon: "/favicon.ico",
              })
            }
          }
          return { ...prev, ...finalData.project }
        })

        // Merge fetched data with current optimistic rendering states
        if (transitioningToReady) {
          setClips(finalData.clips)
        } else {
          setClips((prev) => {
            if (!prev || prev.length === 0) return finalData.clips
            return prev.map((oldClip) => {
              const newClip = finalData.clips.find((c: Clip) => c.id === oldClip.id)
              if (!newClip) return oldClip

              const merged = {
                ...oldClip,
                status: newClip.status,
                renderStatus: newClip.renderStatus,
                captionVideoUrl: newClip.captionVideoUrl,
              }

              if (newClip.captionVideoUrl && exportingClipIds[oldClip.id]) {
                setExportingClipIds((prev) => {
                  const updated = { ...prev }
                  delete updated[oldClip.id]
                  return updated
                })
              }

              if (
                currentAutoDownload[merged.id] &&
                !merged.captionVideoUrl &&
                merged.renderStatus !== "Export failed"
              ) {
                return {
                  ...merged,
                  status: "rendering",
                  renderStatus: merged.renderStatus || "Rendering HD export...",
                }
              }
              return merged
            })
          })
        }

        const isStillProcessing =
          finalData.project.status !== "ready" && finalData.project.status !== "error"
        const hasRenderingClips = finalData.clips.some(
          (c: Clip) => c.status === "rendering"
        )
        const hasLocalAutoDownloads = Object.keys(autoDownloadRef.current).length > 0

        if (!isStillProcessing && !hasRenderingClips && !hasLocalAutoDownloads) {
          clearInterval(intervalId)
        }
      } catch (err) {
        console.error("Failed to fetch project status", err)
      }
    }

    const isProcessing =
      project.status !== "ready" && project.status !== "error"
    const hasRenderingClips =
      clips.some((c) => c.status === "rendering") ||
      Object.keys(autoDownloadClipIds).length > 0

    if (isProcessing || hasRenderingClips) {
      intervalId = setInterval(fetchStatus, 60000)
    }

    return () => clearInterval(intervalId)
  }, [project.id, project.status, clips, autoDownloadClipIds])

  if (project.status === "error") {
    return (
      <div className="flex min-h-[70vh] flex-col items-center justify-center space-y-8 px-4 text-center">
        <div className="flex size-20 items-center justify-center rounded-3xl bg-rose-50 text-rose-500">
          <Sparkles className="h-10 w-10" />
        </div>
        <div className="space-y-2">
          <h2 className="text-3xl font-bold tracking-tight text-slate-900">
            Something went wrong
          </h2>
          <p className="mx-auto max-w-md text-base text-slate-500">
            We encountered an issue while processing your video. Our team has
            been notified.
          </p>
        </div>
        <Button
          onClick={() => router.push("/projects")}
          className="h-11 rounded-xl bg-slate-900 px-6 font-semibold text-white hover:bg-slate-800"
        >
          Back to Dashboard
        </Button>
      </div>
    )
  }

  const shouldShowClipsView = project.status === "ready" || clips.length > 0

  if (shouldShowClipsView) {
    return (
      <div className="mx-auto w-full max-w-5xl space-y-6 sm:px-6 sm:py-8 md:space-y-10 md:py-10">
        {/* HEADER — minimal */}
        <div className="flex flex-col justify-between gap-5 border-b border-slate-100 pb-5 md:flex-row md:items-center md:gap-6 md:pb-6">
          <div className="flex min-w-0 items-start gap-3 sm:items-center sm:gap-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => router.push("/projects")}
              className="hidden h-10 w-10 shrink-0 rounded-xl hover:bg-slate-100 sm:inline-flex"
            >
              <ArrowLeft className="h-5 w-5 text-slate-600" />
            </Button>
            <div className="min-w-0 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <EditableTitle
                  projectId={project.id}
                  value={project.title}
                  onSaved={(newTitle) =>
                    setProject((prev) => ({ ...prev, title: newTitle }))
                  }
                />
                {project.isYouTube && project.sourceUrl && (
                  <a
                    href={project.sourceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-full border border-rose-100 bg-rose-50 px-2.5 py-1 text-[11px] font-semibold text-rose-600 transition-colors hover:bg-rose-100"
                    title="Open original on YouTube"
                  >
                    <ExternalLink className="h-3 w-3" />
                    YouTube
                  </a>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs font-medium text-slate-400">
                <span>
                  {new Date(project.createdAt).toLocaleDateString("en-US", {
                    month: "long",
                    day: "numeric",
                    year: "numeric",
                  })}
                </span>
                <span className="h-1 w-1 rounded-full bg-slate-200" />
                <span>
                  {clips.length} {clips.length === 1 ? "clip" : "clips"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Quality precision banner for low clip counts */}
        {clips.length < 5 && clips.length > 0 && (
          <div className="flex max-w-4xl items-start gap-3.5 rounded-2xl border border-[#0075de]/10 bg-[#e8f4fd]/30 px-5 py-4 shadow-sm">
            <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-[#0075de]/10 text-[#0075de]">
              <Sparkles className="h-4 w-4" />
            </div>
            <div className="space-y-1">
              <h4 className="text-sm leading-tight font-bold text-slate-900">
                Curated Viral Moments
              </h4>
              <p className="text-xs leading-relaxed font-medium text-slate-600">
                We found {clips.length} clip{clips.length === 1 ? "" : "s"} with
                strong viral potential — we skip the rest so every clip you get
                is worth posting.
              </p>
            </div>
          </div>
        )}

        {/* CLIPS LIST — horizontal cards */}
        <div className="flex flex-col gap-4">
          {clips.map((clip, index) => {
            const isCaptioned = showCaptions[clip.id] ?? true

            return (
              <ClipCard
                key={clip.id}
                clip={clip}
                index={index}
                isCaptioned={isCaptioned}
                isFree={_userData.plan === "free"}
                onToggleCaptions={(clipId) =>
                  setShowCaptions((prev) => ({
                    ...prev,
                    [clipId]: !(prev[clipId] ?? true),
                  }))
                }
                onEdit={(c) => setActiveEditClip(c)}
                onDownload={(c) => handleDownloadClick(c)}
                isPlaying={activePlayingId === clip.id}
                onPlay={() =>
                  setActivePlayingId(
                    activePlayingId === clip.id ? null : clip.id
                  )
                }
                isDownloading={downloadingClipId === clip.id}
                isExporting={exportingClipIds[clip.id]}
              />
            )
          })}
        </div>
      </div>
    )
  }

  return <ProcessingSteps project={project} />
}

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

import { useUser } from "@clerk/nextjs"

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
  const { user: clerkUser } = useUser()
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

  const triggerDirectDownload = async (url: string, clipTitle?: string) => {
    try {
      const response = await fetch(url)
      if (!response.ok) throw new Error("Fetch failed")
      const blob = await response.blob()
      const blobUrl = window.URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = blobUrl

      const safeTitle = (project.title || "video").replace(/[^a-z0-9]/gi, "_").toLowerCase()
      const safeClipTitle = (clipTitle || "clip").replace(/[^a-z0-9]/gi, "_").toLowerCase()
      link.download = `${safeTitle}_${safeClipTitle}.mp4`

      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(blobUrl)
      return true
    } catch (err) {
      console.error("Direct download failed, using fallback:", err)
      window.open(url, "_blank", "noopener,noreferrer")
      return false
    }
  }

  const handleDownloadClick = async (clip: Clip, options?: { withoutCaptions?: boolean }) => {
    // If download without captions is requested
    if (options?.withoutCaptions && clip.originalVideoUrl) {
      setDownloadingClipId(clip.id)
      const toastId = toast.loading("Downloading video...")
      const success = await triggerDirectDownload(clip.originalVideoUrl, `${clip.title}_original`)
      toast.dismiss(toastId)
      if (success) {
        toast.success("Download started.")
      } else {
        toast.success("Opening video in new tab.")
      }
      setDownloadingClipId(null)
      return
    }

    // If HD export already exists, download directly
    if (clip.captionVideoUrl) {
      setDownloadingClipId(clip.id)
      const toastId = toast.loading("Downloading video directly...")
      const success = await triggerDirectDownload(clip.captionVideoUrl, clip.title)
      toast.dismiss(toastId)
      if (success) {
        toast.success("Download started!")
      } else {
        toast.success("Opening clip in new tab (fallback)!")
      }
      setDownloadingClipId(null)
      return
    }

    // Otherwise trigger HD export
    const loadingToastId = toast.loading("Queuing HD export...")
    try {
      const data = await triggerHDExport(clip.id)

      // If the export was already done, download directly
      if (data.alreadyExported && data.url) {
        toast.dismiss(loadingToastId)
        setDownloadingClipId(clip.id)
        const toastId = toast.loading("Downloading video directly...")
        const success = await triggerDirectDownload(data.url, clip.title)
        toast.dismiss(toastId)
        if (success) {
          toast.success("Download started!")
        } else {
          toast.success("Opening clip in new tab (fallback)!")
        }
        setDownloadingClipId(null)
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

            toast.success("Export ready! Downloading...")
            void triggerDirectDownload(newClip.captionVideoUrl!, oldClip.title)
          }
        })

        // Preserve fields the polling endpoint doesn't include (sourceUrl/isYouTube)
        setProject((prev) => {
          if (prev.status !== "ready" && finalData.project.status === "ready") {
            // Fetch updated credits/user info when processing completes
            clerkUser?.reload()
            if (
              typeof window !== "undefined" &&
              "Notification" in window &&
              Notification.permission === "granted"
            ) {
              new Notification("Kivio", {
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
            We couldn&apos;t process this video. If credits were deducted, they have been refunded.
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
      <div className="mx-auto w-full max-w-4xl space-y-4 sm:px-4 sm:py-4 md:space-y-6 md:py-6">
        {/* HEADER — minimal */}
        <div className="flex flex-col justify-between gap-3 pb-1 md:flex-row md:items-center">
          <div className="flex min-w-0 items-start gap-1">
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
                    className="inline-flex items-center gap-1 rounded-full border border-rose-100 bg-rose-50 px-2 py-0.5 text-[10px] font-semibold text-rose-600 transition-colors hover:bg-rose-100"
                    title="Open original on YouTube"
                  >
                    <ExternalLink className="h-3 w-3" />
                    YouTube
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* CLIPS LIST — horizontal cards */}
        <div className="flex flex-col gap-4">
          {clips
            .filter((clip) => clip.status !== "error")
            .map((clip, index) => {
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
                  onDownload={(c, opts) => handleDownloadClick(c, opts)}
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

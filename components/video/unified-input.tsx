"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { useRouter } from "next/navigation"
import { Upload, Sparkles, Info, X, Video, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { toast } from "sonner"
import { useAuth } from "@clerk/nextjs"
import { useDashboardUser } from "@/components/dashboard-context"
import { getPlanLimit } from "@/lib/config"
import { ConfirmDialog, type SingleClipOptions } from "./confirm-dialog"
import { CaptionTemplate } from "./caption_templates"
import { normalizeVideoUrl } from "@/lib/youtube"
import {
  detectPlatform,
  isSupportedVideoUrl,
  PLATFORM_INFO,
} from "@/lib/video-sources"
import {
  PlatformLogo,
  YouTubeLogo,
  GoogleDriveLogo,
  VimeoLogo,
  LoomLogo,
  TwitchLogo,
} from "./platform-logos"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

function formatDuration(seconds: number): string {
  if (isNaN(seconds) || seconds <= 0) return "0:00"
  const hrs = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  if (hrs > 0) {
    return `${hrs}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`
  }
  return `${mins}:${String(secs).padStart(2, "0")}`
}

const extractVideoThumbnailAndDuration = (
  file: File
): Promise<{ thumbnail: string; duration: number }> => {
  return new Promise((resolve) => {
    const video = document.createElement("video")
    video.preload = "metadata"
    video.muted = true
    video.playsInline = true

    const objectUrl = URL.createObjectURL(file)
    video.src = objectUrl

    let hasResolved = false
    const finish = (thumbnail: string, duration: number) => {
      if (hasResolved) return
      hasResolved = true
      URL.revokeObjectURL(objectUrl)
      resolve({ thumbnail, duration })
    }

    const timeout = setTimeout(() => {
      finish("", video.duration || 0)
    }, 4000)

    video.onloadedmetadata = () => {
      const duration = video.duration || 0
      const seekTime = duration > 2 ? 1 : Math.max(0.1, duration * 0.2)
      video.currentTime = seekTime
    }

    video.onseeked = () => {
      try {
        const canvas = document.createElement("canvas")
        canvas.width = Math.min(video.videoWidth || 320, 640)
        canvas.height = Math.min(video.videoHeight || 180, 360)
        const ctx = canvas.getContext("2d")
        if (ctx) {
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
          const dataUrl = canvas.toDataURL("image/jpeg", 0.8)
          clearTimeout(timeout)
          finish(dataUrl, video.duration || 0)
          return
        }
      } catch (err) {
        console.error("Failed to capture video thumbnail:", err)
      }
      clearTimeout(timeout)
      finish("", video.duration || 0)
    }

    video.onerror = () => {
      clearTimeout(timeout)
      finish("", 0)
    }
  })
}

type UnifiedInputProps = {
  onUrlSubmit?: (
    url: string,
    styling: CaptionTemplate,
    transcribeLanguage?: string,
    translateLanguage?: string,
    duration?: number | null,
    title?: string | null,
    removeSilence?: boolean,
    singleClipOptions?: SingleClipOptions
  ) => Promise<boolean> | boolean | void
  onFileSelect?: (
    file: File,
    styling: CaptionTemplate,
    transcribeLanguage?: string,
    translateLanguage?: string,
    removeSilence?: boolean,
    singleClipOptions?: SingleClipOptions
  ) => Promise<void> | void
  isSubmitting?: boolean
  className?: string
  placeholder?: string
}

export function UnifiedInput({
  onUrlSubmit,
  onFileSelect,
  isSubmitting = false,
  className,
  placeholder = "Drop a file or paste a video link…",
}: UnifiedInputProps) {
  const router = useRouter()
  const { isSignedIn } = useAuth()
  const { user } = useDashboardUser()
  const [youtubeUrl, setYoutubeUrl] = useState("")
  const [isDragging, setIsDragging] = useState(false)
  const [localSubmitting, setLocalSubmitting] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [thumbnail, setThumbnail] = useState<string | null>(null)
  const [videoTitle, setVideoTitle] = useState<string | null>(null)
  const [videoDuration, setVideoDuration] = useState<number | null>(null)
  const [fetchingMetadata, setFetchingMetadata] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const urlInputRef = useRef<HTMLInputElement>(null)
  const lastAutoOpenedUrlRef = useRef("")

  // Trigger file picker from URL query param (landing-page redirect)
  useEffect(() => {
    if (typeof window === "undefined") return
    const params = new URLSearchParams(window.location.search)
    if (params.get("triggerUpload") === "true") {
      window.history.replaceState({}, document.title, window.location.pathname)
      setTimeout(() => fileInputRef.current?.click(), 300)
    }
  }, [])

  const isSubmittingState = isSubmitting || localSubmitting

  const detectedPlatform = detectPlatform(youtubeUrl)

  const isUrlValid = (() => {
    let u = youtubeUrl.trim()
    if (!/^https?:\/\//i.test(u)) u = `https://${u}`
    return isSupportedVideoUrl(u)
  })()

  // Auto-extract thumbnail and metadata as soon as URL becomes valid
  useEffect(() => {
    let u = youtubeUrl.trim()
    if (!/^https?:\/\//i.test(u)) u = `https://${u}`
    if (!isSupportedVideoUrl(u)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setThumbnail(null)
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setVideoTitle(null)
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setVideoDuration(null)
      return
    }

    // Instant thumbnail if YouTube
    const match = u.match(
      /[?&]v=([a-zA-Z0-9_-]{11})|youtu\.be\/([a-zA-Z0-9_-]{11})|shorts\/([a-zA-Z0-9_-]{11})/
    )
    const id = match?.[1] ?? match?.[2] ?? match?.[3]
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (id) setThumbnail(`https://img.youtube.com/vi/${id}/mqdefault.jpg`)

    if (isSignedIn) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setFetchingMetadata(true)
      fetch("/api/video/metadata", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: u }),
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.success && data.metadata) {
            setVideoTitle(data.metadata.title)
            setVideoDuration(data.metadata.duration)
            if (data.metadata.thumbnail) {
              setThumbnail(data.metadata.thumbnail)
            }
          }
        })
        .catch((err) => console.error("Error fetching metadata:", err))
        .finally(() => setFetchingMetadata(false))
    }
  }, [youtubeUrl, isSignedIn])

  // Auto-open dialog when a valid URL is entered
  useEffect(() => {
    let u = youtubeUrl.trim()
    if (!/^https?:\/\//i.test(u)) u = `https://${u}`

    if (isSupportedVideoUrl(u)) {
      if (
        !dialogOpen &&
        !isSubmittingState &&
        !pendingFile &&
        lastAutoOpenedUrlRef.current !== u
      ) {
        lastAutoOpenedUrlRef.current = u
        setYoutubeUrl(u)
        setPendingFile(null)
        setDialogOpen(true)
      }
    } else {
      lastAutoOpenedUrlRef.current = ""
    }
  }, [youtubeUrl, dialogOpen, isSubmittingState, pendingFile])

  const requireAuth = (action: () => void) => {
    if (!isSignedIn) {
      toast.error("Please log in to continue", {
        description: "You need to be logged in to generate viral clips.",
      })
      try {
        sessionStorage.setItem("pending_youtube_url", youtubeUrl)
      } catch { }
      router.push("/projects")
      return
    }
    action()
  }

  const openDialogForUrl = useCallback(() => {
    let u = youtubeUrl.trim()
    if (!/^https?:\/\//i.test(u)) u = `https://${u}`
    if (!isSupportedVideoUrl(u)) return
    setYoutubeUrl(u)
    setPendingFile(null)
    setDialogOpen(true)
  }, [youtubeUrl])

  const clearSelection = useCallback(() => {
    setPendingFile(null)
    setThumbnail(null)
    setVideoTitle(null)
    setVideoDuration(null)
    setYoutubeUrl("")
    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
  }, [])

  const clearUrl = useCallback(() => {
    setYoutubeUrl("")
    setThumbnail(null)
    setVideoTitle(null)
    setVideoDuration(null)
    lastAutoOpenedUrlRef.current = ""
    urlInputRef.current?.focus()
  }, [])

  const processFile = async (file: File) => {
    const ACCEPTED = [
      "video/mp4",
      "video/quicktime",
      "video/webm",
      "video/x-msvideo",
      "video/x-matroska",
    ]
    if (!ACCEPTED.includes(file.type)) {
      toast.error("Invalid file type", {
        description: "Please upload MP4, MOV, WebM, AVI, or MKV.",
      })
      return
    }

    setPendingFile(file)
    setVideoTitle(file.name)
    setYoutubeUrl("")
    setDialogOpen(true)
    setFetchingMetadata(true)

    try {
      const { thumbnail: thumb, duration } = await extractVideoThumbnailAndDuration(file)
      setThumbnail(thumb || null)
      setVideoDuration(duration || null)
    } catch (err) {
      console.error("Error generating video preview:", err)
      setVideoDuration(null)
    } finally {
      setFetchingMetadata(false)
    }
  }

  const handleGenerateClick = () => {
    if (pendingFile) {
      requireAuth(() => setDialogOpen(true))
    } else if (isUrlValid) {
      requireAuth(openDialogForUrl)
    }
  }

  const handleConfirm = async (
    styling: CaptionTemplate,
    transcribeLang: string,
    translateLang: string,
    removeSilence: boolean,
    singleClipOptions?: SingleClipOptions
  ) => {
    requireAuth(async () => {
      if (pendingFile) {
        setDialogOpen(false)
        if (onFileSelect)
          await onFileSelect(
            pendingFile,
            styling,
            transcribeLang,
            translateLang,
            removeSilence,
            singleClipOptions
          )
        return
      }
      if (onUrlSubmit) {
        const normalizedUrl = normalizeVideoUrl(youtubeUrl)
        const success = await onUrlSubmit(
          normalizedUrl,
          styling,
          transcribeLang,
          translateLang,
          videoDuration,
          videoTitle,
          removeSilence,
          singleClipOptions
        )
        if (success) {
          setDialogOpen(false)
        }
      } else {
        setLocalSubmitting(true)
        try {
          sessionStorage.setItem("pending_youtube_url", normalizeVideoUrl(youtubeUrl))
          sessionStorage.setItem("pending_caption_styling", JSON.stringify(styling))
          sessionStorage.setItem("pending_transcribe_language", transcribeLang)
          sessionStorage.setItem("pending_translate_language", translateLang)
          sessionStorage.setItem("pending_remove_silence", removeSilence ? "true" : "false")
          if (videoDuration != null) {
            sessionStorage.setItem("pending_video_duration", String(videoDuration))
          }
          if (videoTitle) {
            sessionStorage.setItem("pending_video_title", videoTitle)
          }
          router.push("/projects")
          setDialogOpen(false)
        } catch {
        } finally {
          setLocalSubmitting(false)
        }
      }
    })
  }

  return (
    <>
      <div className={cn("mx-auto w-full max-w-2xl", className)}>
        <input
          ref={fileInputRef}
          type="file"
          accept="video/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) processFile(f)
          }}
        />

        {/* Single Unified Capsule Container (Klap layout) */}
        <div
          onDragOver={(e) => {
            e.preventDefault()
            setIsDragging(true)
          }}
          onDragEnter={(e) => {
            e.preventDefault()
            setIsDragging(true)
          }}
          onDragLeave={(e) => {
            e.preventDefault()
            if (!e.currentTarget.contains(e.relatedTarget as Node)) {
              setIsDragging(false)
            }
          }}
          onDrop={(e) => {
            e.preventDefault()
            setIsDragging(false)
            const file = e.dataTransfer.files?.[0]
            if (file) processFile(file)
          }}
          className={cn(
            "group relative flex w-full items-center rounded-2xl border bg-white p-1.5 sm:p-2 transition-all duration-200 shadow-[0_4px_20px_rgba(0,0,0,0.06)]",
            isDragging
              ? "border-2 border-dashed border-primary bg-primary/[0.03] scale-[1.01] shadow-lg shadow-primary/10"
              : "border-slate-200/90 hover:border-slate-300 focus-within:border-primary focus-within:ring-4 focus-within:ring-primary/15"
          )}
        >
          {/* Drag Overlay */}
          {isDragging && (
            <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center gap-2.5 rounded-2xl bg-white/95 backdrop-blur-sm text-primary font-semibold text-sm sm:text-base animate-in fade-in duration-150">
              <Upload className="h-5 w-5 animate-bounce" />
              <span>Drop your video file to start</span>
            </div>
          )}

          {/* Left Upload Icon Button (shown when no video is selected) */}
          {!pendingFile && (
            <TooltipProvider delayDuration={200}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="flex h-10 w-10 sm:h-11 sm:w-11 shrink-0 items-center justify-center rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100/80 active:scale-95 transition-all duration-150"
                    aria-label="Upload video file"
                  >
                    <Upload className="h-5 w-5" strokeWidth={2} />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="top" className="text-xs bg-slate-900 text-white rounded-lg px-2.5 py-1">
                  Upload video file (or drop anywhere)
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}

          {/* Middle: Either Dropped Video Preview Card OR URL Input */}
          {pendingFile ? (
            <div className="flex min-w-0 flex-1 items-center gap-3 py-0.5 pl-1 pr-2 animate-in fade-in zoom-in-95 duration-200">
              {/* Video Thumbnail with Klap-Style Duration Badge */}
              <div className="relative h-12 w-20 sm:h-13 sm:w-24 shrink-0 overflow-hidden rounded-xl border border-slate-200/80 bg-slate-900 shadow-sm">
                {thumbnail ? (
                  <img
                    src={thumbnail}
                    alt={pendingFile.name}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center bg-slate-100 text-slate-400">
                    {fetchingMetadata ? (
                      <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    ) : (
                      <Video className="h-5 w-5" />
                    )}
                  </div>
                )}

                {/* Duration Badge in Bottom-Right */}
                {videoDuration != null && (
                  <div className="absolute bottom-1 right-1 rounded bg-black/80 px-1.5 py-0.5 text-[10px] sm:text-[11px] font-bold text-white tracking-wider backdrop-blur-xs">
                    {formatDuration(videoDuration)}
                  </div>
                )}
              </div>

              {/* File Info */}
              <div className="flex min-w-0 flex-1 flex-col justify-center">
                <span className="truncate text-sm font-semibold text-slate-800">
                  {pendingFile.name}
                </span>
                <span className="text-xs text-slate-500 font-medium">
                  {(pendingFile.size / (1024 * 1024)).toFixed(1)} MB
                  {videoDuration != null && ` • ${formatDuration(videoDuration)}`}
                  {fetchingMetadata && " • loading preview…"}
                </span>
              </div>

              {/* Clear Selection Button */}
              <button
                type="button"
                onClick={clearSelection}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
                title="Remove video"
                aria-label="Remove video"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <div className="flex min-w-0 flex-1 items-center">
              {detectedPlatform !== "unsupported" && (
                <div
                  title={PLATFORM_INFO[detectedPlatform].name}
                  className="ml-1.5 shrink-0 flex items-center justify-center animate-in fade-in zoom-in-95 duration-150"
                >
                  <PlatformLogo platform={detectedPlatform} className="h-4 w-4 sm:h-4.5 sm:w-4.5" />
                </div>
              )}
              <Input
                ref={urlInputRef}
                type="text"
                placeholder={placeholder}
                className={cn(
                  "h-10 sm:h-11 w-full flex-1 border-0 bg-transparent text-[14px] sm:text-[15px] font-normal text-slate-800 shadow-none placeholder:text-slate-400 focus:outline-none focus-visible:ring-0 focus-visible:ring-offset-0",
                  detectedPlatform !== "unsupported" ? "pl-2 pr-2 sm:pr-3" : "px-2 sm:px-3"
                )}
                value={youtubeUrl}
                onChange={(e) => setYoutubeUrl(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (isUrlValid || pendingFile) && !isSubmittingState)
                    handleGenerateClick()
                }}
              />
              {youtubeUrl && (
                <button
                  type="button"
                  onClick={clearUrl}
                  className="mr-1 sm:mr-1.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
                  title="Clear URL"
                  aria-label="Clear URL"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          )}

          {/* Right Action Button */}
          <Button
            onClick={handleGenerateClick}
            disabled={isSubmittingState || (!isUrlValid && !pendingFile)}
            className="flex h-10 sm:h-11 items-center justify-center rounded-xl bg-primary px-4 sm:px-6 font-semibold text-white shadow-sm transition-all duration-200 hover:bg-primary-active active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40 text-xs sm:text-sm shrink-0 gap-1.5"
          >
            <Sparkles className="h-4 w-4" />
            <span>{isSubmittingState ? "Generating…" : "Generate"}</span>
          </Button>
        </div>
        {detectedPlatform !== "unsupported" && PLATFORM_INFO[detectedPlatform]?.hint ? (
          <p className="mt-1.5 text-center text-xs text-amber-600/90 font-medium animate-in fade-in duration-200">
            💡 {PLATFORM_INFO[detectedPlatform].hint}
          </p>
        ) : !youtubeUrl && !pendingFile ? (
          <div className="mt-2.5 flex items-center justify-center gap-2 text-xs text-slate-400 select-none">
            <span className="text-[11px] font-medium text-slate-400/80">Supports</span>
            <div className="flex items-center gap-2">
              <span title="YouTube" className="flex items-center justify-center h-5 w-5 rounded hover:scale-110 transition-transform cursor-default">
                <YouTubeLogo className="h-4 w-4" />
              </span>
              <span title="Google Drive" className="flex items-center justify-center h-5 w-5 rounded hover:scale-110 transition-transform cursor-default">
                <GoogleDriveLogo className="h-4 w-4" />
              </span>
              <span title="Vimeo" className="flex items-center justify-center h-5 w-5 rounded hover:scale-110 transition-transform cursor-default">
                <VimeoLogo className="h-4 w-4" />
              </span>
              <span title="Loom" className="flex items-center justify-center h-5 w-5 rounded hover:scale-110 transition-transform cursor-default">
                <LoomLogo className="h-4 w-4" />
              </span>
              <span title="Twitch" className="flex items-center justify-center h-5 w-5 rounded hover:scale-110 transition-transform cursor-default">
                <TwitchLogo className="h-4 w-4" />
              </span>
            </div>
          </div>
        ) : null}
      </div>

      <ConfirmDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onConfirm={handleConfirm}
        isSubmitting={isSubmittingState}
        thumbnail={thumbnail}
        videoTitle={videoTitle}
        duration={videoDuration}
        fetchingMetadata={fetchingMetadata}
        videoFile={pendingFile}
      />
    </>
  )
}

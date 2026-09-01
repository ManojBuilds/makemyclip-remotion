"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { useRouter } from "next/navigation"
import { Upload, Sparkles, Info } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { toast } from "sonner"
import { useAuth } from "@clerk/nextjs"
import { useDashboardUser } from "@/components/dashboard-context"
import { getPlanLimit } from "@/lib/config"
import { ConfirmDialog } from "./confirm-dialog"
import { CaptionTemplate } from "./caption_templates"
import { normalizeVideoUrl } from "@/lib/youtube"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

const isValidYoutubeUrl = (url: string): boolean => {
  if (!url) return false
  const normalized = normalizeVideoUrl(url)
  const re =
    /^(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch\?(?:.*&)?v=|embed\/|shorts\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/
  return re.test(normalized)
}

type UnifiedInputProps = {
  onUrlSubmit?: (
    url: string,
    styling: CaptionTemplate,
    transcribeLanguage?: string,
    translateLanguage?: string,
    duration?: number | null,
    title?: string | null,
    removeSilence?: boolean
  ) => Promise<boolean> | boolean | void
  onFileSelect?: (
    file: File,
    styling: CaptionTemplate,
    transcribeLanguage?: string,
    translateLanguage?: string,
    removeSilence?: boolean
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
  placeholder = "Drop a video link",
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

  const isUrlValid = (() => {
    let u = youtubeUrl.trim()
    if (!/^https?:\/\//i.test(u)) u = `https://${u}`
    return isValidYoutubeUrl(u)
  })()

  // Auto-extract YouTube thumbnail and metadata as soon as URL becomes valid
  useEffect(() => {
    let u = youtubeUrl.trim()
    if (!/^https?:\/\//i.test(u)) u = `https://${u}`
    if (!isValidYoutubeUrl(u)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setThumbnail(null)
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setVideoTitle(null)
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setVideoDuration(null)
      return
    }
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
          }
        })
        .catch((err) => console.error("Error fetching metadata:", err))
        .finally(() => setFetchingMetadata(false))
    }
  }, [youtubeUrl, isSignedIn])

  // Auto-open dialog when a valid YouTube URL is entered
  useEffect(() => {
    let u = youtubeUrl.trim()
    if (!/^https?:\/\//i.test(u)) u = `https://${u}`

    if (isValidYoutubeUrl(u)) {
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
      router.push("/login")
      return
    }
    action()
  }

  const openDialogForUrl = useCallback(() => {
    let u = youtubeUrl.trim()
    if (!/^https?:\/\//i.test(u)) u = `https://${u}`
    if (!isValidYoutubeUrl(u)) return
    setYoutubeUrl(u)
    setPendingFile(null)
    setDialogOpen(true)
  }, [youtubeUrl])

  const openDialogForFile = useCallback((file: File) => {
    setPendingFile(file)
    setThumbnail(null)
    setVideoTitle(file.name)
    setDialogOpen(true)
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
    setVideoDuration(null)
    openDialogForFile(file)

    try {
      const duration = await new Promise<number>((resolve, reject) => {
        const video = document.createElement("video")
        video.preload = "metadata"
        video.onloadedmetadata = () => {
          resolve(video.duration)
          URL.revokeObjectURL(video.src)
        }
        video.onerror = () => reject(new Error("Could not read video metadata"))
        video.src = URL.createObjectURL(file)
      })
      setVideoDuration(duration)
    } catch (err) {
      console.error("Error reading file duration:", err)
      setVideoDuration(null)
    }
  }

  const handleConfirm = async (
    styling: CaptionTemplate,
    transcribeLang: string,
    translateLang: string,
    removeSilence: boolean
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
            removeSilence
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
          removeSilence
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
      <div className="mx-auto w-full max-w-4xl">
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

        <div
          onDragOver={(e) => {
            e.preventDefault()
            setIsDragging(true)
          }}
          onDragLeave={(e) => {
            e.preventDefault()
            setIsDragging(false)
          }}
          onDrop={(e) => {
            e.preventDefault()
            setIsDragging(false)
            const file = e.dataTransfer.files?.[0]
            if (file) processFile(file)
          }}
          className={cn(
            "flex flex-col items-center gap-4 w-full sm:flex-row sm:gap-6",
            className
          )}
        >
          {/* Main URL Input Capsule Wrapper */}
          <div
            className="w-full sm:flex-1 rounded-full bg-white transition-all duration-300"
            style={{
              border: '6px solid #0075de33',
              padding: '1px'
            }}
          >
            <div
              className={cn(
                "relative flex w-full items-center rounded-full border border-primary bg-white p-1.5 transition-all duration-300 pl-4 sm:pl-6",
                isDragging
                  ? "border-dashed border-primary bg-primary/5 scale-[1.01]"
                  : "focus-within:border-primary-active focus-within:ring-[3px] focus-within:ring-primary/20"
              )}
            >
              <Input
                type="text"
                placeholder={placeholder}
                className="h-auto w-full flex-1 border-0 bg-transparent px-1 py-2 sm:py-3 text-[14px] sm:text-[15px] text-slate-700 shadow-none placeholder:text-slate-400 focus:outline-none focus-visible:ring-0 focus-visible:ring-offset-0"
                value={youtubeUrl}
                onChange={(e) => setYoutubeUrl(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && isUrlValid && !isSubmittingState)
                    requireAuth(openDialogForUrl)
                }}
              />

              <Button
                onClick={() => requireAuth(openDialogForUrl)}
                disabled={isSubmittingState || !isUrlValid}
                className="flex h-9 sm:h-11 items-center justify-center rounded-full border-0 bg-primary px-4 sm:px-7 font-semibold text-white shadow-sm transition-all duration-200 hover:bg-primary-active active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 text-xs sm:text-sm"
              >
                <span>{isSubmittingState ? "Generating…" : "Get free clips"}</span>
              </Button>
            </div>
          </div>

          {/* Separator */}
          <span className="text-[14px] sm:text-[15px] font-medium text-slate-400/90">or</span>

          {/* Upload Button */}
          <Button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="flex h-12 sm:h-14 w-full sm:w-auto items-center justify-center rounded-full border border-slate-200 bg-white px-8 font-semibold text-slate-800 shadow-[0_4px_12px_rgba(0,0,0,0.03)] transition-all duration-200 hover:bg-slate-50 hover:border-slate-300 hover:shadow-[0_6px_16px_rgba(0,0,0,0.06)] active:scale-[0.98] text-sm sm:text-base"
          >
            <span>Upload files</span>
          </Button>
        </div>
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
      />
    </>
  )
}

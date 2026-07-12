"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { useRouter } from "next/navigation"
import { Upload, Sparkles, Info } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { toast } from "sonner"
import { useSession } from "@/lib/auth-client"
import { useDashboardUser } from "@/components/dashboard-context"
import { getPlanLimit } from "@/lib/config"
import { ConfirmDialog } from "./confirm-dialog"
import { CaptionTemplate } from "./caption_templates"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

const isValidYoutubeUrl = (url: string): boolean => {
  if (!url) return false
  const re =
    /^(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch\?(?:.*&)?v=|embed\/|shorts\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/
  return re.test(url.trim())
}

type UnifiedInputProps = {
  onUrlSubmit?: (
    url: string,
    styling: CaptionTemplate,
    transcribeLanguage?: string,
    translateLanguage?: string,
    duration?: number | null,
    title?: string | null
  ) => Promise<boolean> | boolean | void
  onFileSelect?: (
    file: File,
    styling: CaptionTemplate,
    transcribeLanguage?: string,
    translateLanguage?: string
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
  placeholder = "Paste YouTube link or drop a file",
}: UnifiedInputProps) {
  const router = useRouter()
  const { data: session } = useSession()
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

    if (session) {
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
  }, [youtubeUrl, session])

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
    if (!session) {
      toast.error("Please log in to continue", {
        description: "You need to be logged in to generate viral clips.",
      })
      try {
        sessionStorage.setItem("pending_youtube_url", youtubeUrl)
      } catch {}
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
    translateLang: string
  ) => {
    requireAuth(async () => {
      if (pendingFile) {
        setDialogOpen(false)
        if (onFileSelect)
          await onFileSelect(
            pendingFile,
            styling,
            transcribeLang,
            translateLang
          )
        return
      }
      if (onUrlSubmit) {
        const success = await onUrlSubmit(
          youtubeUrl,
          styling,
          transcribeLang,
          translateLang,
          videoDuration,
          videoTitle
        )
        if (success) {
          setDialogOpen(false)
        }
      } else {
        setLocalSubmitting(true)
        try {
          sessionStorage.setItem("pending_youtube_url", youtubeUrl)
          sessionStorage.setItem("pending_transcribe_language", transcribeLang)
          sessionStorage.setItem("pending_translate_language", translateLang)
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
            "relative flex w-full flex-col gap-2 rounded-xl border bg-white p-2 shadow-[0_15px_30px_-5px_rgba(0,0,0,0.05),0_8px_15px_-5px_rgba(0,0,0,0.03)] transition-all duration-300 focus-within:border-primary/50 focus-within:ring-4 focus-within:ring-primary/5 sm:flex-row sm:items-center sm:gap-0 sm:p-2 sm:pl-6",
            isDragging
              ? "scale-[1.01] border-dashed border-primary bg-primary/5"
              : "border-hairline hover:border-slate-300",
            className
          )}
        >
          <Input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) processFile(f)
            }}
          />

          <div className="flex w-full flex-1 items-center pl-2 sm:pl-0">
            <Upload
              className="mr-3 h-5 w-5 flex-shrink-0 cursor-pointer text-slate-400/80 transition-colors hover:text-primary"
              onClick={() => fileInputRef.current?.click()}
            />

            <Input
              type="text"
              placeholder={placeholder}
              className="h-auto w-full flex-1 border-0 bg-transparent px-1 py-3.5 text-[15px] text-slate-700 shadow-none placeholder:text-slate-400 focus:outline-none focus-visible:ring-0 focus-visible:ring-offset-0"
              value={youtubeUrl}
              onChange={(e) => setYoutubeUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && isUrlValid && !isSubmittingState)
                  requireAuth(openDialogForUrl)
              }}
            />

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="mr-1 h-7 w-7 flex-shrink-0 rounded-full p-0 text-slate-400 transition-colors hover:bg-transparent hover:text-slate-600 focus-visible:ring-0"
                  >
                    <Info className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent
                  side="top"
                  align="center"
                  className="max-w-[240px] rounded-lg border-none bg-slate-900 px-3 py-2 text-xs text-white shadow-md"
                >
                  <div className="space-y-1">
                    <p className="font-semibold text-slate-300">
                      Supported Links:
                    </p>
                    <ul className="list-disc pl-4 font-medium text-slate-100">
                      <li>YouTube (Videos, Shorts, Streams)</li>
                    </ul>
                    <p className="mt-1 text-[10px] text-slate-400">
                      Or upload MP4, MOV, WebM, AVI, MKV files directly.
                    </p>
                  </div>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>

          <Button
            onClick={() => requireAuth(openDialogForUrl)}
            disabled={isSubmittingState || !isUrlValid}
            className="flex h-12 w-full items-center justify-center gap-2 rounded-lg border-0 bg-primary px-6 font-semibold text-white shadow-sm transition-all duration-200 hover:bg-primary-active active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 sm:ml-2 sm:w-auto"
          >
            <Sparkles className="h-4 w-4" />
            <span>{isSubmittingState ? "Generating…" : "Generate"}</span>
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

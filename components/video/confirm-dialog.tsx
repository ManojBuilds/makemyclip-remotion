"use client"

import React, { useState, useEffect, useRef } from "react"
import { Sparkles, Check, Loader2, Lock, ChevronDown, Clock, Globe2, FileVideo, Play, ChevronLeft, ChevronRight, Video } from "lucide-react"
import { getTargetClipCount } from "@/lib/clip-utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useDashboardUser } from "@/components/dashboard-context"
import { getPlanLimit, PREVIEW_IMAGES, PREVIEW_VIDEOS, LANGUAGES } from "@/lib/config"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { UpgradeModal } from "@/components/ui/upgrade-modal"
import { hasDismissedPrompt } from "@/lib/upgrade-prompts"
import { cn } from "@/lib/utils"
import Image from "next/image"
import { CAPTION_TEMPLATES, CaptionTemplate } from "./caption_templates"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"


// Helper function to format duration in YouTube style (M:SS or H:MM:SS)
function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || isNaN(seconds) || seconds <= 0) return "0:00"
  const totalSecs = Math.max(0, Math.floor(seconds))
  const hrs = Math.floor(totalSecs / 3600)
  const mins = Math.floor((totalSecs % 3600) / 60)
  const secs = totalSecs % 60
  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
  }
  return `${mins}:${secs.toString().padStart(2, "0")}`
}

function formatShortSource(title: string | null | undefined): string {
  if (!title) return "Uploaded Video"
  return title.trim()
}

// ─── Caption Video Preview Card ───────────────────────────────────────────────

function TypographicPreview({ template }: { template: CaptionTemplate }) {
  const p = template.preview
  if (!p) return null

  return (
    <div
      className="absolute inset-0 flex flex-col items-center justify-center p-2 text-center select-none bg-gradient-to-b from-slate-900 via-slate-950 to-black"
      style={{ fontFamily: p.fontFamily }}
    >
      <div
        className={cn(
          "flex flex-wrap items-center justify-center gap-1.5 px-2 text-[12px] leading-tight font-black tracking-wide",
          p.italic && "italic",
          p.isUppercase && "uppercase"
        )}
      >
        {p.words.map((word, idx) => {
          if (!word) return null
          const isActive = idx === p.activeWordIndex

          if (isActive && p.badgeBg) {
            return (
              <span
                key={idx}
                className="rounded-full px-2 py-0.5 shadow-sm inline-block"
                style={{
                  backgroundColor: p.badgeBg,
                  color: p.highlightColor,
                  textShadow: p.strokeColor
                    ? `-1px -1px 0 ${p.strokeColor}, 1px -1px 0 ${p.strokeColor}, -1px 1px 0 ${p.strokeColor}, 1px 1px 0 ${p.strokeColor}, 0 2px 0 ${p.strokeColor}`
                    : undefined,
                }}
              >
                {word}
              </span>
            )
          }

          if (isActive && p.hasDoubleBorder) {
            return (
              <span
                key={idx}
                style={{
                  color: p.highlightColor,
                  textShadow:
                    "-1.5px -1.5px 0 #000, 1.5px -1.5px 0 #000, -1.5px 1.5px 0 #000, 1.5px 1.5px 0 #000",
                  filter: "drop-shadow(0 0 3px #FFFFFF)",
                }}
              >
                {word}
              </span>
            )
          }

          if (isActive && p.glowColor) {
            return (
              <span
                key={idx}
                style={{
                  color: "#FFFFFF",
                  textShadow: `0 0 8px ${p.glowColor}, 0 0 16px ${p.glowColor}`,
                }}
              >
                {word}
              </span>
            )
          }

          if (isActive) {
            return (
              <span
                key={idx}
                style={{
                  color: p.highlightColor,
                  textShadow: p.strokeColor
                    ? `-1.5px -1.5px 0 ${p.strokeColor}, 1.5px -1.5px 0 ${p.strokeColor}, -1.5px 1.5px 0 ${p.strokeColor}, 1.5px 1.5px 0 ${p.strokeColor}`
                    : undefined,
                }}
              >
                {word}
              </span>
            )
          }

          if (template.preset === "neon") {
            return (
              <span
                key={idx}
                style={{
                  color: "#00FFFF",
                  textShadow:
                    "-1px -1px 0 #003080, 1px 1px 0 #003080, 0 0 8px #00FFFF",
                }}
              >
                {word}
              </span>
            )
          }

          return (
            <span
              key={idx}
              style={{
                color: p.primaryColor,
                textShadow: p.strokeColor
                  ? `-1px -1px 0 ${p.strokeColor}, 1px -1px 0 ${p.strokeColor}, -1px 1px 0 ${p.strokeColor}, 1px 1px 0 ${p.strokeColor}`
                  : undefined,
              }}
            >
              {word}
            </span>
          )
        })}
      </div>
    </div>
  )
}

function CaptionPresetCard({
  id,
  template,
  selected,
  isLocked,
  onSelect,
}: {
  id: string
  template: CaptionTemplate
  selected: boolean
  isLocked: boolean
  onSelect: () => void
}) {
  const imageSrc = PREVIEW_IMAGES[id] || `/previews/caption_${id}.jpg`
  const videoSrc = PREVIEW_VIDEOS[id] || `/previews/caption_${id}.webm`
  const [isHovered, setIsHovered] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)

  const isPlaying = (isHovered || selected) && Boolean(videoSrc) && !isLocked

  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    video.muted = true
    video.defaultMuted = true

    if (isPlaying) {
      video.currentTime = 0
      const p = video.play()
      if (p !== undefined) {
        p.catch(() => {})
      }
    } else {
      video.pause()
    }
  }, [isPlaying, videoSrc])

  return (
    <div className="flex flex-col items-center gap-1.5 w-[140px] shrink-0 select-none">
      <button
        type="button"
        onClick={() => {
          onSelect()
          if (videoRef.current) {
            videoRef.current.muted = true
            videoRef.current.currentTime = 0
            videoRef.current.play().catch(() => {})
          }
        }}
        onMouseEnter={() => {
          setIsHovered(true)
          if (videoRef.current) {
            videoRef.current.muted = true
            videoRef.current.currentTime = 0
            videoRef.current.play().catch(() => {})
          }
        }}
        onMouseLeave={() => {
          setIsHovered(false)
          if (videoRef.current && !selected) {
            videoRef.current.pause()
          }
        }}
        className={cn(
          "group relative flex w-full flex-col overflow-hidden rounded-[16px] bg-black p-0 transition-all duration-180 ease-out focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563EB]",
          selected
            ? "border-[2.5px] border-[#2563EB] shadow-lg shadow-[#2563EB]/25 scale-[1.02] -translate-y-[1px]"
            : "border border-[#E5E7EB] hover:border-[#2563EB]/50 hover:shadow-md hover:-translate-y-[1px]"
        )}
      >
        {/* Selected badge with checkmark icon */}
        {selected && (
          <div className="absolute top-2 right-2 z-30 flex h-6 w-6 items-center justify-center rounded-full bg-[#2563EB] text-white shadow-md animate-in fade-in zoom-in-95 duration-180">
            <Check className="h-3.5 w-3.5 stroke-[3] animate-in zoom-in-50 duration-180" />
          </div>
        )}

        {/* Locked presets */}
        {isLocked && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/40 backdrop-blur-[2px]">
            <div className="absolute top-2 right-2 flex items-center gap-1 rounded-full bg-slate-900/90 px-1.5 py-0.5 text-[9px] font-bold text-amber-300 shadow-md">
              <Lock className="h-2.5 w-2.5" />
              <span>Pro</span>
            </div>
          </div>
        )}

        {/* Video or Typographic preview area (9:16 Reel format) */}
        <div className="relative aspect-[9/16] w-full overflow-hidden bg-slate-950">
          {imageSrc ? (
            <>
              <img
                src={imageSrc}
                alt={`${template.name} preview`}
                loading="lazy"
                onError={(e) => {
                  e.currentTarget.src = `/previews/caption_${id}.jpg`
                }}
                className={cn(
                  "pointer-events-none absolute inset-0 h-full w-full object-cover transition-opacity duration-200 z-0",
                  isLocked ? "blur-[1px] opacity-90" : "",
                  isPlaying ? "opacity-0" : "opacity-100"
                )}
              />
              {videoSrc && !isLocked && (
                <video
                  ref={(el) => {
                    if (el) {
                      el.muted = true
                      el.defaultMuted = true
                    }
                    videoRef.current = el
                  }}
                  src={videoSrc}
                  loop
                  muted
                  playsInline
                  preload="auto"
                  className={cn(
                    "pointer-events-none absolute inset-0 h-full w-full object-cover transition-opacity duration-200 z-10",
                    isPlaying ? "opacity-100" : "opacity-0"
                  )}
                />
              )}
            </>
          ) : (
            <TypographicPreview template={template} />
          )}

          {/* Preset Tag pill */}
          {template.tag && (
            <div className="absolute top-2 left-2 z-10 pointer-events-none">
              <span className="rounded-full bg-slate-950/80 px-2 py-0.5 text-[9px] font-semibold tracking-wide text-slate-200 backdrop-blur-sm border border-white/10">
                {template.tag}
              </span>
            </div>
          )}

          {/* Playing indicator */}
          {isPlaying && (
            <div className="absolute bottom-2 right-2 z-20 flex items-center gap-1.5 rounded-full bg-black/60 px-2 py-0.5 backdrop-blur-xs">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[9px] font-bold text-white uppercase tracking-wider">Play</span>
            </div>
          )}
        </div>
      </button>

      {/* Preset Name underneath */}
      <div className="flex flex-col items-center text-center leading-tight">
        <span className={cn(
          "text-[13px] font-semibold tracking-tight transition-colors duration-180 truncate max-w-[140px]",
          selected ? "text-[#2563EB]" : "text-slate-800"
        )}>
          {template.name}
        </span>
      </div>
    </div>
  )
}

// Helper to parse mm:ss or hh:mm:ss to seconds
function parseTimeToSeconds(timeStr: string, fallback: number): number {
  if (!timeStr) return fallback
  const parts = timeStr.trim().split(":").map(Number)
  if (parts.some(isNaN)) return fallback
  if (parts.length === 2) {
    return parts[0] * 60 + parts[1]
  }
  if (parts.length === 3) {
    return parts[0] * 3600 + parts[1] * 60 + parts[2]
  }
  if (parts.length === 1) {
    return parts[0]
  }
  return fallback
}

export type SingleClipOptions = {
  isSingleClip: boolean
  cropMode: "auto" | "split" | "letterbox" | "passthrough"
  startTime?: number
  endTime?: number
}

// ─── Confirm Dialog ───────────────────────────────────────────────────────────

interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: (
    styling: CaptionTemplate,
    transcribeLang: string,
    translateLang: string,
    removeSilence: boolean,
    singleClipOptions?: SingleClipOptions
  ) => void
  isSubmitting: boolean
  thumbnail?: string | null
  videoTitle?: string | null
  duration?: number | null
  fetchingMetadata?: boolean
  videoFile?: File | null
}

export function ConfirmDialog({
  open,
  onOpenChange,
  onConfirm,
  isSubmitting,
  thumbnail,
  videoTitle,
  duration,
  fetchingMetadata,
  videoFile,
}: ConfirmDialogProps) {
  const { user, status } = useDashboardUser()
  const isLoadingUser = status === "loading"
  const plan = user?.plan || "free"
  const isFree = isLoadingUser ? false : plan === "free"

  const [localThumbnail, setLocalThumbnail] = useState<string | null>(null)
  const [localDuration, setLocalDuration] = useState<number | null>(null)

  // Extract thumbnail and duration from videoFile if missing
  useEffect(() => {
    if (!open) {
      setLocalThumbnail(null)
      setLocalDuration(null)
      return
    }

    if (videoFile && (!thumbnail || duration == null)) {
      let isMounted = true
      const video = document.createElement("video")
      video.preload = "metadata"
      video.muted = true
      video.playsInline = true
      const objectUrl = URL.createObjectURL(videoFile)
      video.src = objectUrl

      video.onloadedmetadata = () => {
        if (!isMounted) return
        const d = video.duration || 0
        if (duration == null) {
          setLocalDuration(d)
        }
        const seekTime = d > 2 ? 1 : Math.max(0.1, d * 0.2)
        video.currentTime = seekTime
      }

      video.onseeked = () => {
        if (!isMounted) return
        try {
          const canvas = document.createElement("canvas")
          canvas.width = Math.min(video.videoWidth || 320, 640)
          canvas.height = Math.min(video.videoHeight || 180, 360)
          const ctx = canvas.getContext("2d")
          if (ctx) {
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
            const dataUrl = canvas.toDataURL("image/jpeg", 0.8)
            if (isMounted && !thumbnail) {
              setLocalThumbnail(dataUrl)
              setIsThumbnailLoading(false)
            }
          }
        } catch (err) {
          console.error("Error generating modal preview:", err)
        }
        URL.revokeObjectURL(objectUrl)
      }

      video.onerror = () => {
        URL.revokeObjectURL(objectUrl)
      }

      return () => {
        isMounted = false
        URL.revokeObjectURL(objectUrl)
      }
    }
  }, [open, videoFile, thumbnail, duration])

  const effectiveThumbnail = thumbnail || localThumbnail
  const effectiveDuration = duration != null ? duration : localDuration

  const planLimitConfig = getPlanLimit(plan)
  const limit = planLimitConfig.maxUploadDurationSeconds
  const limitLabel = planLimitConfig.label
  const isOverLimit = isLoadingUser ? false : (effectiveDuration ? effectiveDuration > limit : false)

  const [selectedTemplate, setSelectedTemplate] = useState<string>("impact")
  const [wordHighlight, setWordHighlight] = useState<boolean>(true)
  const [sourceLang, setSourceLang] = useState<string>("auto")
  const [translateLang, setTranslateLang] = useState<string>("none")
  const [removeSilence, setRemoveSilence] = useState<boolean>(true)
  const [isThumbnailLoading, setIsThumbnailLoading] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false)
  const [showCaptionStyle, setShowCaptionStyle] = useState<boolean>(true)

  // Mode Selection: "viral" (AI highlight detection) vs "single" (reframe & burn captions directly)
  // Reframe Full Video mode is strictly for development and not shipped to production (Vercel)
  const isReframeEnabled =
    process.env.NODE_ENV !== "production" ||
    process.env.NEXT_PUBLIC_ENABLE_REFRAME_TAB === "true"
  const [mode, setMode] = useState<"viral" | "single">("viral")
  const [cropMode, setCropMode] = useState<"auto" | "split" | "letterbox" | "passthrough">("auto")
  const [startTimeInput, setStartTimeInput] = useState<string>("0:00")
  const [endTimeInput, setEndTimeInput] = useState<string>("")

  const [activeUpgradeTrigger, setActiveUpgradeTrigger] = useState<string | null>(null)
  const presetScrollRef = useRef<HTMLDivElement>(null)

  const scrollPresets = (direction: "left" | "right") => {
    if (presetScrollRef.current) {
      const scrollAmount = direction === "left" ? -320 : 320
      presetScrollRef.current.scrollBy({ left: scrollAmount, behavior: "smooth" })
    }
  }

  useEffect(() => {
    if (open) {
      setSelectedTemplate("impact")
      setWordHighlight(CAPTION_TEMPLATES.impact?.wordHighlightDefault ?? true)
      setSourceLang("auto")
      setTranslateLang("none")
      setIsThumbnailLoading(
        Boolean(
          effectiveThumbnail &&
            !effectiveThumbnail.startsWith("data:") &&
            !effectiveThumbnail.startsWith("blob:")
        )
      )
      setRemoveSilence(true)
      setShowAdvanced(false)
      setShowCaptionStyle(true)
      setMode("viral")
      setCropMode("auto")
      setStartTimeInput("0:00")
      if (effectiveDuration) {
        setEndTimeInput(formatDuration(effectiveDuration))
      } else {
        setEndTimeInput("")
      }

      if (!isLoadingUser && isOverLimit && isFree && !hasDismissedPrompt("upload_limit")) {
        setActiveUpgradeTrigger("upload_limit")
      }
    }
  }, [open, thumbnail, isOverLimit, isFree, isLoadingUser, effectiveDuration])

  const handleSelectPreset = (id: string) => {
    setSelectedTemplate(id)
    const tpl = CAPTION_TEMPLATES[id]
    if (tpl) {
      setWordHighlight(tpl.wordHighlightDefault)
    }
  }

  const handleConfirm = () => {
    if (isFree && isOverLimit) {
      setActiveUpgradeTrigger("upload_limit")
      return
    }

    const styling = CAPTION_TEMPLATES[selectedTemplate]
    if (styling) {
      const isSingle = isReframeEnabled && mode === "single"
      const totalDur = effectiveDuration || 0
      const parsedStart = parseTimeToSeconds(startTimeInput, 0)
      const parsedEnd = endTimeInput ? parseTimeToSeconds(endTimeInput, totalDur) : totalDur

      const singleOpts: SingleClipOptions | undefined = isSingle
        ? {
            isSingleClip: true,
            cropMode,
            startTime: Math.max(0, parsedStart),
            endTime: parsedEnd > parsedStart ? parsedEnd : undefined,
          }
        : undefined

      onConfirm(
        { ...styling, word_highlight: wordHighlight },
        sourceLang,
        translateLang,
        removeSilence,
        singleOpts
      )
    }
  }

  // Calculate estimated clips
  const clipEstimate = effectiveDuration ? getTargetClipCount(effectiveDuration) : { target: 3, max: 4 }
  const estimatedClipsText = `${clipEstimate.target}–${clipEstimate.max}`

  // Display language name for stat card
  const currentLangObj = LANGUAGES.find((l) => l.code === sourceLang)
  const displayLanguageName = sourceLang === "auto" ? "English" : (currentLangObj?.name || "English")
  const formattedDuration = formatDuration(effectiveDuration)
  const shortSourceTitle = formatShortSource(videoTitle)

  return (
    <>
      <UpgradeModal
        open={Boolean(activeUpgradeTrigger)}
        onOpenChange={(openState) => {
          if (!openState) setActiveUpgradeTrigger(null)
        }}
        triggerId={activeUpgradeTrigger}
      />

      <Dialog
        open={open}
        onOpenChange={(openState) => {
          if (isSubmitting) return
          onOpenChange(openState)
        }}
      >
        <DialogContent className="flex max-h-[85vh] flex-col gap-0 overflow-hidden rounded-[20px] border border-[#E5E7EB] bg-white p-0 shadow-2xl transition-all duration-180 sm:max-w-[600px]">
          {/* Header */}
          <DialogHeader className="shrink-0 p-6 pb-2 text-left">
            <DialogTitle className="text-xl font-bold tracking-tight text-slate-900">
              Create Shorts
            </DialogTitle>
            <DialogDescription className="mt-0.5 text-xs font-normal text-slate-500">
              Review your clip settings before generating.
            </DialogDescription>
          </DialogHeader>

          {/* Scrollable Content Body */}
          <div className="flex-1 min-h-0 space-y-7 overflow-y-auto overscroll-contain px-6 py-3">

            {/* 1. Video Section Preview (Centered, Matching Width, Duration on Right) */}
            <div className="mx-auto flex flex-col items-center justify-center w-full max-w-[280px] space-y-1.5 text-center">
              <div className="relative aspect-video w-full overflow-hidden rounded-xl bg-slate-950 shadow-xs">
                {effectiveThumbnail ? (
                  <div className="relative h-full w-full">
                    {effectiveThumbnail.startsWith("data:") ||
                    effectiveThumbnail.startsWith("blob:") ? (
                      <img
                        src={effectiveThumbnail}
                        alt="Video preview"
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <>
                        {isThumbnailLoading && (
                          <Skeleton className="absolute inset-0 h-full w-full" />
                        )}
                        <Image
                          src={effectiveThumbnail}
                          alt="Video preview"
                          fill
                          unoptimized
                          className="h-full w-full object-cover"
                          onLoad={() => setIsThumbnailLoading(false)}
                        />
                      </>
                    )}
                  </div>
                ) : (
                  <div className="flex h-full w-full flex-col items-center justify-center gap-1.5 bg-slate-900 text-slate-400">
                    {fetchingMetadata ? (
                      <>
                        <Loader2 className="h-5 w-5 animate-spin text-primary" />
                        <span className="text-xs font-medium text-slate-400">Loading preview…</span>
                      </>
                    ) : (
                      <>
                        <FileVideo className="h-7 w-7 stroke-[1.5] text-slate-500" />
                        <span className="text-xs font-medium text-slate-400">Video Source Ready</span>
                      </>
                    )}
                  </div>
                )}

                {/* Duration Badge (bottom-right with mm:ss) */}
                {effectiveDuration ? (
                  <div className="absolute bottom-2 right-2 rounded-md bg-black/85 px-1.5 py-0.5 text-[11px] font-bold text-white backdrop-blur-xs shadow-sm font-mono tracking-wider">
                    {formattedDuration}
                  </div>
                ) : null}
              </div>

              {/* Video Title - perfectly aligned to thumbnail width */}
              {videoTitle && (
                <div
                  className="w-full text-center text-xs font-semibold text-slate-800 truncate px-1"
                  title={videoTitle}
                >
                  {shortSourceTitle}
                </div>
              )}
            </div>

            {/* Plan limit alert if over limit */}
            {isOverLimit && (
              <div className="flex items-center justify-between rounded-[14px] border border-amber-200 bg-amber-50/80 p-3 text-amber-900 text-xs font-medium">
                <div>
                  Video exceeds your <span className="font-bold">{limitLabel}</span> plan limit.
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setActiveUpgradeTrigger("upload_limit")}
                  className="ml-2 h-7 shrink-0 rounded-lg border-amber-300 bg-white text-xs font-bold text-amber-900 hover:bg-amber-100"
                >
                  Upgrade Plan
                </Button>
              </div>
            )}

            {/* Mode Switcher: Find Viral Clips vs Reframe Full Video (Dev-only, hidden in production) */}
            {isReframeEnabled && (
              <div className="rounded-[14px] border border-[#E5E7EB] bg-slate-50 p-1.5">
                <div className="grid grid-cols-2 gap-1.5">
                  <button
                    type="button"
                    onClick={() => setMode("viral")}
                    className={cn(
                      "flex items-center justify-center gap-2 rounded-xl py-2 px-3 text-xs font-semibold transition-all cursor-pointer",
                      mode === "viral"
                        ? "bg-white text-slate-900 shadow-xs border border-slate-200/80 font-bold"
                        : "text-slate-500 hover:text-slate-900 hover:bg-white/50"
                    )}
                  >
                    <Sparkles className={cn("h-3.5 w-3.5", mode === "viral" ? "text-[#2563EB]" : "text-slate-400")} />
                    <span>Find Viral Clips</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setMode("single")}
                    className={cn(
                      "flex items-center justify-center gap-2 rounded-xl py-2 px-3 text-xs font-semibold transition-all cursor-pointer",
                      mode === "single"
                        ? "bg-white text-slate-900 shadow-xs border border-slate-200/80 font-bold"
                        : "text-slate-500 hover:text-slate-900 hover:bg-white/50"
                    )}
                  >
                    <Video className={cn("h-3.5 w-3.5", mode === "single" ? "text-emerald-600" : "text-slate-400")} />
                    <span>Reframe Full Video</span>
                    <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-200">
                      Dev
                    </span>
                  </button>
                </div>

                <p className="mt-1.5 text-center text-[11px] text-slate-500">
                  {mode === "viral"
                    ? "AI analyzes full video to discover viral moments"
                    : "Skips clip finding — reframes video directly with animated captions (Dev Only)"}
                </p>
              </div>
            )}

            {/* Single Video Mode Settings: Framing Layout & Optional Trim (Dev-only) */}
            {isReframeEnabled && mode === "single" && (
              <div className="rounded-[14px] border border-[#E5E7EB] bg-white p-4 space-y-4 animate-in fade-in-50 duration-180">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs font-semibold text-slate-800">
                      Framing Layout
                    </Label>
                    <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-100 uppercase">
                      9:16 Vertical
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    {[
                      { id: "auto", label: "Auto AI Tracking", desc: "Active speaker" },
                      { id: "split", label: "Split Screen", desc: "Dual speaker stack" },
                      { id: "letterbox", label: "Fit / Blur BG", desc: "Preserves 16:9" },
                      { id: "passthrough", label: "No Crop", desc: "Direct 9:16" },
                    ].map((layout) => (
                      <button
                        key={layout.id}
                        type="button"
                        onClick={() => setCropMode(layout.id as any)}
                        className={cn(
                          "flex flex-col items-start p-2.5 rounded-xl border text-left transition-all cursor-pointer",
                          cropMode === layout.id
                            ? "border-[#2563EB] bg-blue-50/50 text-[#2563EB] shadow-xs"
                            : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50/50"
                        )}
                      >
                        <span className="text-xs font-bold">{layout.label}</span>
                        <span className="text-[10px] text-slate-500 mt-0.5">{layout.desc}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Optional Trim */}
                <div className="pt-2 border-t border-slate-100">
                  <div className="flex items-center justify-between mb-1.5">
                    <Label className="text-xs font-semibold text-slate-800">
                      Clip Boundaries (Optional Trim)
                    </Label>
                    <span className="text-[11px] text-slate-400">
                      Format: MM:SS
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <span className="text-[10px] font-medium text-slate-500 mb-1 block">Start Time</span>
                      <Input
                        value={startTimeInput}
                        onChange={(e) => setStartTimeInput(e.target.value)}
                        placeholder="0:00"
                        className="h-8 text-xs font-mono"
                      />
                    </div>
                    <div>
                      <span className="text-[10px] font-medium text-slate-500 mb-1 block">End Time</span>
                      <Input
                        value={endTimeInput}
                        onChange={(e) => setEndTimeInput(e.target.value)}
                        placeholder={effectiveDuration ? formatDuration(effectiveDuration) : "End"}
                        className="h-8 text-xs font-mono"
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 3. Caption Style Section (Collapsible) */}
            <div className="rounded-[14px] border border-[#E5E7EB] bg-white overflow-hidden transition-all duration-180">
              <div className="flex items-center justify-between px-4 py-3 bg-white hover:bg-slate-50/50 transition-colors">
                <button
                  type="button"
                  onClick={() => setShowCaptionStyle(!showCaptionStyle)}
                  className="flex items-center gap-2 text-left text-xs font-semibold text-slate-700 focus:outline-none flex-1 py-0.5"
                >
                  <ChevronDown
                    className={cn(
                      "h-3.5 w-3.5 text-slate-400 transition-transform duration-180",
                      showCaptionStyle && "rotate-180"
                    )}
                  />
                  <span>Caption Style</span>
                  <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-bold text-[#2563EB] border border-blue-100">
                    {CAPTION_TEMPLATES[selectedTemplate]?.name || selectedTemplate}
                  </span>
                  <span className="text-[11px] font-normal text-slate-400">
                    ({Object.keys(CAPTION_TEMPLATES).length} styles)
                  </span>
                </button>

                {/* Back and Forward scroll navigation buttons */}
                {showCaptionStyle && (
                  <div className="flex items-center gap-1.5 shrink-0 ml-2">
                    <button
                      type="button"
                      onClick={() => scrollPresets("left")}
                      aria-label="Scroll presets left"
                      className="flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 shadow-xs transition-colors hover:bg-slate-100 hover:text-slate-900 active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563EB]"
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => scrollPresets("right")}
                      aria-label="Scroll presets right"
                      className="flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 shadow-xs transition-colors hover:bg-slate-100 hover:text-slate-900 active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563EB]"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </button>
                  </div>
                )}
              </div>

              {showCaptionStyle && (
                <div className="border-t border-slate-100 p-3 bg-slate-50/40">
                  <div
                    ref={presetScrollRef}
                    className="flex gap-3.5 overflow-x-auto pb-2.5 pt-1 px-1 scroll-smooth scrollbar-thin scrollbar-thumb-slate-200 scrollbar-track-transparent"
                  >
                    {Object.keys(PREVIEW_IMAGES).map((id) => {
                      const template = CAPTION_TEMPLATES[id]
                      if (!template) return null
                      return (
                        <CaptionPresetCard
                          key={id}
                          id={id}
                          template={template}
                          selected={selectedTemplate === id}
                          isLocked={false}
                          onSelect={() => handleSelectPreset(id)}
                        />
                      )
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* 4. Advanced Settings (Collapsible) */}
            <div className="rounded-[14px] border border-[#E5E7EB] bg-white overflow-hidden transition-all duration-180">
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex w-full items-center justify-between px-4 py-3 text-left text-xs font-semibold text-slate-700 hover:bg-slate-50/50 transition-colors"
              >
                <span>Advanced Settings</span>
                <ChevronDown
                  className={cn(
                    "h-3.5 w-3.5 text-slate-400 transition-transform duration-180",
                    showAdvanced && "rotate-180"
                  )}
                />
              </button>

              {showAdvanced && (
                <div className="border-t border-[#E5E7EB] p-4 space-y-3 animate-in fade-in-50 duration-180">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label className="mb-1.5 block text-[11px] font-semibold text-slate-600">
                        Source Language
                      </Label>
                      <Select value={sourceLang} onValueChange={setSourceLang}>
                        <SelectTrigger className="w-full rounded-lg border-[#E5E7EB] h-9 text-xs">
                          <SelectValue placeholder="Select language" />
                        </SelectTrigger>
                        <SelectContent position="popper" className="max-h-[220px] rounded-lg border-[#E5E7EB]">
                          <SelectItem value="auto">Auto Detect</SelectItem>
                          {LANGUAGES.map((lang) => (
                            <SelectItem key={`src-${lang.code}`} value={lang.code}>
                              {lang.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div>
                      <Label className="mb-1.5 block text-[11px] font-semibold text-slate-600">
                        Translate Captions
                      </Label>
                      <Select value={translateLang} onValueChange={setTranslateLang}>
                        <SelectTrigger className="w-full rounded-lg border-[#E5E7EB] h-9 text-xs">
                          <SelectValue placeholder="Select language" />
                        </SelectTrigger>
                        <SelectContent position="popper" className="max-h-[220px] rounded-lg border-[#E5E7EB]">
                          <SelectItem value="none">None (Don&apos;t Translate)</SelectItem>
                          {LANGUAGES.map((lang) => (
                            <SelectItem key={`trans-${lang.code}`} value={lang.code}>
                              {lang.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  {/* Word-Level Highlighting Toggle Switch */}
                  <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                    <div>
                      <Label htmlFor="word-highlight" className="block text-[11px] font-semibold text-slate-700 cursor-pointer">
                        Word-Level Highlighting
                      </Label>
                      <p className="text-[10px] text-slate-400">
                        Highlight active words individually during speech
                      </p>
                    </div>
                    <Switch
                      id="word-highlight"
                      checked={wordHighlight}
                      onCheckedChange={setWordHighlight}
                    />
                  </div>

                  {/* Remove Silence Toggle Switch */}
                  <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                    <div>
                      <Label htmlFor="remove-silence" className="block text-[11px] font-semibold text-slate-700 cursor-pointer">
                        Remove Silence
                      </Label>
                      <p className="text-[10px] text-slate-400">
                        Auto-cut dead air and long pauses for tighter clips
                      </p>
                    </div>
                    <Switch
                      id="remove-silence"
                      checked={removeSilence}
                      onCheckedChange={setRemoveSilence}
                    />
                  </div>
                </div>
              )}
            </div>

          </div>

          {/* Sticky Generate Button & Footer with Reassurance items */}
          <div className="shrink-0 border-t border-[#E5E7EB] bg-white p-4 pb-3 text-center shadow-lg">
            <Button
              onClick={handleConfirm}
              disabled={isSubmitting || isLoadingUser}
              className="h-11 w-full rounded-[14px] bg-[#2563EB] text-sm font-semibold text-white shadow-sm transition-all duration-180 hover:bg-[#1d4ed8] hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {isReframeEnabled && mode === "single" ? "Reframing Video…" : "Generating…"}
                </span>
              ) : isLoadingUser ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading…
                </span>
              ) : isOverLimit ? (
                "Upgrade to Process Video"
              ) : isReframeEnabled && mode === "single" ? (
                <span className="flex items-center justify-center gap-1.5">
                  <Video className="h-4 w-4" />
                  Reframe Video
                </span>
              ) : (
                <span className="flex items-center justify-center gap-1.5">
                  <Sparkles className="h-4 w-4" />
                  Generate Clips
                </span>
              )}
            </Button>

            {/* Subtext */}
            <p className="mt-1.5 text-[11px] font-medium text-slate-400">
              {isReframeEnabled && mode === "single"
                ? "1 Reframed Clip with Captions • Auto-downloads when ready"
                : `Est. ${estimatedClipsText} clips • Ready in ~2 minutes`}
            </p>

            {/* Reassurance section */}
            <div className="mt-2.5 flex items-center justify-center gap-4 text-[10px] font-medium text-slate-500">
              <span className="flex items-center gap-1">
                <Check className="h-3 w-3 text-[#2563EB] stroke-[2.5]" />
                {isReframeEnabled && mode === "single" ? "9:16 Vertical crop" : "AI detects highlights"}
              </span>
              <span className="flex items-center gap-1">
                <Check className="h-3 w-3 text-[#2563EB] stroke-[2.5]" />
                Auto speaker tracking
              </span>
              <span className="flex items-center gap-1">
                <Check className="h-3 w-3 text-[#2563EB] stroke-[2.5]" />
                Animated captions
              </span>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

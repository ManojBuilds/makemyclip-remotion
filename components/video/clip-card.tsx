"use client"

import { useState, useEffect, memo } from "react"
import { Button } from "@/components/ui/button"
import {
  Clock,
  Video,
  Loader2,
  Download,
  Check,
  Copy,
  Sparkles,
  Type,
  Play,
  Eye,
  Smartphone,
  ClosedCaption,
  ChevronDown,
  Scissors,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "sonner"
import type { Clip } from "@/lib/types"
import {
  trackClipDownloaded,
  trackCheckoutInitiated,
  trackClipRenderStarted,
} from "@/lib/posthog"
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

const CLIP_TYPE_MAP: Record<string, { label: string; classes: string }> = {
  hot_take: { label: "Hot Take", classes: "bg-rose-50 text-rose-600" },
  aha_moment: { label: "Aha Moment", classes: "bg-amber-50 text-amber-600" },
  funny_exchange: { label: "Banter", classes: "bg-violet-50 text-violet-600" },
  debate: { label: "Debate", classes: "bg-indigo-50 text-indigo-600" },
  storytelling: { label: "Story", classes: "bg-emerald-50 text-emerald-600" },
  quotable: { label: "Quotable", classes: "bg-sky-50 text-sky-600" },
  emotional: { label: "Vulnerable", classes: "bg-pink-50 text-pink-600" },
  mind_blowing_fact: {
    label: "Mind-Blowing",
    classes: "bg-fuchsia-50 text-fuchsia-600",
  },
}

const CLIP_THEME_MAP: Record<string, { gradient: string; iconColor: string }> =
{
  hot_take: {
    gradient: "from-rose-900/30 via-slate-950 to-rose-950/20",
    iconColor: "text-rose-400",
  },
  aha_moment: {
    gradient: "from-amber-900/30 via-slate-950 to-amber-950/20",
    iconColor: "text-amber-400",
  },
  funny_exchange: {
    gradient: "from-violet-900/30 via-slate-950 to-violet-950/20",
    iconColor: "text-violet-400",
  },
  debate: {
    gradient: "from-indigo-900/30 via-slate-950 to-indigo-950/20",
    iconColor: "text-indigo-400",
  },
  storytelling: {
    gradient: "from-emerald-900/30 via-slate-950 to-emerald-950/20",
    iconColor: "text-emerald-400",
  },
  quotable: {
    gradient: "from-sky-900/30 via-slate-950 to-sky-950/20",
    iconColor: "text-sky-400",
  },
  emotional: {
    gradient: "from-pink-900/30 via-slate-950 to-pink-950/20",
    iconColor: "text-pink-400",
  },
  mind_blowing_fact: {
    gradient: "from-fuchsia-900/30 via-slate-950 to-fuchsia-950/20",
    iconColor: "text-fuchsia-400",
  },
}

/* ─────────────────────────────────────────────
   Optimized native video preview with lazy loading.
   Only mounts the actual video player when the user
   clicks the Play button, keeping CPU & connections clean.
   ───────────────────────────────────────────── */
export function NativeVideoPreview({
  src,
  className,
  isPlaying,
  onPlay,
  clipType = "hot_take",
  posterUrl,
  duration,
}: {
  src: string
  className?: string
  isPlaying: boolean
  onPlay: () => void
  clipType?: string
  posterUrl?: string | null
  duration?: number
}) {
  const theme = CLIP_THEME_MAP[clipType] || CLIP_THEME_MAP.hot_take

  const previewBadge = (
    <div className="absolute top-3 left-3 z-30 flex items-center gap-1.5 select-none">
      <span className="inline-flex items-center gap-1 rounded-lg bg-black/60 px-2.5 py-1 text-[10px] font-bold text-white/95 backdrop-blur-sm">
        <Eye className="h-3.5 w-3.5" /> Preview
      </span>
      <span className="inline-flex items-center rounded-lg bg-black/60 px-2.5 py-1 text-[10px] font-bold text-white/95 backdrop-blur-sm">
        540p
      </span>
    </div>
  )

  const durationBadge = duration ? (
    <span className="absolute top-3 right-3 z-30 inline-flex items-center rounded-lg bg-black/60 px-2.5 py-1 text-[10px] font-bold text-white/95 backdrop-blur-sm select-none">
      {Math.round(duration)}s
    </span>
  ) : null

  if (isPlaying) {
    return (
      <div className={cn("relative h-full w-full bg-slate-950", className)}>
        {previewBadge}
        {durationBadge}
        <video
          src={src}
          poster={posterUrl || undefined}
          autoPlay
          controls
          playsInline
          className="h-full w-full object-cover bg-slate-950"
        />
      </div>
    )
  }

  return (
    <Button
      onClick={onPlay}
      type="button"
      variant="ghost"
      className={cn(
        "group/preview relative block flex h-full w-full flex-col items-center justify-center overflow-hidden p-0 transition-all duration-500 hover:bg-transparent",
        className
      )}
    >
      {previewBadge}
      {durationBadge}
      {/* Background Gradient & Pattern or Poster Image */}
      {posterUrl ? (
        <>
          <img
            src={posterUrl}
            alt="Video preview thumbnail"
            className="absolute inset-0 h-full w-full object-cover bg-slate-950 transition-transform duration-500 group-hover/preview:scale-105"
            loading="lazy"
          />
          {/* Subtle dark overlay to make play button pop and look premium */}
          <div className="absolute inset-0 bg-slate-950/20 transition-colors duration-500 group-hover/preview:bg-slate-950/40" />
        </>
      ) : (
        <>
          <div
            className={cn(
              "absolute inset-0 bg-gradient-to-br transition-all duration-500 group-hover/preview:scale-105",
              theme.gradient
            )}
          />
          <div className="absolute inset-0 bg-[radial-gradient(#ffffff08_1px,transparent_1px)] [background-size:16px_16px] opacity-60" />
        </>
      )}

      {/* Glow effect on hover */}
      <div className="absolute inset-0 bg-primary/0 transition-colors duration-500 group-hover/preview:bg-primary/5" />

      {/* Solid White Play Button */}
      <div className="relative z-10 flex size-14 items-center justify-center rounded-full bg-white text-slate-950 shadow-[0_8px_32px_0_rgba(0,0,0,0.3)] transition-all duration-300 group-hover/preview:scale-110">
        <Play className="size-6 fill-current text-slate-950 translate-x-0.5" />
      </div>
    </Button>
  )
}

/* ─────────────────────────────────────────────
   Viral score ring component matching Vizard.ai
   ───────────────────────────────────────────── */
const VIRAL_SCORE_TIERS: Record<string, { range: string; desc: string; dot: string }> = {
  "Very High": { range: "8.5–10", desc: "Ready to post — strong hook & high resonance.", dot: "bg-emerald-500" },
  High: { range: "7.0–8.4", desc: "Likely to perform well on social platforms.", dot: "bg-amber-500" },
  Medium: { range: "5.0–6.9", desc: "May need a tighter hook or edit to take off.", dot: "bg-indigo-500" },
  Low: { range: "0–4.9", desc: "Consider reworking the angle or using as B-roll.", dot: "bg-rose-500" },
}

export function ViralScoreRing({ score }: { score: number }) {
  const radius = 30
  const stroke = 5
  const normalizedRadius = radius - stroke * 2
  const circumference = normalizedRadius * 2 * Math.PI
  const strokeDashoffset = circumference - (score / 10) * circumference

  let strokeColor = "stroke-slate-250"
  let textColor = "text-slate-700"
  let bgColor = "bg-slate-50"
  let labelText = "Low"

  if (score >= 8.5) {
    strokeColor = "stroke-emerald-500"
    textColor = "text-emerald-700"
    bgColor = "bg-emerald-50/50"
    labelText = "Very High"
  } else if (score >= 7.0) {
    strokeColor = "stroke-amber-500"
    textColor = "text-amber-700"
    bgColor = "bg-amber-50/50"
    labelText = "High"
  } else if (score >= 5.0) {
    strokeColor = "stroke-indigo-500"
    textColor = "text-indigo-700"
    bgColor = "bg-indigo-50/50"
    labelText = "Medium"
  } else {
    strokeColor = "stroke-rose-500"
    textColor = "text-rose-700"
    bgColor = "bg-rose-50/50"
    labelText = "Low"
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex flex-col items-center gap-1.5 cursor-help shrink-0 select-none">
            <div
              className={cn(
                "relative flex items-center justify-center rounded-full border border-slate-100 p-0.5",
                bgColor
              )}
            >
              <svg
                height={radius * 2}
                width={radius * 2}
                className="-rotate-90 transform"
              >
                <circle
                  className="stroke-slate-100"
                  fill="transparent"
                  strokeWidth={stroke}
                  r={normalizedRadius}
                  cx={radius}
                  cy={radius}
                />
                <circle
                  className={cn(
                    "transition-all duration-500 ease-in-out",
                    strokeColor
                  )}
                  fill="transparent"
                  strokeWidth={stroke}
                  strokeDasharray={circumference + " " + circumference}
                  style={{ strokeDashoffset }}
                  strokeLinecap="round"
                  r={normalizedRadius}
                  cx={radius}
                  cy={radius}
                />
              </svg>
              <span
                className={cn(
                  "absolute text-sm sm:text-lg font-black tabular-nums",
                  textColor
                )}
              >
                {score}
              </span>
            </div>
            <span
              className={cn(
                "text-[9px] font-extrabold tracking-widest uppercase",
                textColor === "text-slate-700" ? "text-slate-400" : textColor
              )}
            >
              Viral Score
            </span>
          </div>
        </TooltipTrigger>
        <TooltipContent side="top" sideOffset={6} className="max-w-[280px] px-3.5 py-2.5">
          <div className="flex items-start gap-2">
            <span className={cn("mt-1 h-2 w-2 shrink-0 rounded-full", VIRAL_SCORE_TIERS[labelText].dot)} />
            <div>
              <p className="text-xs font-bold leading-tight">{labelText} <span className="font-normal opacity-60">({VIRAL_SCORE_TIERS[labelText].range})</span></p>
              <p className="mt-0.5 text-[11px] leading-snug opacity-75">{VIRAL_SCORE_TIERS[labelText].desc}</p>
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

/* ─────────────────────────────────────────────
   HookCard: click anywhere on hook to copy.
   ───────────────────────────────────────────── */
export function HookCard({ hookText }: { hookText: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(hookText)
      setCopied(true)
      toast.success("Hook copied to clipboard")
      setTimeout(() => setCopied(false), 1500)
    } catch (err) {
      console.error("Copy failed:", err)
      toast.error("Couldn't copy to clipboard")
    }
  }

  return (
    <Button
      type="button"
      onClick={handleCopy}
      title="Click to copy hook"
      variant="ghost"
      className="group/hook block h-auto w-full rounded-xl border border-slate-100 bg-slate-50/60 p-0 px-3.5 py-3 text-left transition-colors hover:border-primary/20 hover:bg-primary/5 hover:text-slate-700"
    >
      <div className="mb-1 flex items-center justify-between gap-3">
        <span className="text-[10px] font-bold tracking-[0.15em] text-slate-400 uppercase">
          Hook Text
        </span>
        {copied ? (
          <Check className="size-3.5 text-emerald-500" />
        ) : (
          <Copy className="size-3.5 text-slate-300 transition-colors group-hover/hook:text-primary" />
        )}
      </div>
      <p className="line-clamp-3 text-sm leading-snug font-medium text-slate-700">
        {hookText}
      </p>
    </Button>
  )
}

/* ─────────────────────────────────────────────
   DescriptionCard: displays description and hashtags with copy functionality.
   ───────────────────────────────────────────── */
export function DescriptionCard({
  description,
  hashtags,
}: {
  description: string
  hashtags?: string | null
}) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      const textToCopy = hashtags
        ? `${description}\n\n${hashtags}`
        : description
      await navigator.clipboard.writeText(textToCopy)
      setCopied(true)
      toast.success("Description & hashtags copied!")
      setTimeout(() => setCopied(false), 1500)
    } catch (err) {
      console.error("Copy failed:", err)
      toast.error("Couldn't copy to clipboard")
    }
  }

  return (
    <div className="relative group/desc rounded-xl border border-indigo-100/40 bg-indigo-50/20 p-2.5 text-indigo-950 sm:p-3.5">
      <div className="mb-1.5 flex items-center justify-between gap-3">
        <div className="flex items-center gap-1.5 text-[10px] font-bold tracking-wider text-indigo-600 uppercase">
          <Sparkles className="h-3.5 w-3.5 fill-indigo-100/30" />
          <span>AI Description & Hashtags</span>
        </div>
        <Button
          type="button"
          onClick={handleCopy}
          title="Copy description & hashtags"
          variant="ghost"
          className="h-6 w-6 rounded-md p-0 text-slate-400 hover:bg-indigo-100/60 hover:text-indigo-600 active:scale-95 transition-all"
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-emerald-500" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </Button>
      </div>
      <p className="text-[11px] leading-relaxed font-medium text-slate-600 sm:text-xs">
        {description}
      </p>
      {hashtags && (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {hashtags.split(/\s+/).map((tag, idx) => (
            <span
              key={idx}
              className="inline-block rounded-md bg-indigo-50 px-1.5 py-0.5 text-[10px] font-bold text-indigo-600 border border-indigo-100/40 sm:text-[11px]"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function formatTime(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return "00:00"
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
}

type ClipCardProps = {
  clip: Clip
  index: number
  isCaptioned: boolean
  onToggleCaptions: (clipId: string) => void
  onEdit: (clip: Clip) => void
  onDownload: (clip: Clip, options?: { withoutCaptions?: boolean }) => void
  isPlaying: boolean
  onPlay: () => void
  isDownloading?: boolean
  isExporting?: boolean
  isFree?: boolean
}

import { UpgradeModal } from "@/components/ui/upgrade-modal"

function ClipCardBase({
  clip,
  index,
  isCaptioned,
  onToggleCaptions,
  onEdit,
  onDownload,
  isPlaying,
  onPlay,
  isDownloading = false,
  isExporting = false,
  isFree = false,
}: ClipCardProps) {
  const [showUpgradeModal, setShowUpgradeModal] = useState(false)
  const [isDownloadingPreview, setIsDownloadingPreview] = useState(false)
  const isRendering = clip.status === "rendering"
  const clipType = clip.clipType && CLIP_TYPE_MAP[clip.clipType]
  const duration = clip.endTime - clip.startTime
  const videoUrl = isCaptioned
    ? clip.previewVideoUrl || clip.captionVideoUrl || clip.originalVideoUrl
    : clip.originalVideoUrl

  return (
    <div
      className="group relative flex flex-col overflow-hidden rounded-2xl border border-slate-100 bg-white transition-all duration-300 hover:border-slate-200 hover:shadow-[0_12px_40px_rgba(0,0,0,0.05)] md:flex-row"
      style={{ contentVisibility: "auto", containIntrinsicSize: "auto 220px" }}
    >
      <div className="relative w-full aspect-[9/16] flex-shrink-0 overflow-hidden bg-slate-950 md:w-[270px]">
        {videoUrl ? (
          <NativeVideoPreview
            src={videoUrl}
            isPlaying={isPlaying}
            onPlay={onPlay}
            clipType={clip.clipType || "hot_take"}
            posterUrl={clip.thumbnailUrl}
            duration={duration}
            className="h-full w-full"
          />
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center gap-3 bg-slate-900 text-slate-500">
            <div className="relative size-10">
              <div className="absolute inset-0 animate-spin rounded-full border-2 border-primary/20 border-t-primary" />
            </div>
            <span className="animate-pulse text-[9px] font-semibold tracking-widest text-slate-400 uppercase">
              Generating…
            </span>
          </div>
        )}

        {isRendering && (
          <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-slate-950/70 px-3 text-center backdrop-blur-sm">
            <div className="relative mb-2 size-8">
              <div className="absolute inset-0 animate-spin rounded-full border-2 border-primary/20 border-t-primary" />
            </div>
            <p className="text-[10px] leading-tight font-bold text-white">
              {clip.renderStatus || "Rendering…"}
            </p>
          </div>
        )}
      </div>

      <div className="flex min-w-0 flex-1 flex-col p-3.5 sm:p-5">
        <div className="mb-3 sm:mb-4">
          <div className="flex items-start justify-between gap-3 sm:gap-4">
            <div className="min-w-0 flex-1">
              <div className="mb-1.5 flex items-center gap-1.5 sm:mb-2 sm:gap-2">
                <span className="inline-flex shrink-0 items-center justify-center rounded-md bg-indigo-50 px-2 py-0.5 text-[11px] font-bold text-indigo-600">
                  #{String(index + 1).padStart(2, "0")}
                </span>
                {clipType && (
                  <span
                    className={cn(
                      "inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-bold",
                      clipType.classes
                    )}
                  >
                    {clipType.label}
                  </span>
                )}
              </div>
              <h3 className="line-clamp-2 text-lg sm:text-xl font-bold tracking-tight text-slate-900 leading-snug">
                {clip.title}
              </h3>
            </div>

            <div className="hidden shrink-0 sm:block">
              <ViralScoreRing score={clip.viralScore} />
            </div>
          </div>

          {/* Mobile-only: Viral score shown inline below title */}
          <div className="mt-2.5 flex sm:hidden">
            <ViralScoreRing score={clip.viralScore} />
          </div>
        </div>

        <div className="mb-3 flex flex-wrap items-center gap-1.5 sm:mb-4 sm:gap-2">
          {/* Time range */}
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-slate-100 bg-slate-50/60 px-2.5 py-1 text-[11px] font-semibold text-slate-600 sm:text-xs">
            <Clock className="h-3.5 w-3.5 text-slate-400" />
            {formatTime(clip.startTime)} - {formatTime(clip.endTime)} ({Math.round(duration)}s)
          </span>
          {/* Aspect ratio */}
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-slate-100 bg-slate-50/60 px-2.5 py-1 text-[11px] font-semibold text-slate-600 sm:text-xs">
            <Smartphone className="h-3.5 w-3.5 text-slate-400" />
            9:16
          </span>
          {/* Captions */}
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-slate-100 bg-slate-50/60 px-2.5 py-1 text-[11px] font-semibold text-slate-600 sm:text-xs">
            <ClosedCaption className="h-3.5 w-3.5 text-slate-400" />
            Captions
          </span>
          {/* Auto Framed */}
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-slate-100 bg-slate-50/60 px-2.5 py-1 text-[11px] font-semibold text-slate-600 sm:text-xs">
            <Sparkles className="h-3.5 w-3.5 text-slate-400" />
            Auto Framed
          </span>
        </div>

        {clip.hookText && (
          <div className="mb-2.5 sm:mb-3.5">
            <HookCard hookText={clip.hookText} />
          </div>
        )}

        {clip.description && (
          <div className="mb-3 sm:mb-4">
            <DescriptionCard
              description={clip.description}
              hashtags={clip.hashtags}
            />
          </div>
        )}

        <div className="mt-auto flex flex-col gap-2 border-t border-slate-100/60 pt-3 sm:flex-row sm:items-center sm:justify-end sm:gap-3 sm:pt-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onEdit(clip)}
            disabled={isRendering}
            className="flex h-9 w-full sm:w-auto items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 text-xs font-semibold text-slate-700 shadow-sm transition-all duration-300 hover:bg-slate-50 hover:border-slate-300 active:scale-95 sm:h-10"
            title="Trim unwanted sections from start or end"
          >
            <Scissors className="size-3.5 text-slate-500" />
            <span>Trim Clip</span>
          </Button>

          {isFree ? (
            <>
              <Button
                variant="outline"
                size="sm"
                className="flex h-9 w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-xs font-bold text-slate-700 shadow-sm transition-all duration-300 hover:bg-slate-50 active:scale-95 sm:h-10 sm:w-auto sm:px-5"
                onClick={async () => {
                  if (!clip.previewVideoUrl) {
                    toast.error("Preview video is not ready yet.")
                    return
                  }
                  setIsDownloadingPreview(true)
                  const toastId = toast.loading("Downloading preview video...")
                  try {
                    const response = await fetch(clip.previewVideoUrl)
                    if (!response.ok) throw new Error("Fetch failed")
                    const blob = await response.blob()
                    const blobUrl = window.URL.createObjectURL(blob)
                    const link = document.createElement("a")
                    link.href = blobUrl

                    const safeTitle = (clip.title || "clip").replace(/[^a-z0-9]/gi, "_").toLowerCase()
                    link.download = `${safeTitle}_preview.mp4`

                    document.body.appendChild(link)
                    link.click()
                    document.body.removeChild(link)
                    window.URL.revokeObjectURL(blobUrl)
                    trackClipDownloaded({ clipId: clip.id })
                    toast.dismiss(toastId)
                    toast.success("Download started!")
                  } catch (err) {
                    console.error("Direct download failed, using fallback:", err)
                    window.open(clip.previewVideoUrl, "_blank", "noopener,noreferrer")
                    trackClipDownloaded({ clipId: clip.id })
                    toast.dismiss(toastId)
                    toast.success("Opening preview video in new tab.")
                  } finally {
                    setIsDownloadingPreview(false)
                  }
                }}
                disabled={!clip.previewVideoUrl || isDownloadingPreview}
              >
                {isDownloadingPreview ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Download className="size-3.5 text-slate-500" />
                )}
                {isDownloadingPreview ? "Downloading..." : "Download Preview (SD)"}
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={() => {
                  trackCheckoutInitiated({ planId: "pro_upgrade" })
                  setShowUpgradeModal(true)
                }}
                className="flex h-9 w-full items-center justify-center gap-2 rounded-xl px-4 text-xs font-bold shadow-sm transition-all duration-300 active:scale-95 sm:h-10 sm:w-auto sm:px-5"
              >
                <Sparkles className="size-3.5 text-primary-foreground" />
                Upgrade to Export HD
              </Button>
            </>
          ) : (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  size="sm"
                  className="flex h-9 w-full sm:w-auto items-center justify-center gap-2 rounded-xl border-0 bg-slate-950 px-4 text-xs font-bold text-white shadow-sm transition-all duration-300 hover:bg-slate-800 active:scale-95 sm:h-10 sm:px-5"
                  disabled={isRendering || isExporting || isDownloading || !clip.originalVideoUrl}
                >
                  {isRendering || isExporting ? (
                    <>
                      <Loader2 className="size-3.5 animate-spin" />
                      Exporting HD…
                    </>
                  ) : isDownloading ? (
                    <>
                      <Loader2 className="size-3.5 animate-spin" />
                      Downloading…
                    </>
                  ) : (
                    <>
                      <Download className="size-3.5" />
                      <span>Download</span>
                      <ChevronDown className="size-4 ml-1 opacity-70" />
                    </>
                  )}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-fit">
                <DropdownMenuItem
                  className="justify-between gap-8 px-4 text-[11px] whitespace-nowrap"
                  onClick={() => onDownload(clip)}
                >
                  {clip.captionVideoUrl ? (
                    <span>Download with Captions</span>
                  ) : (
                    <span>Export HD with Captions</span>
                  )}
                  <ClosedCaption className="size-3.5 opacity-80" />
                </DropdownMenuItem>
                <DropdownMenuItem
                  className="justify-between gap-8 px-4 text-[11px] whitespace-nowrap"
                  onClick={() => onDownload(clip, { withoutCaptions: true })}
                >
                  <span>Download without Captions</span>
                  <ClosedCaption className="size-3.5 opacity-40" />
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>

      <UpgradeModal
        open={showUpgradeModal}
        onOpenChange={setShowUpgradeModal}
        triggerId="export_1080p"
      />
    </div>
  )
}

export const ClipCard = memo(ClipCardBase, (prev, next) => {
  const a = prev.clip
  const b = next.clip

  return (
    prev.isFree === next.isFree &&
    prev.isCaptioned === next.isCaptioned &&
    prev.onToggleCaptions === next.onToggleCaptions &&
    prev.onEdit === next.onEdit &&
    prev.onDownload === next.onDownload &&
    prev.isPlaying === next.isPlaying &&
    prev.onPlay === next.onPlay &&
    prev.index === next.index &&
    prev.isDownloading === next.isDownloading &&
    prev.isExporting === next.isExporting &&
    a.id === b.id &&
    a.title === b.title &&
    a.hookText === b.hookText &&
    a.startTime === b.startTime &&
    a.endTime === b.endTime &&
    a.viralScore === b.viralScore &&
    a.status === b.status &&
    a.renderStatus === b.renderStatus &&
    a.originalVideoUrl === b.originalVideoUrl &&
    a.captionVideoUrl === b.captionVideoUrl &&
    a.captionStyle === b.captionStyle &&
    a.clipType === b.clipType &&
    a.captions === b.captions &&
    a.thumbnailUrl === b.thumbnailUrl &&
    a.previewVideoUrl === b.previewVideoUrl
  )
})

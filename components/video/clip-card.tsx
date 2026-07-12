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
} from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "sonner"
import type { Clip } from "@/lib/types"
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
}: {
  src: string
  className?: string
  isPlaying: boolean
  onPlay: () => void
  clipType?: string
  posterUrl?: string | null
}) {
  const theme = CLIP_THEME_MAP[clipType] || CLIP_THEME_MAP.hot_take

  const previewBadge = (
    <span className="absolute top-2 left-2 z-30 inline-flex items-center gap-1 rounded-md bg-black/60 px-1.5 py-0.5 text-[9px] font-bold tracking-wide text-white/80 uppercase backdrop-blur-sm">
      SD Preview
    </span>
  )

  if (isPlaying) {
    return (
      <div className={cn("relative h-full w-full bg-slate-950", className)}>
        {previewBadge}
        <video
          src={src}
          poster={posterUrl || undefined}
          autoPlay
          controls
          playsInline
          className="h-full w-full object-cover"
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
        "group/preview relative block flex h-full w-full flex-col items-center justify-center overflow-hidden p-0 transition-all duration-500 hover:bg-transparent focus-visible:ring-0",
        className
      )}
    >
      {previewBadge}
      {/* Background Gradient & Pattern or Poster Image */}
      {posterUrl ? (
        <>
          <img
            src={posterUrl}
            alt="Video preview thumbnail"
            className="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover/preview:scale-105"
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

      {/* Glassmorphic Play Button */}
      <div className="relative z-10 flex size-14 items-center justify-center rounded-full border border-white/20 bg-white/10 text-white shadow-[0_8px_32px_0_rgba(0,0,0,0.3)] backdrop-blur-md transition-all duration-300 group-hover/preview:scale-110 group-hover/preview:border-white/30 group-hover/preview:bg-white/20">
        <Play
          className={cn(
            "size-6 fill-current transition-transform duration-300 group-hover/preview:translate-x-0.5",
            theme.iconColor
          )}
        />
      </div>

      <span className="relative z-10 mt-3 text-[10px] font-bold tracking-widest text-white uppercase drop-shadow-sm transition-colors duration-300 group-hover/preview:text-white">
        Play Preview
      </span>
    </Button>
  )
}

/* ─────────────────────────────────────────────
   Viral score ring component matching Vizard.ai
   ───────────────────────────────────────────── */
const VIRAL_SCORE_TIERS: Record<string, { range: string; desc: string; dot: string }> = {
  "Very High": { range: "85–100", desc: "Ready to post — strong hook & high resonance.", dot: "bg-emerald-500" },
  High: { range: "70–84", desc: "Likely to perform well on social platforms.", dot: "bg-amber-500" },
  Medium: { range: "50–69", desc: "May need a tighter hook or edit to take off.", dot: "bg-indigo-500" },
  Low: { range: "0–49", desc: "Consider reworking the angle or using as B-roll.", dot: "bg-rose-500" },
}

export function ViralScoreRing({ score }: { score: number }) {
  const radius = 30
  const stroke = 5
  const normalizedRadius = radius - stroke * 2
  const circumference = normalizedRadius * 2 * Math.PI
  const strokeDashoffset = circumference - (score / 100) * circumference

  let strokeColor = "stroke-slate-250"
  let textColor = "text-slate-700"
  let bgColor = "bg-slate-50"
  let labelText = "Low"

  if (score >= 85) {
    strokeColor = "stroke-emerald-500"
    textColor = "text-emerald-700"
    bgColor = "bg-emerald-50/50"
    labelText = "Very High"
  } else if (score >= 70) {
    strokeColor = "stroke-amber-500"
    textColor = "text-amber-700"
    bgColor = "bg-amber-50/50"
    labelText = "High"
  } else if (score >= 50) {
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
          <div className="flex shrink-0 cursor-help items-center gap-2.5">
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
                  "absolute text-xs sm:text-lg font-black tabular-nums",
                  textColor
                )}
              >
                {score}
              </span>
            </div>
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
  onDownload: (clip: Clip) => void
  isPlaying: boolean
  onPlay: () => void
  isDownloading?: boolean
  isExporting?: boolean
  isFree?: boolean
}

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
      <div className="relative w-full flex-shrink-0 overflow-hidden rounded-2xl bg-slate-950 md:w-[380px] md:min-w-[280px]">
        {videoUrl ? (
          <NativeVideoPreview
            src={videoUrl}
            isPlaying={isPlaying}
            onPlay={onPlay}
            clipType={clip.clipType || "hot_take"}
            posterUrl={clip.thumbnailUrl}
            className="aspect-[4/5] w-full md:aspect-auto md:h-full md:min-h-[360px]"
          />
        ) : (
          <div className="flex aspect-[4/5] w-full flex-col items-center justify-center gap-3 bg-slate-900 text-slate-500 md:aspect-auto md:h-full md:min-h-[360px]">
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
                <span className="inline-flex shrink-0 items-center justify-center rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-bold text-slate-700">
                  #{String(index + 1).padStart(2, "0")}
                </span>
                {clipType && (
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold",
                      clipType.classes
                    )}
                  >
                    {clipType.label}
                  </span>
                )}
              </div>
              <h3 className="line-clamp-2 text-base leading-snug font-black text-slate-950 sm:text-lg">
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
          <span className="inline-flex items-center gap-1 rounded-lg border border-slate-100 bg-slate-50 px-2 py-0.5 text-[11px] font-semibold text-slate-600 sm:gap-1.5 sm:px-2.5 sm:py-1 sm:text-xs">
            <Clock className="h-3 w-3 text-slate-400 sm:h-3.5 sm:w-3.5" />
            {formatTime(clip.startTime)} - {formatTime(clip.endTime)} (
            {Math.round(duration)}s)
          </span>
          <span className="inline-flex items-center gap-1 rounded-lg border border-slate-100 bg-slate-50 px-2 py-0.5 text-[11px] font-semibold text-slate-500 sm:px-2.5 sm:py-1 sm:text-xs">
            <Video className="h-3 w-3 text-slate-400 sm:h-3.5 sm:w-3.5" />
            9:16
          </span>
        </div>

        {clip.hookText && (
          <div className="mb-2.5 sm:mb-3.5">
            <HookCard hookText={clip.hookText} />
          </div>
        )}

        {clip.viralReason && (
          <div className="mb-3 rounded-xl border border-indigo-100/40 bg-indigo-50/20 p-2.5 text-indigo-950 sm:mb-4 sm:p-3.5">
            <div className="mb-1 flex items-center gap-1.5 text-[10px] font-bold tracking-wider text-indigo-600 uppercase">
              <Sparkles className="h-3.5 w-3.5 fill-indigo-100/30" />
              <span>AI Virality Explanation</span>
            </div>
            <p className="line-clamp-3 text-[11px] leading-relaxed font-medium text-slate-600 sm:line-clamp-none sm:text-xs">
              {clip.viralReason}
            </p>
          </div>
        )}

        <div className="mt-auto flex flex-col gap-2 border-t border-slate-100/60 pt-3 sm:flex-row sm:items-center sm:justify-end sm:gap-3 sm:pt-4">
          {isFree ? (
            <>
              <Button
                variant="outline"
                size="sm"
                className="flex h-9 w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-xs font-bold text-slate-700 shadow-sm transition-all duration-300 hover:bg-slate-50 active:scale-95 sm:h-10 sm:w-auto sm:px-5"
                onClick={() => {
                  if (clip.previewVideoUrl) {
                    window.open(clip.previewVideoUrl, "_blank", "noopener,noreferrer")
                    toast.success("Opening preview video in new tab!")
                  } else {
                    toast.error("Preview video is not ready yet.")
                  }
                }}
                disabled={!clip.previewVideoUrl}
              >
                <Download className="size-3.5 text-slate-500" />
                Download Preview (SD)
              </Button>
              <a
                href="/pricing"
                className="flex h-9 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 px-4 text-xs font-bold text-white shadow-sm transition-all duration-300 hover:from-violet-500 hover:to-indigo-500 active:scale-95 sm:h-10 sm:w-auto sm:px-5 sm:hover:scale-[1.02]"
              >
                <Sparkles className="size-3.5 text-amber-300 fill-amber-300 animate-pulse" />
                Upgrade to Download HD
              </a>
            </>
          ) : (
            <Button
              size="sm"
              className="flex h-9 w-full items-center justify-center gap-2 rounded-xl border-0 bg-slate-950 px-4 text-xs font-bold text-white shadow-sm transition-all duration-300 hover:bg-slate-800 active:scale-95 sm:h-10 sm:w-auto sm:px-5 sm:hover:scale-[1.02]"
              onClick={() => {
                if (clip.captionVideoUrl) {
                  window.open(clip.captionVideoUrl, "_blank", "noopener,noreferrer")
                } else {
                  onDownload(clip)
                }
              }}
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
              ) : clip.captionVideoUrl ? (
                <>
                  <Download className="size-3.5" />
                  Download HD
                </>
              ) : (
                <>
                  <Download className="size-3.5" />
                  Export HD
                </>
              )}
            </Button>
          )}
        </div>
      </div>
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

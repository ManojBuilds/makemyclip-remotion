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
  Flame,
  TrendingUp,
  Quote,
  Play,
  Eye,
  Smartphone,
  ClosedCaption,
  ChevronDown,
  Scissors,
  Share2,
  Zap,
  SlidersHorizontal,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "sonner"
import type { Clip } from "@/lib/types"
import {
  trackClipDownloaded,
  trackCheckoutInitiated,
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
import { UpgradeModal } from "@/components/ui/upgrade-modal"

const CLIP_TYPE_MAP: Record<string, { label: string; badge: string; glow: string }> = {
  hot_take: {
    label: "Hot Take",
    badge: "bg-rose-50 text-rose-700 border-rose-200/80",
    glow: "text-rose-500",
  },
  aha_moment: {
    label: "Aha Moment",
    badge: "bg-amber-50 text-amber-700 border-amber-200/80",
    glow: "text-amber-500",
  },
  funny_exchange: {
    label: "Banter",
    badge: "bg-violet-50 text-violet-700 border-violet-200/80",
    glow: "text-violet-500",
  },
  debate: {
    label: "Debate",
    badge: "bg-indigo-50 text-indigo-700 border-indigo-200/80",
    glow: "text-indigo-500",
  },
  storytelling: {
    label: "Story",
    badge: "bg-emerald-50 text-emerald-700 border-emerald-200/80",
    glow: "text-emerald-500",
  },
  quotable: {
    label: "Quotable",
    badge: "bg-sky-50 text-sky-700 border-sky-200/80",
    glow: "text-sky-500",
  },
  emotional: {
    label: "Vulnerable",
    badge: "bg-pink-50 text-pink-700 border-pink-200/80",
    glow: "text-pink-500",
  },
  mind_blowing_fact: {
    label: "Mind-Blowing",
    badge: "bg-fuchsia-50 text-fuchsia-700 border-fuchsia-200/80",
    glow: "text-fuchsia-500",
  },
}

const CLIP_THEME_MAP: Record<string, { gradient: string }> = {
  hot_take: { gradient: "from-rose-900/30 via-slate-950 to-rose-950/20" },
  aha_moment: { gradient: "from-amber-900/30 via-slate-950 to-amber-950/20" },
  funny_exchange: { gradient: "from-violet-900/30 via-slate-950 to-violet-950/20" },
  debate: { gradient: "from-indigo-900/30 via-slate-950 to-indigo-950/20" },
  storytelling: { gradient: "from-emerald-900/30 via-slate-950 to-emerald-950/20" },
  quotable: { gradient: "from-sky-900/30 via-slate-950 to-sky-950/20" },
  emotional: { gradient: "from-pink-900/30 via-slate-950 to-pink-950/20" },
  mind_blowing_fact: { gradient: "from-fuchsia-900/30 via-slate-950 to-fuchsia-950/20" },
}

/* ─────────────────────────────────────────────
   Format viral score and calculate tier metadata
   ───────────────────────────────────────────── */
export function getViralTier(score: number | undefined | null) {
  const numScore = typeof score === "number" ? score : Number(score || 0)
  const score100 =
    numScore <= 10
      ? Math.round(numScore * 10)
      : Math.min(100, Math.max(1, Math.round(numScore)))

  if (score100 >= 90) {
    return {
      tierKey: "Viral Outlier",
      tagline: "Top 1% viral potential",
      score100,
      badge: "bg-emerald-500/10 text-emerald-700 border-emerald-500/30 dark:text-emerald-400",
      pillContainer: "border-emerald-500/30 bg-emerald-50/60 shadow-emerald-500/10",
      scoreColor: "text-emerald-700",
      flameColor: "text-emerald-500",
      ringStroke: "#10b981",
      hookPower: Math.min(99, score100),
      pacingScore: Math.min(98, Math.max(88, score100 - 2)),
      retentionScore: Math.min(99, Math.max(90, score100 - 1)),
    }
  }
  if (score100 >= 80) {
    return {
      tierKey: "High Potential",
      tagline: "Strong engagement loop",
      score100,
      badge: "bg-amber-500/10 text-amber-700 border-amber-500/30 dark:text-amber-400",
      pillContainer: "border-amber-500/30 bg-amber-50/60 shadow-amber-500/10",
      scoreColor: "text-amber-700",
      flameColor: "text-amber-500",
      ringStroke: "#f59e0b",
      hookPower: score100,
      pacingScore: Math.max(78, score100 - 3),
      retentionScore: Math.max(82, score100 - 1),
    }
  }
  if (score100 >= 70) {
    return {
      tierKey: "Good Pacing",
      tagline: "Consistent watch time",
      score100,
      badge: "bg-indigo-500/10 text-indigo-700 border-indigo-500/30 dark:text-indigo-400",
      pillContainer: "border-indigo-500/30 bg-indigo-50/60 shadow-indigo-500/10",
      scoreColor: "text-indigo-700",
      flameColor: "text-indigo-500",
      ringStroke: "#6366f1",
      hookPower: score100,
      pacingScore: Math.max(72, score100 - 2),
      retentionScore: Math.max(74, score100 - 2),
    }
  }
  return {
    tierKey: "Moderate",
    tagline: "Solid conversational clip",
    score100,
    badge: "bg-slate-500/10 text-slate-700 border-slate-500/30",
    pillContainer: "border-slate-200 bg-slate-50/80",
    scoreColor: "text-slate-700",
    flameColor: "text-slate-400",
    ringStroke: "#94a3b8",
    hookPower: Math.max(50, score100),
    pacingScore: Math.max(55, score100),
    retentionScore: Math.max(60, score100),
  }
}

function formatViralReason(rawReason?: string | null, clipType?: string) {
  if (
    !rawReason ||
    rawReason.includes("enhanced heuristic") ||
    rawReason.includes("Multi-signal") ||
    rawReason.trim().length < 10
  ) {
    const formattedType = clipType ? clipType.replace("_", " ") : "highlight"
    return `Captures an immediate curiosity gap in the opening 3 seconds with high-energy ${formattedType} momentum.`
  }
  return rawReason
}

function formatTime(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return "00:00"
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
}

/* ─────────────────────────────────────────────
   Optimized native video preview
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
      <span className="inline-flex items-center gap-1 rounded-full bg-black/60 px-2.5 py-1 text-[10px] font-bold text-white/95 backdrop-blur-md border border-white/10 shadow-sm">
        <Eye className="size-3 text-emerald-400" /> Preview
      </span>
      <span className="inline-flex items-center rounded-full bg-black/60 px-2.5 py-1 text-[10px] font-bold text-white/95 backdrop-blur-md border border-white/10 shadow-sm">
        720p
      </span>
    </div>
  )

  const durationBadge = duration ? (
    <span className="absolute top-3 right-3 z-30 inline-flex items-center rounded-full bg-black/60 px-2.5 py-1 text-[10px] font-bold text-white/95 backdrop-blur-md border border-white/10 shadow-sm select-none">
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
      {posterUrl ? (
        <>
          <img
            src={posterUrl}
            alt="Video preview thumbnail"
            className="absolute inset-0 h-full w-full object-cover bg-slate-950 transition-transform duration-500 group-hover/preview:scale-105"
            loading="lazy"
          />
          <div className="absolute inset-0 bg-slate-950/25 transition-colors duration-500 group-hover/preview:bg-slate-950/45" />
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

      {/* Pulsing Play Button */}
      <div className="relative z-10 flex size-14 items-center justify-center rounded-full bg-white text-slate-950 shadow-[0_8px_32px_0_rgba(0,0,0,0.35)] transition-all duration-300 group-hover/preview:scale-110 group-hover/preview:shadow-[0_12px_40px_0_rgba(0,0,0,0.45)]">
        <Play className="size-6 fill-current text-slate-950 translate-x-0.5" />
      </div>
    </Button>
  )
}

/* ─────────────────────────────────────────────
   Hero Virality Score HUD Widget
   ───────────────────────────────────────────── */
export function HeroViralHUD({ score, reason }: { score: number; reason?: string }) {
  const tier = getViralTier(score)

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="cursor-help select-none">
            <div
              className={cn(
                "flex items-center gap-2 rounded-2xl border px-3 py-1.5 backdrop-blur-md shadow-xs transition-all hover:scale-[1.02]",
                tier.pillContainer
              )}
            >
              <div className="flex items-center gap-1.5">
                <Flame className={cn("size-4.5 fill-current", tier.flameColor)} />
                <span className={cn("text-lg sm:text-xl font-black tabular-nums tracking-tight", tier.scoreColor)}>
                  {tier.score100}
                </span>
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-tight">/100</span>
              </div>
              <div className="h-3.5 w-px bg-slate-300/80" />
              <div className="flex flex-col text-left leading-none">
                <span className={cn("text-[10px] font-extrabold uppercase tracking-wider", tier.scoreColor)}>
                  {tier.tierKey}
                </span>
                <span className="text-[9px] font-medium text-slate-400 hidden sm:inline">
                  {tier.tagline}
                </span>
              </div>
            </div>
          </div>
        </TooltipTrigger>
        <TooltipContent side="top" sideOffset={8} className="max-w-[280px] p-3 text-left">
          <div className="space-y-2">
            <div className="flex items-center justify-between border-b border-white/10 pb-1.5">
              <span className="text-xs font-bold text-white">Algorithm Predictor</span>
              <span className={cn("text-xs font-extrabold", tier.scoreColor)}>{tier.score100}/100</span>
            </div>
            <div className="space-y-1.5 text-[11px]">
              <div className="flex items-center justify-between">
                <span className="text-slate-300">0–3s Hook Power</span>
                <span className="font-bold text-white">{tier.hookPower}%</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-300">Rhythm & Pacing</span>
                <span className="font-bold text-white">{tier.pacingScore}%</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-300">Watch-Time Retention</span>
                <span className="font-bold text-white">{tier.retentionScore}%</span>
              </div>
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

/* ─────────────────────────────────────────────
   ClipCard Props Definition
   ───────────────────────────────────────────── */
type ClipCardProps = {
  clip: Clip
  index: number
  isCaptioned: boolean
  onToggleCaptions: (clipId: string) => void
  onEdit: (clip: Clip) => void
  onDownload: (clip: Clip, options?: { withoutCaptions?: boolean; hdExport?: boolean }) => void
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
  const [showUpgradeModal, setShowUpgradeModal] = useState(false)
  const [activeTab, setActiveTab] = useState<"hook" | "post" | "signals">("hook")
  const [copiedHook, setCopiedHook] = useState(false)
  const [copiedPost, setCopiedPost] = useState(false)

  const isRendering = clip.status === "rendering"
  const clipType = clip.clipType && CLIP_TYPE_MAP[clip.clipType]
  const duration = clip.endTime - clip.startTime
  const viralTier = getViralTier(clip.viralScore)
  const viralReasonFormatted = formatViralReason(clip.viralReason, clip.clipType || undefined)

  const videoUrl = isCaptioned
    ? clip.previewVideoUrl || clip.captionVideoUrl || clip.originalVideoUrl
    : clip.originalVideoUrl

  const handleCopyHook = async () => {
    if (!clip.hookText) return
    try {
      await navigator.clipboard.writeText(clip.hookText)
      setCopiedHook(true)
      toast.success("Hook quote copied to clipboard!")
      setTimeout(() => setCopiedHook(false), 1800)
    } catch {
      toast.error("Failed to copy hook")
    }
  }

  const handleCopyPost = async () => {
    const postCopy = `${clip.title}\n\n${clip.description || ""}\n\n${clip.hashtags || ""}`.trim()
    try {
      await navigator.clipboard.writeText(postCopy)
      setCopiedPost(true)
      toast.success("Title, caption & hashtags copied!")
      setTimeout(() => setCopiedPost(false), 1800)
    } catch {
      toast.error("Failed to copy post copy")
    }
  }

  const handleCopyTag = async (tag: string) => {
    try {
      await navigator.clipboard.writeText(tag)
      toast.success(`Copied ${tag}`)
    } catch {
      toast.error("Copy failed")
    }
  }

  return (
    <div
      className="group relative flex flex-col overflow-hidden rounded-3xl border border-slate-200/80 bg-white shadow-[0_4px_24px_-4px_rgba(0,0,0,0.04)] transition-all duration-300 hover:border-slate-300 hover:shadow-[0_16px_48px_-8px_rgba(0,0,0,0.08)] md:flex-row"
      style={{ contentVisibility: "auto", containIntrinsicSize: "auto 240px" }}
    >
      {/* ── Left Column: 9:16 Video Player Preview ─────────────────── */}
      <div className="relative w-full aspect-[9/16] flex-shrink-0 overflow-hidden bg-slate-950 md:w-[275px]">
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
            <span className="animate-pulse text-[10px] font-bold tracking-widest text-slate-400 uppercase">
              Generating…
            </span>
          </div>
        )}

        {isRendering && (
          <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-slate-950/75 px-3 text-center backdrop-blur-sm">
            <div className="relative mb-2 size-8">
              <div className="absolute inset-0 animate-spin rounded-full border-2 border-primary/20 border-t-primary" />
            </div>
            <p className="text-[11px] leading-tight font-bold text-white">
              {clip.renderStatus || "Rendering Clip…"}
            </p>
          </div>
        )}
      </div>

      {/* ── Right Column: Editorial Studio Card ────────────────────── */}
      <div className="flex min-w-0 flex-1 flex-col p-4 sm:p-5.5">
        {/* Header Row: Index, Category, Title & Viral HUD */}
        <div className="mb-3">
          <div className="flex items-start justify-between gap-3 sm:gap-4">
            <div className="min-w-0 flex-1">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center justify-center rounded-lg bg-slate-100 px-2 py-0.5 text-[11px] font-extrabold text-slate-700">
                  #{String(index + 1).padStart(2, "0")}
                </span>
                {clipType && (
                  <span
                    className={cn(
                      "inline-flex items-center rounded-lg border px-2.5 py-0.5 text-[10px] font-bold",
                      clipType.badge
                    )}
                  >
                    {clipType.label}
                  </span>
                )}
                <div className="flex items-center gap-1.5 text-slate-400 text-xs font-medium">
                  <span>•</span>
                  <span>{Math.round(duration)}s</span>
                  <span>•</span>
                  <span>{formatTime(clip.startTime)} - {formatTime(clip.endTime)}</span>
                  <span>•</span>
                  <span>9:16</span>
                </div>
              </div>

              <h3 className="line-clamp-2 text-lg sm:text-xl font-bold tracking-tight text-slate-900 leading-snug">
                {clip.title}
              </h3>
            </div>

            {/* Desktop Hero Virality Score HUD */}
            <div className="hidden shrink-0 sm:block">
              <HeroViralHUD score={clip.viralScore} reason={clip.viralReason} />
            </div>
          </div>

          {/* Mobile Virality Score Row */}
          <div className="mt-2.5 flex sm:hidden">
            <HeroViralHUD score={clip.viralScore} reason={clip.viralReason} />
          </div>

          {/* AI Hook Insight Callout (Clean Left Accent Line) */}
          <div className="mt-2.5 flex items-start gap-2.5 rounded-r-xl border-l-2 border-amber-500 bg-amber-50/40 px-3 py-2 text-slate-700">
            <Sparkles className="size-3.5 mt-0.5 text-amber-500 shrink-0 fill-amber-100" />
            <p className="text-xs leading-relaxed font-medium text-slate-600">
              <span className="font-semibold text-slate-900">Hook Strategy:</span> {viralReasonFormatted}
            </p>
          </div>
        </div>

        {/* ── Studio Segmented Tab Switcher ── */}
        <div className="mb-3 flex items-center border-b border-slate-100 pb-2">
          <div className="flex items-center gap-1 bg-slate-100/70 p-0.5 rounded-xl border border-slate-200/50">
            <button
              type="button"
              onClick={() => setActiveTab("hook")}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-bold transition-all",
                activeTab === "hook"
                  ? "bg-white text-slate-900 shadow-xs"
                  : "text-slate-500 hover:text-slate-900"
              )}
            >
              <Quote className="size-3 text-indigo-500" />
              <span>Hook Quote</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("post")}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-bold transition-all",
                activeTab === "post"
                  ? "bg-white text-slate-900 shadow-xs"
                  : "text-slate-500 hover:text-slate-900"
              )}
            >
              <Share2 className="size-3 text-indigo-500" />
              <span>Post Copy & Tags</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("signals")}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-bold transition-all",
                activeTab === "signals"
                  ? "bg-white text-slate-900 shadow-xs"
                  : "text-slate-500 hover:text-slate-900"
              )}
            >
              <TrendingUp className="size-3 text-emerald-500" />
              <span>Retention Signals</span>
            </button>
          </div>
        </div>

        {/* ── Studio Tab Body ───────────────────────────────────────── */}
        <div className="mb-4 min-h-[95px]">
          {activeTab === "hook" && (
            <div className="relative rounded-2xl border border-slate-100 bg-slate-50/60 p-3.5 text-left">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-2.5 flex-1 min-w-0">
                  <Quote className="size-4.5 text-indigo-400/80 shrink-0 mt-0.5" />
                  <p className="text-sm font-medium leading-relaxed text-slate-800 italic">
                    "{clip.hookText || "Watch this viral highlight."}"
                  </p>
                </div>
                {clip.hookText && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleCopyHook}
                    className="h-7 px-2.5 text-xs font-semibold text-slate-500 hover:text-slate-900 gap-1.5 shrink-0 bg-white border border-slate-200/60 shadow-2xs"
                  >
                    {copiedHook ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
                    <span>{copiedHook ? "Copied" : "Copy"}</span>
                  </Button>
                )}
              </div>
            </div>
          )}

          {activeTab === "post" && (
            <div className="relative rounded-2xl border border-slate-100 bg-slate-50/60 p-3.5 space-y-2.5">
              <div className="flex items-start justify-between gap-3">
                <p className="line-clamp-2 text-xs leading-relaxed font-medium text-slate-700 flex-1 min-w-0">
                  {clip.description || "Featured viral clip repurposing key highlights for TikTok, Shorts & Reels."}
                </p>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleCopyPost}
                  className="h-7 px-2.5 text-xs font-semibold text-slate-500 hover:text-slate-900 gap-1.5 shrink-0 bg-white border border-slate-200/60 shadow-2xs"
                >
                  {copiedPost ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
                  <span>{copiedPost ? "Copied" : "Copy All"}</span>
                </Button>
              </div>
              {clip.hashtags && (
                <div className="flex flex-wrap gap-1.5 pt-0.5">
                  {clip.hashtags.split(/\s+/).map((tag, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => handleCopyTag(tag)}
                      title="Click to copy tag"
                      className="inline-flex items-center rounded-lg bg-indigo-50/80 hover:bg-indigo-100 px-2 py-0.5 text-[10px] font-bold text-indigo-600 transition-colors"
                    >
                      {tag}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === "signals" && (
            <div className="rounded-2xl border border-slate-100 bg-slate-50/60 p-3">
              <div className="grid grid-cols-3 gap-2.5">
                <div className="rounded-xl border border-slate-100 bg-white p-2 text-center">
                  <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Hook Score</div>
                  <div className="text-base font-black text-emerald-600 tabular-nums">{viralTier.hookPower}%</div>
                  <div className="text-[9px] text-slate-400 font-medium">0–3s Retention</div>
                </div>

                <div className="rounded-xl border border-slate-100 bg-white p-2 text-center">
                  <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Speech Pacing</div>
                  <div className="text-base font-black text-indigo-600 tabular-nums">{viralTier.pacingScore}%</div>
                  <div className="text-[9px] text-slate-400 font-medium">Conversational</div>
                </div>

                <div className="rounded-xl border border-slate-100 bg-white p-2 text-center">
                  <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Audience Fit</div>
                  <div className="text-base font-black text-violet-600 tabular-nums">{viralTier.retentionScore}%</div>
                  <div className="text-[9px] text-slate-400 font-medium">Shorts / Reels</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ── Footer Action Bar: Edit Clip & Direct 1-Click Download ──── */}
        <div className="mt-auto flex items-center justify-between border-t border-slate-100 pt-3">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onEdit(clip)}
                  disabled={isRendering}
                  className="flex h-9 items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 text-xs font-bold text-slate-700 shadow-2xs transition-all hover:bg-slate-50 hover:border-slate-300 active:scale-95"
                >
                  <SlidersHorizontal className="size-3.5 text-indigo-600" />
                  <span>Edit Clip</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="top" className="text-xs font-medium">
                Trim timestamps or edit subtitle transcription
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          {/* Download HD Options Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                size="sm"
                disabled={
                  isRendering ||
                  isExporting ||
                  isDownloading ||
                  (!clip.previewVideoUrl && !clip.originalVideoUrl && !clip.captionVideoUrl)
                }
                className="flex h-9 items-center justify-center gap-2 rounded-xl border-0 bg-slate-950 px-4 text-xs font-bold text-white shadow-sm transition-all hover:bg-slate-800 active:scale-95"
              >
                {isRendering || isExporting ? (
                  <>
                    <Loader2 className="size-3.5 animate-spin" />
                    <span>Exporting HD…</span>
                  </>
                ) : isDownloading ? (
                  <>
                    <Loader2 className="size-3.5 animate-spin" />
                    <span>Downloading…</span>
                  </>
                ) : (
                  <>
                    <Download className="size-3.5 text-emerald-400" />
                    <span>Download HD</span>
                    <ChevronDown className="size-3.5 opacity-70 ml-0.5" />
                  </>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56 p-1.5 shadow-xl rounded-xl">
              <DropdownMenuItem
                className="flex items-center justify-between gap-3 px-3 py-2.5 text-xs font-semibold cursor-pointer rounded-lg hover:bg-slate-50 focus:bg-slate-50"
                onClick={() => onDownload(clip, { withoutCaptions: false })}
              >
                <div className="flex items-center gap-2">
                  <ClosedCaption className="size-4 text-slate-700" />
                  <span>With Captions</span>
                </div>
                <span className="text-[10px] font-bold text-emerald-600 uppercase tracking-wider bg-emerald-50 px-1.5 py-0.5 rounded">
                  {isFree ? "720p" : "1080p HD"}
                </span>
              </DropdownMenuItem>

              <DropdownMenuItem
                className="flex items-center justify-between gap-3 px-3 py-2.5 text-xs font-semibold cursor-pointer rounded-lg hover:bg-slate-50 focus:bg-slate-50"
                onClick={() => onDownload(clip, { withoutCaptions: true })}
              >
                <div className="flex items-center gap-2">
                  <Video className="size-4 text-slate-700" />
                  <span>Without Captions</span>
                </div>
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                  Clean
                </span>
              </DropdownMenuItem>

              {isFree && (
                <>
                  <div className="my-1 h-px bg-slate-100" />
                  <DropdownMenuItem
                    className="flex items-center justify-between gap-3 px-3 py-2.5 text-xs font-semibold cursor-pointer rounded-lg hover:bg-slate-50 focus:bg-slate-50 text-slate-900"
                    onClick={() => {
                      trackCheckoutInitiated({ planId: "pro_upgrade" })
                      setShowUpgradeModal(true)
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <Sparkles className="size-4 text-amber-500 fill-amber-100" />
                      <span>Remove Watermark</span>
                    </div>
                    <span className="text-[10px] font-bold text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded uppercase">
                      Pro
                    </span>
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {showUpgradeModal && (
        <UpgradeModal
          open={showUpgradeModal}
          onOpenChange={setShowUpgradeModal}
        />
      )}
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
    a.viralReason === b.viralReason &&
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

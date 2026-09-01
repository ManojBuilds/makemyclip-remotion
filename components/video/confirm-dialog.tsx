"use client"

import React, { useState, useEffect, useRef } from "react"
import { Sparkles, Check, Loader2, Lock, ChevronDown, Clock, Globe2, FileVideo, Play } from "lucide-react"
import { getTargetClipCount } from "@/lib/clip-utils"
import { Button } from "@/components/ui/button"
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


// Helper function to format duration in MM:SS
function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || isNaN(seconds)) return ""
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, "0")}`
}

function formatShortSource(title: string | null | undefined): string {
  if (!title) return "Uploaded Video"
  return title.trim()
}

// ─── Caption Video Preview Card ───────────────────────────────────────────────

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
  const imageSrc = PREVIEW_IMAGES[id]
  const videoSrc = PREVIEW_VIDEOS[id]
  const [isHovered, setIsHovered] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    if (isHovered && videoRef.current) {
      videoRef.current.currentTime = 0
      videoRef.current.play().catch(() => { })
    } else if (!isHovered && videoRef.current) {
      videoRef.current.pause()
    }
  }, [isHovered])

  return (
    <div className="flex flex-col items-center gap-2">
      <button
        type="button"
        onClick={onSelect}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        className={cn(
          "group relative flex w-full flex-col overflow-hidden rounded-[16px] bg-black p-0 transition-all duration-180 ease-out select-none focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563EB]",
          selected
            ? "border-[2.5px] border-[#2563EB] shadow-lg shadow-[#2563EB]/25 scale-[1.02] -translate-y-[2px]"
            : "border border-[#E5E7EB] hover:border-[#2563EB]/40 hover:shadow-md hover:-translate-y-[2px]"
        )}
      >
        {/* Selected badge with checkmark icon */}
        {selected && (
          <div className="absolute top-2.5 right-2.5 z-30 flex h-6 w-6 items-center justify-center rounded-full bg-[#2563EB] text-white shadow-md animate-in fade-in zoom-in-95 duration-180">
            <Check className="h-3.5 w-3.5 stroke-[3] animate-in zoom-in-50 duration-180" />
          </div>
        )}

        {/* Locked presets */}
        {isLocked && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/40 backdrop-blur-[2px]">
            <div className="absolute top-2.5 right-2.5 flex items-center gap-1 rounded-full bg-slate-900/90 px-2 py-0.5 text-[10px] font-bold text-amber-300 shadow-md">
              <Lock className="h-2.5 w-2.5" />
              <span>Pro</span>
            </div>
          </div>
        )}

        {/* Video preview area — 16:9 ratio, enlarged by ~20% via container height */}
        <div className="relative aspect-video w-full overflow-hidden bg-slate-950">
          {imageSrc && (
            <img
              src={imageSrc}
              alt={`${template.name} preview`}
              loading="lazy"
              className={cn(
                "pointer-events-none absolute inset-0 h-full w-full object-cover transition-opacity duration-180",
                isLocked ? "blur-[1px] opacity-90" : "",
                isHovered && videoSrc ? "opacity-0" : "opacity-100"
              )}
            />
          )}
          {videoSrc && !isLocked && (
            <video
              ref={videoRef}
              src={videoSrc}
              loop
              muted
              playsInline
              className={cn(
                "pointer-events-none absolute inset-0 h-full w-full object-cover transition-opacity duration-180",
                isHovered ? "opacity-100" : "opacity-0"
              )}
            />
          )}
        </div>
      </button>

      {/* Preset Name underneath */}
      <span className={cn(
        "text-xs font-semibold tracking-tight transition-colors duration-180",
        selected ? "text-[#2563EB]" : "text-slate-700"
      )}>
        {template.name}
      </span>
    </div>
  )
}

// ─── Confirm Dialog ───────────────────────────────────────────────────────────

interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: (
    styling: CaptionTemplate,
    transcribeLang: string,
    translateLang: string,
    removeSilence: boolean
  ) => void
  isSubmitting: boolean
  thumbnail?: string | null
  videoTitle?: string | null
  duration?: number | null
  fetchingMetadata?: boolean
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
}: ConfirmDialogProps) {
  const { user } = useDashboardUser()
  const plan = user?.plan || "free"
  const isFree = plan === "free"

  const planLimitConfig = getPlanLimit(plan)
  const limit = planLimitConfig.maxUploadDurationSeconds
  const limitLabel = planLimitConfig.label
  const isOverLimit = duration ? duration > limit : false

  const [selectedTemplate, setSelectedTemplate] = useState<string>("impact")
  const [wordHighlight, setWordHighlight] = useState<boolean>(true)
  const [sourceLang, setSourceLang] = useState<string>("auto")
  const [translateLang, setTranslateLang] = useState<string>("none")
  const [removeSilence, setRemoveSilence] = useState<boolean>(true)
  const [isThumbnailLoading, setIsThumbnailLoading] = useState(true)
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false)

  const [activeUpgradeTrigger, setActiveUpgradeTrigger] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setSelectedTemplate("impact")
      setWordHighlight(CAPTION_TEMPLATES.impact?.wordHighlightDefault ?? true)
      setSourceLang("auto")
      setTranslateLang("none")
      setIsThumbnailLoading(true)
      setRemoveSilence(true)
      setShowAdvanced(false)

      if (isOverLimit && isFree && !hasDismissedPrompt("upload_limit")) {
        setActiveUpgradeTrigger("upload_limit")
      }
    }
  }, [open, thumbnail, isOverLimit, isFree])

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
      onConfirm(
        { ...styling, word_highlight: wordHighlight },
        sourceLang,
        translateLang,
        removeSilence
      )
    }
  }

  // Calculate estimated clips
  const clipEstimate = duration ? getTargetClipCount(duration) : { target: 3, max: 4 }
  const estimatedClipsText = `${clipEstimate.target}–${clipEstimate.max}`

  // Display language name for stat card
  const currentLangObj = LANGUAGES.find((l) => l.code === sourceLang)
  const displayLanguageName = sourceLang === "auto" ? "English" : (currentLangObj?.name || "English")
  const formattedDuration = formatDuration(duration)
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

            {/* 1. Video Section Preview */}
            <div className="space-y-2">
              <div className="group relative aspect-video w-full overflow-hidden rounded-[16px] border border-[#E5E7EB] bg-slate-950 shadow-xs">
                {thumbnail ? (
                  <>
                    {isThumbnailLoading && (
                      <Skeleton className="absolute inset-0 h-full w-full" />
                    )}
                    <Image
                      src={thumbnail}
                      alt="Video preview"
                      fill
                      className={cn(
                        "object-cover transition-opacity duration-180 group-hover:scale-[1.02]",
                        isThumbnailLoading ? "opacity-0" : "opacity-100"
                      )}
                      onLoad={() => setIsThumbnailLoading(false)}
                    />
                  </>
                ) : (
                  <div className="flex h-full w-full flex-col items-center justify-center gap-1.5 bg-slate-900 text-slate-400">
                    <FileVideo className="h-8 w-8 stroke-[1.5] text-slate-500" />
                    <span className="text-xs font-medium text-slate-400">Video Source Ready</span>
                  </div>
                )}

                {/* Play Button Overlay */}
                <div className="absolute inset-0 flex items-center justify-center bg-black/15 transition-opacity duration-180 group-hover:bg-black/25">
                  <div className="flex h-11 w-11 items-center justify-center rounded-full bg-slate-900/80 text-white backdrop-blur-md shadow-md transition-transform duration-180 group-hover:scale-110">
                    <Play className="h-5 w-5 fill-white ml-0.5" />
                  </div>
                </div>

                {/* Duration Badge */}
                {duration ? (
                  <div className="absolute bottom-2.5 right-2.5 rounded-md bg-slate-900/85 px-2 py-0.5 text-[11px] font-semibold text-white backdrop-blur-md shadow-xs font-mono">
                    {formattedDuration}
                  </div>
                ) : null}

                {/* Detected Language Badge */}
                <div className="absolute top-2.5 left-2.5 flex items-center gap-1 rounded-md bg-slate-900/85 px-2 py-0.5 text-[11px] font-semibold text-white backdrop-blur-md shadow-xs">
                  <Globe2 className="h-3 w-3 text-[#2563EB]" />
                  <span>{displayLanguageName}</span>
                </div>
              </div>

              {/* Video Title */}
              {videoTitle && (
                <div className="px-1 text-xs font-medium text-slate-600 truncate" title={videoTitle}>
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

            {/* 3. Caption Style Section (Visual Focus - ~20% enlarged preset cards) */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold tracking-tight text-slate-900">
                Caption Style
              </h3>
              <div className="grid grid-cols-3 gap-3.5">
                {Object.entries(CAPTION_TEMPLATES).map(([id, template]) => (
                  <CaptionPresetCard
                    key={id}
                    id={id}
                    template={template}
                    selected={selectedTemplate === id}
                    isLocked={false}
                    onSelect={() => handleSelectPreset(id)}
                  />
                ))}
              </div>
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
              disabled={isSubmitting}
              className="h-11 w-full rounded-[14px] bg-[#2563EB] text-sm font-semibold text-white shadow-sm transition-all duration-180 hover:bg-[#1d4ed8] hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Generating…
                </span>
              ) : isOverLimit ? (
                "Upgrade to Process Video"
              ) : (
                <span className="flex items-center justify-center gap-2">
                  ✨ Generate {estimatedClipsText} Clips
                </span>
              )}
            </Button>

            {/* Subtext */}
            <p className="mt-1.5 text-[11px] font-medium text-slate-400">
              Usually finishes in under 2 minutes
            </p>

            {/* Reassurance section */}
            <div className="mt-2.5 flex items-center justify-center gap-4 text-[10px] font-medium text-slate-500">
              <span className="flex items-center gap-1">
                <Check className="h-3 w-3 text-[#2563EB] stroke-[2.5]" />
                AI detects highlights
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

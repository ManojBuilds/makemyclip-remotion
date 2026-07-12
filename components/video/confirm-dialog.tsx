"use client"

import React, { useState, useEffect } from "react"
import { Sparkles, Upload, Check, Zap, Loader2 } from "lucide-react"
import { getTargetClipCount } from "@/lib/clip-utils"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Label } from "@/components/ui/label"
import { useDashboardUser } from "@/components/dashboard-context"
import { getPlanLimit, PREVIEW_IMAGES, LANGUAGES } from "@/lib/config"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
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



// ─── Caption Video Preview Card ───────────────────────────────────────────────

function CaptionPresetCard({
  id,
  template,
  selected,
  onSelect,
}: {
  id: string
  template: CaptionTemplate
  selected: boolean
  onSelect: () => void
}) {
  const imageSrc = PREVIEW_IMAGES[id]

  return (
    <Button
      variant="outline"
      size="icon"
      type="button"
      onClick={onSelect}
      className={cn(
        "group relative flex h-auto w-full flex-col items-stretch overflow-hidden rounded-2xl p-0 text-left transition-all duration-200 select-none focus-visible:ring-2 focus-visible:ring-primary",
        selected
          ? "border-primary shadow-md ring-2 shadow-primary/10 ring-primary/20"
          : "border-border hover:border-primary/40 hover:shadow-sm"
      )}
    >
      {/* Selected badge */}
      {selected && (
        <div className="absolute top-2.5 right-2.5 z-20 flex h-5 w-5 animate-in items-center justify-center rounded-full bg-primary shadow-sm duration-200 zoom-in">
          <Check className="h-3 w-3 text-primary-foreground" strokeWidth={3} />
        </div>
      )}

      {/* Video preview area — 16:9 ratio */}
      <div className="relative aspect-video w-full overflow-hidden bg-black">
        {imageSrc && (
          <img
            src={imageSrc}
            alt={`${template.name} preview`}
            loading="lazy"
            className="pointer-events-none absolute inset-0 h-full w-full scale-[1.4] object-cover"
          />
        )}
      </div>
    </Button>
  )
}

// ─── Confirm Dialog ───────────────────────────────────────────────────────────

interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: (
    styling: CaptionTemplate,
    transcribeLang: string,
    translateLang: string
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

  const planLimitConfig = getPlanLimit(plan)
  const limit = planLimitConfig.maxDurationSeconds
  const limitLabel = planLimitConfig.label
  const isOverLimit = duration ? duration > limit : false

  const [selectedTemplate, setSelectedTemplate] = useState<string>("hormozi")
  const [sourceLang, setSourceLang] = useState<string>("auto")
  const [translateLang, setTranslateLang] = useState<string>("none")
  const [isThumbnailLoading, setIsThumbnailLoading] = useState(true)

  useEffect(() => {
    if (open) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelectedTemplate("hormozi")
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSourceLang("auto")
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setTranslateLang("none")
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIsThumbnailLoading(true)
    }
  }, [open, thumbnail])

  const handleConfirm = () => {
    const styling = CAPTION_TEMPLATES[selectedTemplate]
    if (styling) onConfirm(styling, sourceLang, translateLang)
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(openState) => {
        if (isSubmitting) return
        onOpenChange(openState)
      }}
    >
      <DialogContent className="gap-0 overflow-hidden rounded-3xl bg-background p-0 shadow-2xl sm:max-w-[520px]">
        {/* Header */}
        <DialogHeader className="px-6 pt-6 pb-4 text-left">
          <DialogTitle className="text-base font-bold text-foreground">
            Create Shorts
          </DialogTitle>
          <p className="mt-0.5 text-xs font-medium text-muted-foreground">
            Select a caption style below. Hover each preset to preview the
            animation.
          </p>
        </DialogHeader>

        <Separator />

        {/* Scrollable body */}
        <div className="max-h-[72vh] space-y-4 overflow-y-auto overscroll-contain px-5 py-4">
          {/* Video thumbnail / title */}
          {thumbnail ? (
            <div className="relative mx-auto h-[120px] w-full max-w-[380px] overflow-hidden rounded-lg bg-muted">
              {isThumbnailLoading && (
                <Skeleton className="absolute inset-0 h-full w-full rounded-lg" />
              )}
              <Image
                src={thumbnail}
                alt="Video preview"
                width={380}
                height={120}
                className={cn(
                  "h-full w-full rounded-lg object-contain transition-opacity duration-300",
                  isThumbnailLoading ? "opacity-0" : "opacity-100"
                )}
                onLoad={() => setIsThumbnailLoading(false)}
              />
            </div>
          ) : videoTitle ? (
            <div className="flex items-center gap-3 rounded-2xl border border-border bg-muted/50 px-4 py-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10">
                <Upload className="h-5 w-5 text-primary" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[10px] font-semibold text-muted-foreground">
                  Selected
                </p>
                <p className="truncate text-sm font-bold text-foreground">
                  {videoTitle}
                </p>
              </div>
            </div>
          ) : null}

          {/* Live Estimate and Info Callout */}
          {fetchingMetadata ? (
            <div className="flex items-center justify-center gap-2 py-2 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Fetching video details...</span>
            </div>
          ) : duration ? (
            (() => {
              const durationInMinutes = Math.ceil(duration / 60)
              const { target, max } = getTargetClipCount(duration)
              return (
                <div className="flex flex-col gap-1.5 rounded-2xl border border-slate-100 bg-[#f8f9fa] p-3.5">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs font-semibold text-slate-700 font-mono">
                    <span>
                      {durationInMinutes} minute
                      {durationInMinutes === 1 ? "" : "s"}
                    </span>
                    <span className="text-slate-300">•</span>
                    <span>
                      {durationInMinutes} credit
                      {durationInMinutes === 1 ? "" : "s"}
                    </span>
                    <span className="text-slate-300">•</span>
                    <span className="flex items-center gap-1 font-bold text-[#0075de]">
                      <Sparkles className="h-3.5 w-3.5" />
                      We expect ~{target}-{max} strong clips
                    </span>
                  </div>
                  <p className="text-[11px] leading-normal font-medium text-muted-foreground">
                    We only surface moments strong enough to post — we skip the
                    rest so every clip is worth your time.
                  </p>
                  {isOverLimit && (
                    <div className="mt-2.5 rounded-xl border border-red-200 bg-red-50 p-3 text-red-800 text-[11px] font-medium leading-normal">
                      This video is {durationInMinutes} minutes long, which exceeds the {limitLabel} limit of your {plan.charAt(0).toUpperCase() + plan.slice(1)} plan.{" "}
                      <a href="/pricing" className="font-bold underline hover:text-red-950">
                        Upgrade plan
                      </a>{" "}
                      to process longer videos.
                    </div>
                  )}
                </div>
              )
            })()
          ) : null}

          {/* Languages selection */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label className="mb-1.5 block text-[10px] font-black tracking-widest text-muted-foreground uppercase">
                Source Language
              </Label>
              <Select value={sourceLang} onValueChange={setSourceLang}>
                <SelectTrigger className="w-full rounded-2xl">
                  <SelectValue placeholder="Select language" />
                </SelectTrigger>
                <SelectContent position="popper" className="max-h-[300px]">
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
              <Label className="mb-1.5 block text-[10px] font-black tracking-widest text-muted-foreground uppercase">
                Translate Caption
              </Label>
              <Select value={translateLang} onValueChange={setTranslateLang}>
                <SelectTrigger className="w-full rounded-2xl">
                  <SelectValue placeholder="Select language" />
                </SelectTrigger>
                <SelectContent position="popper" className="max-h-[300px]">
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

          {/* Captions grid */}
          <div>
            <div className="mb-3 flex items-center justify-between">
              <span className="text-[10px] font-black tracking-widest text-muted-foreground uppercase">
                Captions
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2.5">
              {Object.entries(CAPTION_TEMPLATES).map(([id, template]) => (
                <CaptionPresetCard
                  key={id}
                  id={id}
                  template={template}
                  selected={selectedTemplate === id}
                  onSelect={() => setSelectedTemplate(id)}
                />
              ))}
            </div>
          </div>
        </div>

        <Separator />

        {/* Footer */}
        <div className="flex items-center justify-between gap-4 bg-muted/30 px-5 pt-3.5 pb-5">
          <Button
            onClick={handleConfirm}
            disabled={isSubmitting || isOverLimit}
            className="h-11 w-full shrink-0 px-5"
          >
            <Sparkles className="h-4 w-4" />
            {isSubmitting ? "Generating…" : isOverLimit ? "Plan Limit Exceeded" : "Generate Clips"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

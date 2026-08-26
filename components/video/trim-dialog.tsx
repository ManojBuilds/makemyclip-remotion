"use client"

import React, { useState, useRef, useEffect, useCallback } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import {
  Play,
  Pause,
  Scissors,
  RotateCcw,
  Volume2,
  VolumeX,
  Loader2,
  Check,
} from "lucide-react"
import { cn } from "@/lib/utils"
import type { Clip } from "@/lib/types"
import { toast } from "sonner"

interface TrimDialogProps {
  clip: Clip | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaveTrim: (clipId: string, newStartTime: number, newEndTime: number) => Promise<void>
}

function formatTimecode(secs: number): string {
  if (isNaN(secs) || secs < 0) return "00:00.0"
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  const ms = Math.floor((secs % 1) * 10)
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${ms}`
}

function formatDuration(secs: number): string {
  if (isNaN(secs) || secs < 0) return "00:00.0"
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  const ms = Math.floor((secs % 1) * 10)
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${ms}`
}

// Waveform bar heights generator (consistent pseudo-randomized natural speech pattern)
const WAVEFORM_BARS = Array.from({ length: 72 }).map((_, i) => {
  const sin1 = Math.sin(i * 0.35) * 0.4
  const sin2 = Math.cos(i * 0.7) * 0.25
  const mod = ((i * 7) % 5) * 0.08
  const base = 0.3 + sin1 + sin2 + mod
  return Math.min(1, Math.max(0.18, base))
})

export function TrimDialog({
  clip,
  open,
  onOpenChange,
  onSaveTrim,
}: TrimDialogProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const timelineRef = useRef<HTMLDivElement>(null)

  const clipDuration = clip ? Math.max(0.1, clip.endTime - clip.startTime) : 1

  // Relative trim states (0 to clipDuration)
  const [trimStartRel, setTrimStartRel] = useState<number>(0)
  const [trimEndRel, setTrimEndRel] = useState<number>(clipDuration)
  const [currentTimeRel, setCurrentTimeRel] = useState<number>(0)
  const [isPlaying, setIsPlaying] = useState<boolean>(false)
  const [isMuted, setIsMuted] = useState<boolean>(false)
  const [isSaving, setIsSaving] = useState<boolean>(false)

  // Active drag state
  const [activeDrag, setActiveDrag] = useState<"start" | "end" | "window" | "playhead" | null>(null)
  const dragStartData = useRef<{
    startX: number
    initStart: number
    initEnd: number
    initPlayhead: number
    timelineWidth: number
  }>({ startX: 0, initStart: 0, initEnd: 0, initPlayhead: 0, timelineWidth: 1 })

  // Reset when dialog opens with a clip
  useEffect(() => {
    if (open && clip) {
      setTrimStartRel(0)
      setTrimEndRel(clip.endTime - clip.startTime)
      setCurrentTimeRel(0)
      setIsPlaying(false)
      setActiveDrag(null)
    }
  }, [open, clip])

  const videoUrl = clip ? (clip.previewVideoUrl || clip.originalVideoUrl || clip.captionVideoUrl) : null

  // Absolute timestamps
  const absoluteStartTime = clip ? clip.startTime + trimStartRel : 0
  const absoluteEndTime = clip ? clip.startTime + trimEndRel : 0

  // Sync video playback time
  const handleTimeUpdate = () => {
    if (!videoRef.current || activeDrag) return
    const time = videoRef.current.currentTime
    setCurrentTimeRel(time)

    // Loop strictly inside trimmed window
    if (time >= trimEndRel) {
      videoRef.current.currentTime = trimStartRel
      setCurrentTimeRel(trimStartRel)
    }
  }

  const togglePlay = () => {
    if (!videoRef.current) return
    if (isPlaying) {
      videoRef.current.pause()
      setIsPlaying(false)
    } else {
      if (videoRef.current.currentTime < trimStartRel || videoRef.current.currentTime >= trimEndRel) {
        videoRef.current.currentTime = trimStartRel
      }
      videoRef.current.play().catch(() => { })
      setIsPlaying(true)
    }
  }

  const seekTo = useCallback((relSeconds: number) => {
    const clamped = Math.max(0, Math.min(clipDuration, relSeconds))
    setCurrentTimeRel(clamped)
    if (videoRef.current) {
      videoRef.current.currentTime = clamped
    }
  }, [clipDuration])

  // Reset Trim to full clip duration
  const resetTrim = () => {
    setTrimStartRel(0)
    setTrimEndRel(clipDuration)
    seekTo(0)
    toast.info("Trim reset to original bounds")
  }

  // Save handler
  const handleSave = async () => {
    if (!clip) return
    if (trimEndRel <= trimStartRel + 0.5) {
      toast.error("Clip duration must be at least 0.5 seconds")
      return
    }

    try {
      setIsSaving(true)
      await onSaveTrim(clip.id, Number(absoluteStartTime.toFixed(2)), Number(absoluteEndTime.toFixed(2)))
      onOpenChange(false)
    } catch (err) {
      console.error("Trim save failed:", err)
      toast.error("Failed to save trimmed clip")
    } finally {
      setIsSaving(false)
    }
  }

  // Keyboard Shortcuts (Space to play/pause)
  useEffect(() => {
    if (!open) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.code === "Space") {
        e.preventDefault()
        togglePlay()
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [open, isPlaying, trimStartRel, trimEndRel, togglePlay])

  // Pointer drag handling with pointer capture for butter-smooth dragging
  const handlePointerDown = (
    type: "start" | "end" | "window" | "playhead",
    e: React.PointerEvent<HTMLDivElement>
  ) => {
    e.stopPropagation()
    e.preventDefault()
    e.currentTarget.setPointerCapture(e.pointerId)

    if (videoRef.current && isPlaying) {
      videoRef.current.pause()
      setIsPlaying(false)
    }

    const rect = timelineRef.current?.getBoundingClientRect()
    const width = rect?.width || 1

    dragStartData.current = {
      startX: e.clientX,
      initStart: trimStartRel,
      initEnd: trimEndRel,
      initPlayhead: currentTimeRel,
      timelineWidth: width,
    }

    setActiveDrag(type)
  }

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!activeDrag || !timelineRef.current) return
    const deltaX = e.clientX - dragStartData.current.startX
    const deltaSec = (deltaX / dragStartData.current.timelineWidth) * clipDuration

    if (activeDrag === "start") {
      const newStart = Math.max(
        0,
        Math.min(dragStartData.current.initEnd - 0.5, dragStartData.current.initStart + deltaSec)
      )
      setTrimStartRel(Number(newStart.toFixed(1)))
      seekTo(newStart)
    } else if (activeDrag === "end") {
      const newEnd = Math.min(
        clipDuration,
        Math.max(dragStartData.current.initStart + 0.5, dragStartData.current.initEnd + deltaSec)
      )
      setTrimEndRel(Number(newEnd.toFixed(1)))
      seekTo(newEnd)
    } else if (activeDrag === "window") {
      const windowLen = dragStartData.current.initEnd - dragStartData.current.initStart
      let newStart = dragStartData.current.initStart + deltaSec
      let newEnd = newStart + windowLen

      if (newStart < 0) {
        newStart = 0
        newEnd = windowLen
      } else if (newEnd > clipDuration) {
        newEnd = clipDuration
        newStart = clipDuration - windowLen
      }

      setTrimStartRel(Number(newStart.toFixed(1)))
      setTrimEndRel(Number(newEnd.toFixed(1)))
      seekTo(newStart)
    } else if (activeDrag === "playhead") {
      const newPlayhead = Math.max(
        0,
        Math.min(clipDuration, dragStartData.current.initPlayhead + deltaSec)
      )
      seekTo(newPlayhead)
    }
  }

  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (activeDrag) {
      try {
        e.currentTarget.releasePointerCapture(e.pointerId)
      } catch { }
      setActiveDrag(null)
    }
  }

  // Click on the timeline track to jump playhead
  const handleTrackClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (activeDrag || !timelineRef.current) return
    const rect = timelineRef.current.getBoundingClientRect()
    const clickX = e.clientX - rect.left
    const percent = Math.max(0, Math.min(1, clickX / rect.width))
    seekTo(percent * clipDuration)
  }

  // Percentages for timeline
  const startPercent = (trimStartRel / clipDuration) * 100
  const endPercent = (trimEndRel / clipDuration) * 100
  const playheadPercent = (currentTimeRel / clipDuration) * 100

  return (
    <Dialog open={open && Boolean(clip)} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[92vh] flex-col gap-0 overflow-hidden rounded-[28px] border border-slate-100 bg-white p-0 text-slate-900 shadow-2xl sm:max-w-[720px]">
        {/* Header */}
        <DialogHeader className="shrink-0 p-6 pb-2 text-left">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#EEF2FF] text-[#6366F1]">
              <Scissors className="h-5 w-5 stroke-[2.2]" />
            </div>
            <div>
              <DialogTitle className="text-xl font-bold text-slate-900 tracking-tight">
                Trim clip
              </DialogTitle>
              <DialogDescription className="mt-0.5 text-xs text-slate-500 font-normal">
                Drag the handles to select the part you want to keep.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {/* Modal Body */}
        <div className="flex-1 min-h-0 space-y-6 overflow-y-auto p-6 pt-3">
          {/* Video Preview Center */}
          <div className="relative mx-auto flex aspect-[9/16] max-h-[300px] w-auto overflow-hidden rounded-2xl bg-slate-950 shadow-md">
            {videoUrl ? (
              <video
                ref={videoRef}
                src={videoUrl}
                playsInline
                muted={isMuted}
                onTimeUpdate={handleTimeUpdate}
                onEnded={() => setIsPlaying(false)}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-xs text-slate-500">
                No video preview available
              </div>
            )}

            {/* Top Timecode Badge */}
            <div className="absolute top-3 left-1/2 -translate-x-1/2 rounded-md bg-black/60 px-2 py-0.5 text-[11px] font-mono font-medium text-white backdrop-blur-sm">
              {formatTimecode(currentTimeRel)} / {formatTimecode(clipDuration)}
            </div>

            {/* Bottom Floating Buttons */}
            <div className="absolute bottom-3 left-3 z-20">
              <button
                type="button"
                onClick={togglePlay}
                className="flex size-8 items-center justify-center rounded-full bg-black/60 text-white backdrop-blur-sm transition-transform hover:scale-105 active:scale-95"
              >
                {isPlaying ? (
                  <Pause className="size-3.5 fill-current" />
                ) : (
                  <Play className="size-3.5 fill-current translate-x-0.5" />
                )}
              </button>
            </div>

            <div className="absolute bottom-3 right-3 z-20">
              <button
                type="button"
                onClick={() => setIsMuted(!isMuted)}
                className="flex size-8 items-center justify-center rounded-full bg-black/60 text-white backdrop-blur-sm transition-transform hover:scale-105"
              >
                {isMuted ? <VolumeX className="size-3.5" /> : <Volume2 className="size-3.5" />}
              </button>
            </div>
          </div>

          {/* ─── TIMELINE SECTION ─── */}
          <div className="rounded-2xl border border-slate-100 bg-[#FBFBFF] p-4 shadow-xs">
            <div
              ref={timelineRef}
              onClick={handleTrackClick}
              className="relative h-14 w-full select-none cursor-pointer rounded-xl bg-[#F1F3F9] overflow-visible"
            >
              {/* Waveform Background Bars */}
              <div className="absolute inset-0 flex items-center justify-between px-2 pointer-events-none overflow-hidden rounded-xl">
                {WAVEFORM_BARS.map((height, i) => {
                  const barPercent = (i / WAVEFORM_BARS.length) * 100
                  const isInside = barPercent >= startPercent && barPercent <= endPercent
                  return (
                    <div
                      key={i}
                      className={cn(
                        "w-[3px] rounded-full transition-colors duration-150",
                        isInside ? "bg-[#818CF8]" : "bg-slate-300"
                      )}
                      style={{ height: `${height * 75}%` }}
                    />
                  )
                })}
              </div>

              {/* Active Selection Frame (Middle Box) */}
              <div
                onPointerDown={(e) => handlePointerDown("window", e)}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                className={cn(
                  "absolute top-0 bottom-0 cursor-grab border-y-2 border-[#6366F1] bg-[#6366F1]/10 transition-colors active:cursor-grabbing",
                  activeDrag === "window" && "bg-[#6366F1]/15"
                )}
                style={{
                  left: `${startPercent}%`,
                  width: `${Math.max(0, endPercent - startPercent)}%`,
                }}
              />

              {/* ─── LEFT TRIM HANDLE ─── */}
              <div
                onPointerDown={(e) => handlePointerDown("start", e)}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                className="absolute top-0 bottom-0 z-30 flex w-4 -translate-x-1/2 cursor-ew-resize items-center justify-center rounded-l-md bg-[#6366F1] shadow-sm transition-transform hover:scale-105 active:scale-110"
                style={{ left: `${startPercent}%` }}
              >
                {/* Grip Lines */}
                <div className="flex gap-[2px]">
                  <div className="h-4 w-[1.5px] rounded-full bg-white/90" />
                  <div className="h-4 w-[1.5px] rounded-full bg-white/90" />
                </div>

                {/* Floating Tooltip Bubble */}
                <div className="absolute -top-7 left-1/2 -translate-x-1/2 rounded-md bg-[#6366F1] px-1.5 py-0.5 text-[11px] font-mono font-bold text-white shadow-xs pointer-events-none whitespace-nowrap">
                  {formatTimecode(trimStartRel)}
                </div>
              </div>

              {/* ─── RIGHT TRIM HANDLE ─── */}
              <div
                onPointerDown={(e) => handlePointerDown("end", e)}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                className="absolute top-0 bottom-0 z-30 flex w-4 -translate-x-1/2 cursor-ew-resize items-center justify-center rounded-r-md bg-[#6366F1] shadow-sm transition-transform hover:scale-105 active:scale-110"
                style={{ left: `${endPercent}%` }}
              >
                {/* Grip Lines */}
                <div className="flex gap-[2px]">
                  <div className="h-4 w-[1.5px] rounded-full bg-white/90" />
                  <div className="h-4 w-[1.5px] rounded-full bg-white/90" />
                </div>

                {/* Floating Tooltip Bubble */}
                <div className="absolute -top-7 left-1/2 -translate-x-1/2 rounded-md bg-[#6366F1] px-1.5 py-0.5 text-[11px] font-mono font-bold text-white shadow-xs pointer-events-none whitespace-nowrap">
                  {formatTimecode(trimEndRel)}
                </div>
              </div>

              {/* ─── PLAYHEAD NEEDLE ─── */}
              <div
                onPointerDown={(e) => handlePointerDown("playhead", e)}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                className="absolute top-0 bottom-0 z-40 w-[2px] -translate-x-1/2 cursor-ew-resize bg-slate-900 shadow-xs pointer-events-none"
                style={{ left: `${playheadPercent}%` }}
              />
            </div>

            {/* Time Ticks */}
            <div className="mt-2.5 flex justify-between px-0.5 text-[11px] font-mono text-slate-400">
              <span>00:00.0</span>
              <span>{formatTimecode(clipDuration / 2)}</span>
              <span>{formatTimecode(clipDuration)}</span>
            </div>
          </div>
        </div>

        {/* Footer Bar */}
        <div className="shrink-0 flex items-center justify-between border-t border-slate-100 bg-white p-6 pt-4">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={resetTrim}
            className="flex h-10 items-center gap-1.5 rounded-xl border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <RotateCcw className="size-3.5" />
            Reset
          </Button>

          {/* Save Button */}
          <Button
            type="button"
            onClick={handleSave}
            disabled={isSaving}
            className="flex h-10 items-center gap-2 rounded-xl bg-[#6366F1] px-6 text-xs font-semibold text-white shadow-sm hover:bg-[#4F46E5] active:scale-95 disabled:opacity-50"
          >
            {isSaving ? (
              <>
                <Loader2 className="size-3.5 animate-spin" />
                Saving…
              </>
            ) : (
              <>
                <Check className="size-3.5 stroke-[3]" />
                Save clip
              </>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

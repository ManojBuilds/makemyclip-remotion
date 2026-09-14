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
  Subtitles,
  Sparkles,
  SlidersHorizontal,
  Flame,
} from "lucide-react"
import { cn } from "@/lib/utils"
import type { Clip } from "@/lib/types"
import type { ClipCaption } from "@/lib/db/schema"
import { toast } from "sonner"
import { TranscriptEditor } from "./transcript-editor"

export interface EditClipDialogProps {
  clip: Clip | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaveEdit?: (
    clipId: string,
    options: {
      newStartTime?: number
      newEndTime?: number
      newCaptions?: ClipCaption[]
    }
  ) => Promise<void>
  onSaveTrim?: (clipId: string, newStartTime: number, newEndTime: number) => Promise<void>
}

function formatTimecode(secs: number): string {
  if (isNaN(secs) || secs < 0) return "0.0s"
  if (secs >= 60) {
    const m = Math.floor(secs / 60)
    const s = (secs % 60).toFixed(1)
    return `${m}m ${s}s`
  }
  return `${secs.toFixed(1)}s`
}

// Waveform bar heights generator (consistent pseudo-randomized natural speech pattern)
const WAVEFORM_BARS = Array.from({ length: 64 }).map((_, i) => {
  const sin1 = Math.sin(i * 0.35) * 0.4
  const sin2 = Math.cos(i * 0.7) * 0.25
  const mod = ((i * 7) % 5) * 0.08
  const base = 0.3 + sin1 + sin2 + mod
  return Math.min(1, Math.max(0.18, base))
})

export function EditClipDialog({
  clip,
  open,
  onOpenChange,
  onSaveEdit,
  onSaveTrim,
}: EditClipDialogProps) {
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

  // Captions state
  const [editedCaptions, setEditedCaptions] = useState<ClipCaption[]>(clip?.captions || [])
  const [hasCaptionsChanged, setHasCaptionsChanged] = useState<boolean>(false)

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
      setEditedCaptions(clip.captions || [])
      setHasCaptionsChanged(false)
    }
  }, [open, clip])

  const videoUrl = clip ? (clip.previewVideoUrl || clip.originalVideoUrl || clip.captionVideoUrl) : null

  // Absolute timestamps
  const absoluteStartTime = clip ? clip.startTime + trimStartRel : 0
  const absoluteEndTime = clip ? clip.startTime + trimEndRel : 0

  const hasTrimChanged = trimStartRel > 0.05 || trimEndRel < clipDuration - 0.05

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

  // Snippet player for hearing a specific word
  const snippetTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const playSnippet = useCallback((start: number, end: number) => {
    if (!videoRef.current) return
    if (snippetTimeoutRef.current) {
      clearTimeout(snippetTimeoutRef.current)
    }
    videoRef.current.currentTime = start
    videoRef.current.play().catch(() => { })
    setIsPlaying(true)

    const durationMs = Math.max(120, (end - start) * 1000)
    snippetTimeoutRef.current = setTimeout(() => {
      if (videoRef.current) {
        videoRef.current.pause()
        setIsPlaying(false)
      }
    }, durationMs)
  }, [])

  useEffect(() => {
    return () => {
      if (snippetTimeoutRef.current) {
        clearTimeout(snippetTimeoutRef.current)
      }
    }
  }, [])

  // Reset handlers
  const resetTrim = () => {
    setTrimStartRel(0)
    setTrimEndRel(clipDuration)
    seekTo(0)
    toast.info("Trim bounds reset to full clip")
  }

  const resetCaptions = () => {
    setEditedCaptions(clip?.captions || [])
    setHasCaptionsChanged(false)
    toast.info("Subtitles reset to original")
  }

  // Save handler
  const handleSave = async () => {
    if (!clip) return
    if (hasTrimChanged && trimEndRel <= trimStartRel + 0.5) {
      toast.error("Clip duration must be at least 0.5 seconds")
      return
    }

    try {
      setIsSaving(true)

      const payload: {
        newStartTime?: number
        newEndTime?: number
        newCaptions?: ClipCaption[]
      } = {}

      if (hasTrimChanged) {
        payload.newStartTime = Number(absoluteStartTime.toFixed(2))
        payload.newEndTime = Number(absoluteEndTime.toFixed(2))
      }

      if (hasCaptionsChanged) {
        payload.newCaptions = editedCaptions
      }

      if (onSaveEdit) {
        await onSaveEdit(clip.id, payload)
      } else if (onSaveTrim && hasTrimChanged) {
        await onSaveTrim(
          clip.id,
          payload.newStartTime ?? clip.startTime,
          payload.newEndTime ?? clip.endTime
        )
      }

      onOpenChange(false)
    } catch (err) {
      console.error("Clip save failed:", err)
      toast.error("Failed to save clip updates")
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

  // Pointer drag handling for trim timeline
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
  const activeDuration = trimEndRel - trimStartRel

  return (
    <Dialog open={open && Boolean(clip)} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[92vh] h-[90vh] w-[96vw] sm:max-w-5xl flex-col gap-0 overflow-hidden rounded-[28px] border border-slate-200/90 bg-white p-0 text-slate-900 shadow-2xl">
        {/* Studio Top Navigation Bar (Sleek & Space-Efficient) */}
        <DialogHeader className="shrink-0 px-5 py-3 border-b border-slate-100 bg-white">
          <div className="flex items-center justify-between gap-3 pr-8">
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 font-bold text-xs">
                #
              </span>
              <DialogTitle className="text-sm sm:text-base font-bold text-slate-900 truncate">
                {clip?.title || "Edit Clip Studio"}
              </DialogTitle>
              {clip?.viralScore && (
                <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 text-[10px] font-extrabold text-emerald-700 border border-emerald-200/60 shrink-0">
                  <Flame className="size-3 fill-current text-emerald-500" />
                  {Math.round(clip.viralScore <= 10 ? clip.viralScore * 10 : clip.viralScore)}
                </span>
              )}
            </div>
          </div>
        </DialogHeader>

        {/* ── Studio Dual-Pane Body (Vizard.ai / OpusClip Workspace) ── */}
        <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-12 overflow-hidden">
          {/* ── LEFT PANE: Video Player & Timeline Trim (lg:col-span-5) ── */}
          <div className="lg:col-span-5 flex flex-col justify-between border-r border-slate-200/70 bg-slate-50/60 p-4 sm:p-5 overflow-y-auto">
            {/* 9:16 Black Video Container */}
            <div className="relative mx-auto flex aspect-[9/16] h-[360px] sm:h-[420px] max-h-[440px] w-auto items-center justify-center overflow-hidden rounded-2xl bg-slate-950 shadow-lg border border-slate-900">
              {videoUrl ? (
                <video
                  ref={videoRef}
                  src={videoUrl}
                  playsInline
                  muted={isMuted}
                  onTimeUpdate={handleTimeUpdate}
                  onEnded={() => setIsPlaying(false)}
                  className="h-full w-full object-contain"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-xs text-slate-500">
                  No video preview available
                </div>
              )}

              {/* Top Timecode Badge */}
              <div className="absolute top-2.5 left-1/2 -translate-x-1/2 rounded-md bg-black/60 px-2.5 py-0.5 text-[11px] font-mono font-medium text-white backdrop-blur-sm pointer-events-none">
                {formatTimecode(currentTimeRel)} / {formatTimecode(clipDuration)}
              </div>

              {/* Bottom Floating Play / Volume Controls */}
              <div className="absolute bottom-2.5 left-2.5 z-20">
                <button
                  type="button"
                  onClick={togglePlay}
                  aria-label={isPlaying ? "Pause video preview" : "Play video preview"}
                  className="flex size-8 items-center justify-center rounded-full bg-black/60 text-white backdrop-blur-sm transition-transform hover:scale-105 active:scale-95 focus-visible:ring-2 focus-visible:ring-white focus-visible:outline-none"
                >
                  {isPlaying ? (
                    <Pause className="size-4 fill-current" aria-hidden="true" />
                  ) : (
                    <Play className="size-4 fill-current translate-x-0.5" aria-hidden="true" />
                  )}
                </button>
              </div>

              <div className="absolute bottom-2.5 right-2.5 z-20">
                <button
                  type="button"
                  onClick={() => setIsMuted(!isMuted)}
                  aria-label={isMuted ? "Unmute audio" : "Mute audio"}
                  className="flex size-8 items-center justify-center rounded-full bg-black/60 text-white backdrop-blur-sm transition-transform hover:scale-105 focus-visible:ring-2 focus-visible:ring-white focus-visible:outline-none"
                >
                  {isMuted ? (
                    <VolumeX className="size-4" aria-hidden="true" />
                  ) : (
                    <Volume2 className="size-4" aria-hidden="true" />
                  )}
                </button>
              </div>
            </div>

            {/* Timeline Trim Box situated right below video */}
            <div className="mt-3.5  px-2.5 py-1">


              {/* Waveform Slider Track with spacing for handle bubbles */}
              <div
                ref={timelineRef}
                onClick={handleTrackClick}
                className="relative h-12 w-full select-none cursor-pointer rounded-xl bg-[#F1F3F9] overflow-visible"
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

                {/* Left Trim Handle */}
                <div
                  onPointerDown={(e) => handlePointerDown("start", e)}
                  onPointerMove={handlePointerMove}
                  onPointerUp={handlePointerUp}
                  className="absolute top-0 bottom-0 z-30 flex w-4 -translate-x-1/2 cursor-ew-resize items-center justify-center rounded-l-md bg-[#6366F1] shadow-sm transition-transform hover:scale-105 active:scale-110"
                  style={{ left: `${startPercent}%` }}
                >
                  <div className="flex gap-[2px]">
                    <div className="h-3.5 w-[1.5px] rounded-full bg-white/90" />
                    <div className="h-3.5 w-[1.5px] rounded-full bg-white/90" />
                  </div>
                  <div className="absolute -top-6 left-1/2 -translate-x-1/2 rounded-md bg-[#6366F1] px-1 py-0.2 text-[10px] font-mono font-bold text-white shadow-xs pointer-events-none whitespace-nowrap">
                    {formatTimecode(trimStartRel)}
                  </div>
                </div>

                {/* Right Trim Handle */}
                <div
                  onPointerDown={(e) => handlePointerDown("end", e)}
                  onPointerMove={handlePointerMove}
                  onPointerUp={handlePointerUp}
                  className="absolute top-0 bottom-0 z-30 flex w-4 -translate-x-1/2 cursor-ew-resize items-center justify-center rounded-r-md bg-[#6366F1] shadow-sm transition-transform hover:scale-105 active:scale-110"
                  style={{ left: `${endPercent}%` }}
                >
                  <div className="flex gap-[2px]">
                    <div className="h-3.5 w-[1.5px] rounded-full bg-white/90" />
                    <div className="h-3.5 w-[1.5px] rounded-full bg-white/90" />
                  </div>
                  <div className="absolute -top-6 left-1/2 -translate-x-1/2 rounded-md bg-[#6366F1] px-1 py-0.2 text-[10px] font-mono font-bold text-white shadow-xs pointer-events-none whitespace-nowrap">
                    {formatTimecode(trimEndRel)}
                  </div>
                </div>

                {/* Playhead Needle */}
                <div
                  onPointerDown={(e) => handlePointerDown("playhead", e)}
                  onPointerMove={handlePointerMove}
                  onPointerUp={handlePointerUp}
                  className="absolute top-0 bottom-0 z-40 w-[2px] -translate-x-1/2 cursor-ew-resize bg-slate-900 shadow-xs pointer-events-none"
                  style={{ left: `${playheadPercent}%` }}
                />
              </div>


            </div>
          </div>

          {/* ── RIGHT PANE: Document-Style Script Editor (lg:col-span-7) ── */}
          <div className="lg:col-span-7 flex flex-col h-full bg-white overflow-hidden">
            <TranscriptEditor
              captions={editedCaptions}
              currentTime={currentTimeRel}
              onSeek={seekTo}
              onPlaySnippet={playSnippet}
              onCaptionsChange={(newCaptions) => {
                setEditedCaptions(newCaptions)
                setHasCaptionsChanged(true)
              }}
              clipStartTime={absoluteStartTime}
              clipEndTime={absoluteEndTime}
            />
          </div>
        </div>

        {/* Studio Sticky Footer Bar */}
        <div className="shrink-0 flex items-center justify-between border-t border-slate-200/80 bg-white p-4 sm:p-5">
          <div className="flex items-center gap-2">
            {hasTrimChanged && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={resetTrim}
                className="h-8 gap-1.5 rounded-xl border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50"
              >
                <RotateCcw className="size-3" />
                <span>Reset Trim</span>
              </Button>
            )}

            {hasCaptionsChanged && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={resetCaptions}
                className="h-8 gap-1.5 rounded-xl border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50"
              >
                <RotateCcw className="size-3" />
                <span>Reset Subtitles</span>
              </Button>
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onOpenChange(false)}
              className="h-9 px-3.5 text-xs text-slate-500 hover:text-slate-800"
            >
              Cancel
            </Button>

            <Button
              type="button"
              onClick={handleSave}
              disabled={isSaving || (!hasTrimChanged && !hasCaptionsChanged)}
              className="flex h-9 sm:h-10 items-center gap-2 rounded-xl bg-indigo-600 px-5 sm:px-6 text-xs font-bold text-white shadow-sm hover:bg-indigo-700 active:scale-95 disabled:opacity-50"
            >
              {isSaving ? (
                <>
                  <Loader2 className="size-3.5 animate-spin" />
                  <span>Saving…</span>
                </>
              ) : (
                <>
                  <Check className="size-3.5 stroke-[3]" />
                  <span>
                    {hasTrimChanged && hasCaptionsChanged
                      ? "Save Trim & Subtitles"
                      : hasCaptionsChanged
                        ? "Save Subtitles"
                        : hasTrimChanged
                          ? "Save Trim"
                          : "No Changes"}
                  </span>
                </>
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// Backwards compatibility export
export const TrimDialog = EditClipDialog

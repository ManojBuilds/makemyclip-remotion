"use client"

import { useState, useEffect } from "react"
import { Check, Loader2, Video, Bell, BellOff } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import type { Project } from "@/lib/types"

const stepsConfig = [
  { id: "upload", title: "Uploading & pre-processing", durationMs: 4000 },
  { id: "analyze_video", title: "Analyzing video structure", durationMs: 14000 },
  { id: "transcribe", title: "Transcribing audio tracks", durationMs: 18000 },
  { id: "highlights", title: "Finding viral highlights", durationMs: 22000 },
  { id: "crop", title: "Cropping & creating clips", durationMs: 30000 },
]

function getYouTubeId(url?: string | null) {
  if (!url) return null
  const regExp =
    /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=|shorts\/)([^#\&\?]*).*/
  const match = url.match(regExp)
  return match && match[2].length === 11 ? match[2] : null
}

export function ProcessingSteps({ project }: { project: Project }) {
  const [notify, setNotify] = useState(true)
  const [permission, setPermission] = useState<string>(() => {
    if (typeof window !== "undefined" && "Notification" in window) {
      return Notification.permission
    }
    return "unsupported"
  })

  const [activeStepIndex, setActiveStepIndex] = useState(0)

  useEffect(() => {
    if (activeStepIndex >= stepsConfig.length - 1) return
    const currentStep = stepsConfig[activeStepIndex]
    const timer = setTimeout(() => {
      setActiveStepIndex((prev) => prev + 1)
    }, currentStep.durationMs)
    return () => clearTimeout(timer)
  }, [activeStepIndex])

  const handleNotifyToggle = async () => {
    if (typeof window === "undefined" || !("Notification" in window)) {
      toast.error("Browser notifications are not supported in this browser.")
      return
    }

    if (permission === "default") {
      const status = await Notification.requestPermission()
      setPermission(status)
      if (status === "granted") {
        toast.success("Browser notifications active!")
      } else if (status === "denied") {
        toast.error("Notification permission denied.")
      }
    } else if (permission === "denied") {
      toast.error("Notifications blocked in browser settings.")
    } else {
      setNotify(!notify)
      toast.info(notify ? "Notifications paused." : "Notifications active!")
    }
  }

  const youtubeId = getYouTubeId(project.sourceUrl)
  const thumbnailUrl = youtubeId
    ? `https://img.youtube.com/vi/${youtubeId}/maxresdefault.jpg`
    : null

  const fallbackThumbnailUrl = youtubeId
    ? `https://img.youtube.com/vi/${youtubeId}/hqdefault.jpg`
    : null

  return (
    <div className="mx-auto flex w-full max-w-[340px] flex-col items-stretch px-4 py-8 animate-in fade-in duration-300">
      
      {/* Featured Video Thumbnail */}
      <div className="relative aspect-[16/9] w-full overflow-hidden rounded-2xl border border-slate-100 bg-slate-50 shadow-md shadow-slate-100/50">
        {thumbnailUrl ? (
          <img 
            src={thumbnailUrl} 
            alt={project.title} 
            className="h-full w-full object-cover"
            onError={(e) => {
              e.currentTarget.src = fallbackThumbnailUrl || ""
            }}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center bg-slate-50">
            <Video className="size-6 text-slate-300" />
          </div>
        )}
        
        {/* Pulsing Glassmorphic Processing Overlay */}
        <div className="absolute inset-0 bg-black/10 flex items-center justify-center">
          <div className="flex items-center gap-1.5 rounded-full bg-white/95 px-3 py-1 shadow-md backdrop-blur-md">
            <Loader2 className="size-3 animate-spin text-blue-600" />
            <span className="text-[10px] font-bold tracking-wider text-slate-800 uppercase">
              Processing
            </span>
          </div>
        </div>
      </div>

      {/* Video Title & Notify Action Block */}
      <div className="mt-3.5 flex items-center justify-between gap-3 px-1">
        <h4 className="truncate text-sm font-bold text-slate-900 flex-1">
          {project.title}
        </h4>
        {permission !== "unsupported" && (
          <Button
            variant="ghost"
            onClick={handleNotifyToggle}
            className={cn(
              "h-7 gap-1 shrink-0 rounded-full px-2 text-[11px] font-semibold transition-all",
              permission === "denied"
                ? "text-rose-500 bg-rose-50/50 hover:bg-rose-100/50"
                : permission === "default"
                  ? "text-blue-600 bg-blue-50/50 hover:bg-blue-100/50"
                  : notify
                    ? "text-rose-500 bg-rose-50/50 hover:bg-rose-100/50"
                    : "text-slate-400 bg-slate-50 hover:bg-slate-100"
            )}
          >
            {permission === "denied" ? <BellOff className="size-3" /> : <Bell className="size-3" />}
            <span>{permission === "denied" ? "Blocked" : notify && permission !== "default" ? "Mute" : "Notify"}</span>
          </Button>
        )}
      </div>

      {/* Compact Checklist */}
      <div className="mt-4.5 space-y-3.5 border-t border-slate-100/80 pt-4">
        {stepsConfig.map((step, idx) => {
          const isDone = idx < activeStepIndex
          const isActive = idx === activeStepIndex

          return (
            <div key={step.id} className="flex items-center gap-3">
              <div className="flex size-5 shrink-0 items-center justify-center">
                {isDone ? (
                  <div className="flex size-5 items-center justify-center rounded-full bg-emerald-500 text-white">
                    <Check className="size-3" strokeWidth={3.5} />
                  </div>
                ) : isActive ? (
                  <div className="flex size-5 items-center justify-center rounded-full bg-blue-50 text-blue-600">
                    <Loader2 className="size-3.5 animate-spin" />
                  </div>
                ) : (
                  <div className="size-4.5 rounded-full border-2 border-slate-200 bg-transparent" />
                )}
              </div>
              <span
                className={cn(
                  "text-sm font-semibold transition-colors",
                  isActive
                    ? "text-slate-800"
                    : isDone
                      ? "text-slate-400"
                      : "text-slate-300"
                )}
              >
                {step.title}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

"use client"

import { useState } from "react"
import { Check, Loader2, Sparkles, Video } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { getTargetClipCount } from "@/lib/clip-utils"
import { toast } from "sonner"
import type { Project } from "@/lib/types"

const displaySteps = [
  { id: "uploading", title: "Uploading" },
  { id: "processing", title: "Transcribing" },
  { id: "analyzing", title: "Finding highlights" },
  { id: "ready", title: "Creating clips" },
]

function getYouTubeId(url?: string | null) {
  if (!url) return null
  const regExp =
    /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=|shorts\/)([^#\&\?]*).*/
  const match = url.match(regExp)
  return match && match[2].length === 11 ? match[2] : null
}

const formatDuration = (seconds?: number | null) => {
  if (!seconds) return ""
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${String(secs).padStart(2, "0")}`
}

export function ProcessingSteps({ project }: { project: Project }) {
  const [notify, setNotify] = useState(true)
  const [permission, setPermission] = useState<string>(() => {
    if (typeof window !== "undefined" && "Notification" in window) {
      return Notification.permission
    }
    return "unsupported"
  })
  const status = project.status || "processing"

  const handleNotifyToggle = async () => {
    if (typeof window === "undefined" || !("Notification" in window)) {
      toast.error("Browser notifications are not supported in this browser.")
      return
    }

    if (permission === "default") {
      const status = await Notification.requestPermission()
      setPermission(status)
      if (status === "granted") {
        toast.success(
          "Browser notifications active! We will alert you when your clips are ready."
        )
        new Notification("Kivio", {
          body: "Browser notifications enabled! We'll alert you here when your clips are ready.",
          icon: "/favicon.ico",
        })
      } else if (status === "denied") {
        toast.error(
          "Notification permission denied. Please reset permissions in site settings to enable."
        )
      }
    } else if (permission === "denied") {
      toast.error(
        "Notification permission is blocked. Please reset permissions in your browser's address bar to enable."
      )
    } else {
      setNotify(!notify)
      if (notify) {
        toast.info(
          "Notifications paused. We won't alert you when the clips are ready."
        )
      } else {
        toast.success(
          "Notifications active! We will alert you when the clips are ready."
        )
      }
    }
  }

  const getStepStatus = (stepId: string, currentStatus: string) => {
    const states = ["uploading", "processing", "analyzing", "ready"]
    const currentIdx = states.indexOf(currentStatus)
    const stepIdx = states.indexOf(stepId)

    if (currentIdx === -1 || stepIdx === -1) {
      return { done: false, active: false }
    }

    if (currentIdx > stepIdx) {
      return { done: true, active: false }
    }
    if (currentIdx === stepIdx) {
      return { done: false, active: true }
    }
    return { done: false, active: false }
  }

  const youtubeId = getYouTubeId(project.sourceUrl)
  const thumbnailUrl = youtubeId
    ? `https://img.youtube.com/vi/${youtubeId}/mqdefault.jpg`
    : null

  const durationStr = formatDuration(project.duration)

  // Dynamic subheading message based on current status
  const getSubheading = () => {
    switch (status) {
      case "uploading":
        return "Uploading video..."
      case "processing":
        return "Transcribing audio..."
      case "analyzing":
        return "Finding clips..."
      case "ready":
        return "Clips ready!"
      default:
        return "Finding clips..."
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-[420px] flex-col items-start px-4 py-16 sm:py-24">
      {/* 1. Header Card (Video info & completed upload bar) */}
      <div className="w-full rounded-2xl border border-slate-100 bg-white p-3.5 shadow-md shadow-slate-100/80">
        <div className="flex items-center gap-3">
          {/* Thumbnail */}
          <div className="relative flex aspect-[4/3] w-16 shrink-0 items-center justify-center overflow-hidden rounded border border-slate-100 bg-slate-50">
            {thumbnailUrl ? (
              <img
                src={thumbnailUrl}
                alt={project.title}
                className="h-full w-full object-cover"
              />
            ) : (
              <Video className="size-5 text-slate-400" />
            )}
          </div>

          {/* Details */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <h4 className="truncate text-xs font-semibold text-slate-800 sm:text-sm">
                {project.title}
              </h4>
              <span className="shrink-0 rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[9px] font-bold tracking-wider text-slate-400 uppercase">
                1080p
              </span>
            </div>

            {/* Completed Progress Bar */}
            <div className="mt-2 h-[5px] w-full rounded-full bg-emerald-500" />

            {/* Footer details of card */}
            <div className="mt-2 flex items-center justify-between text-[11px] font-medium text-slate-400">
              <span>
                Upload successful{durationStr ? ` (${durationStr})` : ""}
              </span>
              <div className="flex size-4 items-center justify-center rounded-full bg-emerald-500 text-white">
                <Check className="size-2.5" strokeWidth={3} />
              </div>
            </div>
          </div>
        </div>

        {/* Live Estimate and Info Callout */}
        {project.duration
          ? (() => {
            const durationInMinutes = Math.ceil(project.duration / 60)
            const { target, max } = getTargetClipCount(project.duration)
            return (
              <div className="mt-3.5 flex flex-col gap-1.5 rounded-xl border border-slate-100 bg-[#f8f9fa] p-3">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] font-bold text-slate-700">
                  <span>{durationInMinutes} min</span>
                  <span className="text-slate-300">•</span>
                  <span>{durationInMinutes} credits</span>
                  <span className="text-slate-300">•</span>
                  <span className="flex items-center gap-1 font-bold text-[#0075de]">
                    <Sparkles className="h-3 w-3" />
                    We expect ~{target}-{max} strong clips
                  </span>
                </div>
                <p className="text-[10px] leading-normal font-medium text-slate-400">
                  We only keep the most engaging moments and skip the rest to save you editing time.
                </p>
              </div>
            )
          })()
          : null}
      </div>



      <h2 className="text-left text-xl leading-snug font-bold tracking-tight text-slate-900 sm:text-2xl mt-6">
        You can close this tab. We&apos;ll notify you when your clips are ready.
      </h2>

      {/* 4. Subheading with Notification link */}
      <p className="mt-2.5 text-left text-sm font-medium text-slate-500">
        {getSubheading()}{" "}
        {permission !== "unsupported" && (
          <Button
            variant="link"
            onClick={handleNotifyToggle}
            className={cn(
              "inline h-auto p-0 font-semibold underline transition-colors hover:no-underline",
              permission === "denied"
                ? "text-rose-500 hover:text-rose-600"
                : permission === "default"
                  ? "text-blue-600 hover:text-blue-700"
                  : notify
                    ? "text-rose-500 hover:text-rose-600"
                    : "text-slate-400 hover:text-slate-600"
            )}
          >
            {permission === "denied"
              ? "Notifications blocked."
              : permission === "default"
                ? "Notify me."
                : notify
                  ? "Do not notify."
                  : "Notify me."}
          </Button>
        )}
      </p>

      {/* 5. Progress Steps Checklist */}
      <div className="mt-8 w-full space-y-4">
        {displaySteps.map((step) => {
          const { done, active } = getStepStatus(step.id, status)

          return (
            <div key={step.id} className="flex items-center gap-3.5 py-0.5">
              <div className="flex size-5 shrink-0 items-center justify-center">
                {done ? (
                  <div className="flex size-5 items-center justify-center rounded-full bg-emerald-500 text-white shadow-sm shadow-emerald-100">
                    <Check className="size-3" strokeWidth={3} />
                  </div>
                ) : active ? (
                  <Loader2 className="size-4.5 animate-spin text-slate-800" />
                ) : (
                  <div className="size-4.5 rounded-full border-2 border-slate-200 bg-transparent" />
                )}
              </div>
              <span
                className={cn(
                  "text-sm font-semibold transition-colors",
                  active
                    ? "text-slate-900"
                    : done
                      ? "text-slate-500"
                      : "text-slate-300"
                )}
              >
                {step.title}
                {active && status === "analyzing" && " (finding clips)"}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

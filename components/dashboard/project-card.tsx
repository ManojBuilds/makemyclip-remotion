"use client"

import Link from "next/link"
import { cn } from "@/lib/utils"
import {
  Clock,
  Video,
  ChevronRight,
  Calendar,
  Layers,
  Sparkles,
  Upload,
  LucideIcon,
} from "lucide-react"
import type { Project } from "@/lib/types"

export const STATUS_CONFIG: Record<
  string,
  { label: string; color: string; icon: LucideIcon }
> = {
  uploading: {
    label: "Uploading",
    color: "text-blue-600 bg-blue-50 border-blue-100",
    icon: Upload,
  },
  processing: {
    label: "Processing",
    color: "text-amber-600 bg-amber-50 border-amber-100",
    icon: Layers,
  },
  analyzing: {
    label: "Analyzing",
    color: "text-indigo-600 bg-indigo-50 border-indigo-100",
    icon: Sparkles,
  },
  ready: {
    label: "Ready",
    color: "text-emerald-600 bg-emerald-50 border-emerald-100",
    icon: Video,
  },
  error: {
    label: "Error",
    color: "text-rose-600 bg-rose-50 border-rose-100",
    icon: Sparkles,
  },
}

export function ProjectCard({ project }: { project: Project }) {
  const config = STATUS_CONFIG[project.status] || STATUS_CONFIG.processing
  const StatusIcon = config.icon

  return (
    <Link href={`/projects/${project.id}`}>
      <div className="group relative flex h-full flex-col overflow-hidden rounded-xl border border-hairline bg-white p-6 transition-all duration-300 hover:border-primary/40 hover:shadow-md">
        {/* Hover Gradient Effect */}
        <div className="absolute top-0 right-0 h-32 w-32 translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/5 opacity-0 blur-3xl transition-opacity duration-300 group-hover:opacity-100" />

        <div className="mb-6 flex items-start justify-between">
          <div className="space-y-1.5">
            <h3 className="line-clamp-1 text-lg font-bold text-slate-900 transition-colors group-hover:text-primary">
              {project.title}
            </h3>
            <div className="flex items-center gap-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
              <Calendar className="h-3 w-3" />
              {new Date(project.createdAt).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
              })}
            </div>
          </div>
          <div
            className={cn(
              "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold tracking-widest uppercase transition-all duration-300",
              config.color
            )}
          >
            <StatusIcon className="h-3 w-3" />
            {config.label}
          </div>
        </div>

        <div className="mt-auto space-y-5">
          <div className="flex items-center gap-5 text-xs font-bold text-slate-600">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-slate-50 text-slate-400 transition-colors group-hover:bg-primary/10 group-hover:text-primary">
                <Clock className="h-4 w-4" />
              </div>
              <span>
                {project.duration
                  ? `${Math.floor(project.duration / 60)}m ${Math.floor(project.duration % 60)}s`
                  : "—"}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-slate-50 text-slate-400 transition-colors group-hover:bg-primary/10 group-hover:text-primary">
                <Video className="h-4 w-4" />
              </div>
              <span>{project.clipCount ?? 0} clips</span>
            </div>
          </div>

          {project.status === "processing" && (
            <div className="space-y-2">
              <div className="flex justify-between text-[10px] font-bold tracking-widest text-primary uppercase">
                <span>Optimizing</span>
                <span>45%</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                <div className="h-full w-[45%] animate-pulse bg-primary" />
              </div>
            </div>
          )}

          <div className="flex items-center justify-between border-t border-slate-50 pt-4">
            <span className="text-[11px] font-bold tracking-widest text-slate-400 uppercase transition-colors group-hover:text-primary">
              View Details
            </span>
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-50 text-slate-400 transition-all group-hover:translate-x-1 group-hover:bg-primary group-hover:text-white">
              <ChevronRight className="h-4 w-4" />
            </div>
          </div>
        </div>
      </div>
    </Link>
  )
}

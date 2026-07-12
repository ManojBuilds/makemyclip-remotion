"use client"

import Link from "next/link"
import { cn } from "@/lib/utils"
import { Check, Loader2 } from "lucide-react"
import type { Project } from "@/lib/types"

const STATUS_LABEL: Record<string, string> = {
  ready: "Ready",
  uploading: "Uploading",
  processing: "Processing",
  analyzing: "Processing",
}

export function ProjectListItem({ project }: { project: Project }) {
  const isReady = project.status === "ready"
  const label = STATUS_LABEL[project.status] ?? "Processing"

  return (
    <Link href={`/projects/${project.id}`} className="block">
      <div className="group flex items-center justify-between gap-4 rounded-lg border border-hairline bg-white px-4 py-3.5 transition-colors hover:border-slate-300 sm:px-5">
        <div className="min-w-0 space-y-0.5">
          <h3 className="truncate text-sm font-medium text-slate-900">
            {project.title}
          </h3>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span>{new Date(project.createdAt).toLocaleDateString()}</span>
            {isReady && (
              <>
                <span className="text-slate-300">·</span>
                <span>{project.clipCount ?? 0} clips</span>
              </>
            )}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1.5 text-xs text-slate-500">
          {isReady ? (
            <Check className="size-3.5 text-emerald-500" strokeWidth={2.5} />
          ) : (
            <Loader2 className="size-3.5 animate-spin text-slate-400" />
          )}
          <span className={cn(isReady && "text-slate-400")}>{label}</span>
        </div>
      </div>
    </Link>
  )
}

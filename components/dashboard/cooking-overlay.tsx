"use client"

import { Progress } from "@/components/ui/progress"

export function CookingOverlay({
  status,
  progress,
}: {
  status: string
  progress: number
}) {
  return (
    <div className="mx-auto max-w-2xl animate-in pt-2 duration-1000 zoom-in-95 fade-in sm:pt-4">
      <div className="flex flex-col items-center space-y-7 rounded-xl border border-hairline bg-white p-6 text-center shadow-md sm:space-y-10 sm:p-10 md:p-16">
        <div className="w-full max-w-sm space-y-2">
          <Progress value={progress} className="h-2 bg-slate-100" />
          <div className="flex items-center justify-between px-1">
            <p className="text-xs text-slate-500">Uploading video</p>
            <p className="text-xs text-slate-400">{progress}%</p>
          </div>
        </div>
      </div>
    </div>
  )
}

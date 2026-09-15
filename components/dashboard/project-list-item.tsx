"use client"

import { useState } from "react"
import Link from "next/link"
import { Video } from "lucide-react"
import type { Project } from "@/lib/types"

function getYouTubeId(url?: string | null) {
  if (!url) return null
  const regExp =
    /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=|shorts\/)([^#\&\?]*).*/
  const match = url.match(regExp)
  return match && match[2].length === 11 ? match[2] : null
}

export function ProjectListItem({ project }: { project: Project }) {
  const [imgError, setImgError] = useState(false)
  const [videoError, setVideoError] = useState(false)

  const youtubeId = getYouTubeId(project.sourceUrl)
  const thumbnailUrl = youtubeId
    ? `https://img.youtube.com/vi/${youtubeId}/maxresdefault.jpg`
    : project.thumbnailUrl || null

  const fallbackThumbnailUrl = youtubeId
    ? `https://img.youtube.com/vi/${youtubeId}/hqdefault.jpg`
    : null

  const directVideoUrl = !youtubeId
    ? project.videoUrl ||
      (project.sourceUrl && !project.sourceUrl.includes("drive.google.com")
        ? project.sourceUrl
        : null)
    : null

  return (
    <Link
      href={`/projects/${project.id}`}
      className="group block focus:outline-none"
      title={project.title}
    >
      {/* Video Thumbnail */}
      <div className="relative aspect-[16/9] w-full overflow-hidden rounded-xl bg-slate-900">
        {thumbnailUrl && !imgError ? (
          <img
            src={thumbnailUrl}
            alt={project.title}
            className="h-full w-full object-cover transform-gpu transition-all duration-200 ease-out group-hover:scale-[1.02] group-hover:brightness-[1.03]"
            onError={(e) => {
              if (
                fallbackThumbnailUrl &&
                e.currentTarget.src !== fallbackThumbnailUrl
              ) {
                e.currentTarget.src = fallbackThumbnailUrl
              } else {
                setImgError(true)
              }
            }}
          />
        ) : directVideoUrl && !videoError ? (
          <video
            src={
              directVideoUrl.includes("#")
                ? directVideoUrl
                : `${directVideoUrl}#t=0.001`
            }
            muted
            playsInline
            preload="metadata"
            className="h-full w-full object-cover transform-gpu transition-all duration-200 ease-out group-hover:scale-[1.02] group-hover:brightness-[1.03]"
            onError={() => setVideoError(true)}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center bg-slate-50">
            <Video className="size-5 text-slate-300" />
          </div>
        )}

      </div>

      {/* Video Title */}
      <h4 className="mt-1.5 truncate text-xs font-medium text-slate-700 transition-colors duration-200 group-hover:text-slate-950">
        {project.title}
      </h4>
    </Link>
  )
}

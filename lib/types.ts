import type { ReframeKeyframe, ClipCaption } from "@/lib/db/schema"

export type Project = {
  id: string
  title: string
  status: "uploading" | "processing" | "analyzing" | "ready" | "error" | string
  createdAt: string | Date
  videoUrl?: string
  sourceUrl?: string | null
  isYouTube?: boolean
  duration?: number | null
  clipCount?: number
}

export type Clip = {
  id: string
  title: string
  hookText: string
  startTime: number
  endTime: number
  viralScore: number
  viralReason: string
  status: string
  updatedAt?: string | Date | null
  originalVideoUrl?: string | null
  previewVideoUrl?: string | null
  captionVideoUrl?: string | null
  captionStyle: string
  renderStatus?: string | null
  renderProgress?: number
  reframeKeyframes?: ReframeKeyframe[] | null
  captions?: ClipCaption[] | null
  renderedUrl?: string | null
  clipType?: string | null
  speakerDynamic?: string | null
  thumbnailUrl?: string | null
  description?: string | null
  hashtags?: string | null
}

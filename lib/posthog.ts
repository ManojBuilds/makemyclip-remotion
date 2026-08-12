import posthog from "posthog-js"

export interface VideoUploadStartedProps {
  source: "youtube" | "file"
  fileSizeMb?: number
  videoDurationEst?: number
}

export interface ClipRenderStartedProps {
  projectId: string
  clipId: string
  aspectRatio?: string
  captionStyle?: string
}

export interface CheckoutInitiatedProps {
  planId: string
  billingCycle?: "monthly" | "yearly" | "one_time"
  priceCents?: number
}

export interface ClipDownloadedProps {
  projectId?: string
  clipId: string
}

/**
 * Track when a user begins uploading a video file or submitting a YouTube link.
 */
export function trackVideoUploadStarted(props: VideoUploadStartedProps) {
  if (typeof window !== "undefined") {
    posthog.capture("video_upload_started", {
      source: props.source,
      file_size_mb: props.fileSizeMb,
      video_duration_est: props.videoDurationEst,
    })
  }
}

/**
 * Track when a user triggers clip rendering/export.
 */
export function trackClipRenderStarted(props: ClipRenderStartedProps) {
  if (typeof window !== "undefined") {
    posthog.capture("clip_render_started", {
      project_id: props.projectId,
      clip_id: props.clipId,
      aspect_ratio: props.aspectRatio,
      caption_style: props.captionStyle,
    })
  }
}

/**
 * Track when a user clicks to upgrade or initiate checkout.
 */
export function trackCheckoutInitiated(props: CheckoutInitiatedProps) {
  if (typeof window !== "undefined") {
    posthog.capture("checkout_initiated", {
      plan_id: props.planId,
      billing_cycle: props.billingCycle,
      price_cents: props.priceCents,
    })
  }
}

/**
 * Track when a user downloads a rendered video clip.
 */
export function trackClipDownloaded(props: ClipDownloadedProps) {
  if (typeof window !== "undefined") {
    posthog.capture("clip_downloaded", {
      project_id: props.projectId,
      clip_id: props.clipId,
    })
  }
}

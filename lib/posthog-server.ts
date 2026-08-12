import { PostHog } from "posthog-node"

let serverPostHogClient: PostHog | null = null

export function getPostHogServerClient(): PostHog | null {
  if (serverPostHogClient) return serverPostHogClient

  const token = process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN
  const host =
    process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com"

  if (!token) {
    return null
  }

  serverPostHogClient = new PostHog(token, {
    host,
    flushAt: 1,
    flushInterval: 0,
  })

  return serverPostHogClient
}

export interface ServerVideoAnalysisCompletedProps {
  distinctId: string
  projectId: string
  durationSeconds?: number
  clipsCount?: number
  processingTimeMs?: number
}

export interface ServerClipRenderCompletedProps {
  distinctId: string
  projectId: string
  clipId: string
  renderTimeMs?: number
  resolution?: string
}

export interface ServerPaymentCompletedProps {
  distinctId: string
  planId: string
  amountCents: number
  currency?: string
  customerId?: string
}

/**
 * Server-side tracking for when AI video analysis finishes.
 */
export async function trackServerVideoAnalysisCompleted(
  props: ServerVideoAnalysisCompletedProps
) {
  const client = getPostHogServerClient()
  if (!client) return

  client.capture({
    distinctId: props.distinctId,
    event: "video_analysis_completed",
    properties: {
      project_id: props.projectId,
      duration_seconds: props.durationSeconds,
      clips_count: props.clipsCount,
      processing_time_ms: props.processingTimeMs,
    },
  })
}

/**
 * Server-side tracking when clip rendering finishes successfully.
 */
export async function trackServerClipRenderCompleted(
  props: ServerClipRenderCompletedProps
) {
  const client = getPostHogServerClient()
  if (!client) return

  client.capture({
    distinctId: props.distinctId,
    event: "clip_render_completed",
    properties: {
      project_id: props.projectId,
      clip_id: props.clipId,
      render_time_ms: props.renderTimeMs,
      resolution: props.resolution,
    },
  })
}

/**
 * Server-side tracking for successful payments (e.g. from Dodo Payment Webhooks).
 */
export async function trackServerPaymentCompleted(
  props: ServerPaymentCompletedProps
) {
  const client = getPostHogServerClient()
  if (!client) return

  client.capture({
    distinctId: props.distinctId,
    event: "payment_completed",
    properties: {
      plan_id: props.planId,
      amount_cents: props.amountCents,
      currency: props.currency || "USD",
      customer_id: props.customerId,
    },
  })
}

import { serve } from "inngest/next"
import { inngest } from "@/lib/inngest/client"
import {
  processVideo,
  renderClip,
  exportClip,
  batchReframeProject,
} from "@/lib/inngest/functions"

export const maxDuration = 300
export const dynamic = "force-dynamic"

// Create an API that serves zero functions
export const { GET, POST, PUT } = serve({
  client: inngest,
  functions: [processVideo, renderClip, exportClip, batchReframeProject],
})

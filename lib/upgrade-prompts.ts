import { PLAN_LIMITS } from "@/lib/config"

export interface UpgradePrompt {
  id: string
  title: string
  description: string
  cta: string
  targetPlan: "Creator" | "Power"
  badgeText?: string
  highlights: string[]
}

const freeLimitLabel = PLAN_LIMITS.free.label.replace("/video", "")
const powerLimitLabel = PLAN_LIMITS.power.label.replace("/video", "")

export const UPGRADE_PROMPTS: Record<string, UpgradePrompt> = {
  upload_limit: {
    id: "upload_limit",
    title: "Process videos up to 2 Hours",
    description: `Your Free plan supports videos up to ${freeLimitLabel}. Upgrade to Creator to process longer podcasts, interviews, and webinars.`,
    cta: "Upgrade to Creator ($15/mo)",
    targetPlan: "Creator",
    badgeText: "Extended Uploads",
    highlights: [
      "Process long-form podcasts & interviews up to 2 hours",
      "300 processing minutes every month (2x Opus Clip Starter)",
      "Unlock 1080p Full HD exports without watermark",
    ],
  },
  export_4k: {
    id: "export_4k",
    title: "Export in Full HD",
    description:
      "Unlock crystal-clear 1080p Full HD exports and no watermark with the Creator plan for just $15/mo.",
    cta: "Upgrade to Creator ($15/mo)",
    targetPlan: "Creator",
    badgeText: "1080p HD Quality",
    highlights: [
      "Full 1080p HD rendering without watermark",
      "Crisp video quality tailored for TikTok, Reels & Shorts",
      "300 minutes / month included",
    ],
  },
  export_1080p: {
    id: "export_1080p",
    title: "Export in Full HD",
    description:
      "Upgrade to Creator to remove watermarks and export in beautiful 1080p for just $15/mo.",
    cta: "Upgrade to Creator ($15/mo)",
    targetPlan: "Creator",
    badgeText: "Full HD Quality",
    highlights: [
      "Crisp 1080p resolution for all social channels",
      "Clean export with zero watermark",
      "300 minutes / month (2x Opus Clip Starter)",
    ],
  },
  caption_styles: {
    id: "caption_styles",
    title: "Unlock Premium Caption Styles",
    description:
      "Access all modern subtitle presets and word-level highlighting designed to maximize engagement.",
    cta: "Upgrade to Creator ($15/mo)",
    targetPlan: "Creator",
    badgeText: "High-Engagement Styles",
    highlights: [
      "Access viral styles (Beast, Hormozi, Neon, Luxury, Cinema)",
      "Dynamic word highlighting & animated pop-ins",
      "No watermarks on final exports",
    ],
  },
  processing_limit: {
    id: "processing_limit",
    title: "You've Used All Your AI Minutes",
    description:
      "Upgrade to Creator to get 300 monthly minutes (2x Opus Clip Starter) and continue creating viral clips.",
    cta: "Upgrade to Creator ($15/mo)",
    targetPlan: "Creator",
    badgeText: "Monthly AI Quota",
    highlights: [
      "300 AI video processing minutes per month",
      "No watermarks and 1080p Full HD export",
      "Instant top-up credits available anytime",
    ],
  },
  faster_queue: {
    id: "faster_queue",
    title: "Need Faster Processing?",
    description:
      "Creator plan gets fast priority processing, so your clips are ready in seconds.",
    cta: "Upgrade to Creator ($15/mo)",
    targetPlan: "Creator",
    badgeText: "Priority Speed",
    highlights: [
      "Bypass the standard processing queue",
      "Fast rendering for time-sensitive content",
      "Dedicated high-speed cloud GPU processing",
    ],
  },
  storage_limit: {
    id: "storage_limit",
    title: "Keep Your Videos Forever",
    description:
      "Free videos are automatically deleted after 3 days. Upgrade to keep your projects permanently.",
    cta: "Upgrade to Creator ($15/mo)",
    targetPlan: "Creator",
    badgeText: "Permanent Storage",
    highlights: [
      "Unlimited permanent project storage",
      "Re-edit captions & styling anytime",
      "Download raw source renders whenever needed",
    ],
  },
  ai_reframing: {
    id: "ai_reframing",
    title: "Advanced AI Reframing",
    description:
      "Automatically track speakers and center key action for perfect 9:16 vertical shorts.",
    cta: "Upgrade to Creator ($15/mo)",
    targetPlan: "Creator",
    badgeText: "Smart AI Tracking",
    highlights: [
      "Multi-speaker active camera tracking",
      "Auto-cropping tailored for TikTok & Reels",
      "1080p Full HD export with zero watermark",
    ],
  },
}

/**
 * Check session storage to prevent repeated prompts after dismissal during the same session.
 */
export function hasDismissedPrompt(triggerId: string): boolean {
  if (typeof window === "undefined") return false
  try {
    return sessionStorage.getItem(`upgrade_dismissed_${triggerId}`) === "true"
  } catch {
    return false
  }
}

/**
 * Record prompt dismissal in session storage.
 */
export function dismissPrompt(triggerId: string): void {
  if (typeof window === "undefined") return
  try {
    sessionStorage.setItem(`upgrade_dismissed_${triggerId}`, "true")
  } catch {
    // Ignore storage quota or disabled errors
  }
}

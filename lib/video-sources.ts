/**
 * Multi-platform video source detection, normalization, and types.
 * Supports Tier 1 (YouTube, Google Drive, Direct Upload) and Tier 2 (Vimeo, Loom, Twitch).
 * Client-safe module without Node-only dependencies.
 */

import { normalizeVideoUrl } from "./youtube"

export type SupportedPlatform =
  | "youtube"
  | "google_drive"
  | "vimeo"
  | "loom"
  | "twitch"
  | "direct"
  | "unsupported"

export type UniversalVideoMetadata = {
  videoId: string
  title: string
  /** Total video duration in seconds (0 or estimate if not immediately available). */
  duration: number
  thumbnail: string
  author: string | null
  platform: SupportedPlatform
}

export const PLATFORM_INFO: Record<
  SupportedPlatform,
  {
    name: string
    badgeColor: string
    hint?: string
  }
> = {
  youtube: {
    name: "YouTube",
    badgeColor: "bg-red-500/10 text-red-600 border-red-500/20",
  },
  google_drive: {
    name: "Google Drive",
    badgeColor: "bg-amber-500/10 text-amber-600 border-amber-500/20",
    hint: "Make sure link is set to 'Anyone with the link can view'",
  },
  vimeo: {
    name: "Vimeo",
    badgeColor: "bg-sky-500/10 text-sky-600 border-sky-500/20",
  },
  loom: {
    name: "Loom",
    badgeColor: "bg-indigo-500/10 text-indigo-600 border-indigo-500/20",
    hint: "Public or 'Anyone with link' Loom recordings supported",
  },
  twitch: {
    name: "Twitch",
    badgeColor: "bg-purple-500/10 text-purple-600 border-purple-500/20",
    hint: "Clips and VODs supported (up to 2 hours)",
  },
  direct: {
    name: "Direct Video",
    badgeColor: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20",
  },
  unsupported: {
    name: "Unsupported",
    badgeColor: "bg-neutral-500/10 text-neutral-600 border-neutral-500/20",
  },
}

/**
 * Detects the platform type of a given video URL.
 */
export function detectPlatform(url: string | null | undefined): SupportedPlatform {
  if (!url || typeof url !== "string") return "unsupported"
  const normalized = normalizeVideoUrl(url).toLowerCase()
  if (!normalized) return "unsupported"

  if (normalized.includes("youtube.com") || normalized.includes("youtu.be")) {
    return "youtube"
  }
  if (normalized.includes("drive.google.com")) {
    return "google_drive"
  }
  if (normalized.includes("vimeo.com")) {
    return "vimeo"
  }
  if (normalized.includes("loom.com")) {
    return "loom"
  }
  if (normalized.includes("twitch.tv") || normalized.includes("clips.twitch.tv")) {
    return "twitch"
  }

  const cleanPath = normalized.split("?")[0].split("#")[0]
  if (/\.(mp4|webm|mov|mkv|m4v)(\?.*)?$/i.test(cleanPath)) {
    return "direct"
  }
  if (
    normalized.includes("r2.cloudflarestorage.com") ||
    normalized.includes("s3.amazonaws.com")
  ) {
    return "direct"
  }

  return "unsupported"
}

export function isSupportedVideoUrl(url: string): boolean {
  return detectPlatform(url) !== "unsupported"
}

/**
 * Extracts a Google Drive file ID from standard share links.
 */
export function extractGoogleDriveFileId(url: string): string | null {
  const match =
    url.match(/\/file\/d\/([a-zA-Z0-9_-]+)/) ||
    url.match(/[?&]id=([a-zA-Z0-9_-]+)/)
  return match ? match[1] : null
}

/**
 * Normalizes Google Drive link to canonical view shape.
 */
export function sanitizeGoogleDriveUrl(url: string): string {
  const fileId = extractGoogleDriveFileId(url)
  if (fileId) {
    return `https://drive.google.com/file/d/${fileId}/view`
  }
  return url
}

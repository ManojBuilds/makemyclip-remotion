import { execFile } from "child_process"
import { promisify } from "util"
import { fetchYouTubeMetadata, normalizeVideoUrl } from "./youtube"
import {
  detectPlatform,
  extractGoogleDriveFileId,
  UniversalVideoMetadata,
} from "./video-sources"

const execFileAsync = promisify(execFile)

/**
 * Fast metadata fetcher for Vimeo using public oEmbed.
 */
async function fetchVimeoMetadata(url: string): Promise<UniversalVideoMetadata> {
  const oembedUrl = `https://vimeo.com/api/oembed.json?url=${encodeURIComponent(url)}`
  const res = await fetch(oembedUrl, { next: { revalidate: 3600 } })
  if (!res.ok) {
    throw new Error(
      "Failed to fetch Vimeo video details. The video may be private, password-protected, or deleted."
    )
  }
  const data = await res.json()
  return {
    videoId: String(data.video_id || "vimeo_video"),
    title: String(data.title || "Vimeo Video").trim(),
    duration: typeof data.duration === "number" ? data.duration : 120,
    thumbnail: data.thumbnail_url || "",
    author: data.author_name || null,
    platform: "vimeo",
  }
}

/**
 * Fast metadata fetcher for Loom using public oEmbed.
 */
async function fetchLoomMetadata(url: string): Promise<UniversalVideoMetadata> {
  const oembedUrl = `https://www.loom.com/v1/oembed?url=${encodeURIComponent(url)}`
  const res = await fetch(oembedUrl, { next: { revalidate: 3600 } })
  if (!res.ok) {
    throw new Error(
      "Failed to fetch Loom recording. Make sure the video privacy is set to 'Anyone with the link can view'."
    )
  }
  const data = await res.json()
  const match = url.match(/\/share\/([a-zA-Z0-9_-]+)/)
  const videoId = match ? match[1] : "loom_video"

  return {
    videoId,
    title: String(data.title || "Loom Recording").trim(),
    duration: typeof data.duration === "number" && data.duration > 0 ? data.duration : 180,
    thumbnail: data.thumbnail_url || "",
    author: data.author_name || null,
    platform: "loom",
  }
}

/**
 * Fast metadata fetcher for Twitch (clips and VODs) using oEmbed.
 */
async function fetchTwitchMetadata(url: string): Promise<UniversalVideoMetadata> {
  const oembedUrl = `https://www.twitch.tv/p/oembed?url=${encodeURIComponent(url)}`
  try {
    const res = await fetch(oembedUrl, { next: { revalidate: 3600 } })
    if (res.ok) {
      const data = await res.json()
      const isClip = url.includes("clip")
      return {
        videoId: `twitch_${Date.now()}`,
        title: String(data.title || "Twitch Video").trim(),
        duration: isClip ? 60 : 300,
        thumbnail: data.thumbnail_url || "",
        author: data.author_name || null,
        platform: "twitch",
      }
    }
  } catch {
    // fallback below
  }

  const isClip = url.includes("clip")
  return {
    videoId: `twitch_${Date.now()}`,
    title: isClip ? "Twitch Clip" : "Twitch VOD",
    duration: isClip ? 60 : 300,
    thumbnail: "",
    author: null,
    platform: "twitch",
  }
}

/**
 * Fast metadata fetcher for Google Drive via public OpenGraph tags.
 */
async function fetchGoogleDriveMetadata(url: string): Promise<UniversalVideoMetadata> {
  const fileId = extractGoogleDriveFileId(url)
  if (!fileId) {
    throw new Error("Invalid Google Drive file link. Please provide a link to a specific file.")
  }

  const canonicalUrl = `https://drive.google.com/file/d/${fileId}/view`
  let title = "Google Drive Video"
  let thumbnail = ""

  try {
    const res = await fetch(canonicalUrl, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      },
      next: { revalidate: 3600 },
    })

    if (res.ok) {
      const html = await res.text()
      const titleMatch = html.match(/<meta\s+property=["']og:title["']\s+content=["'](.*?)["']/i)
      if (titleMatch && titleMatch[1]) {
        title = titleMatch[1].replace(/ - Google Drive$/i, "").trim()
      }
      const thumbMatch = html.match(/<meta\s+property=["']og:image["']\s+content=["'](.*?)["']/i)
      if (thumbMatch && thumbMatch[1]) {
        thumbnail = thumbMatch[1]
      }
    }
  } catch {
    // Keep fallback title
  }

  return {
    videoId: fileId,
    title,
    duration: 300,
    thumbnail,
    author: null,
    platform: "google_drive",
  }
}

/**
 * Metadata fetcher for direct media files using ffprobe to get exact duration.
 */
async function fetchDirectMediaMetadata(url: string): Promise<UniversalVideoMetadata> {
  const cleanPath = url.split("?")[0].split("#")[0]
  const filename = cleanPath.split("/").pop() || "Direct Video"
  let duration = 0

  try {
    const { stdout } = await execFileAsync(
      "ffprobe",
      [
        "-v",
        "error",
        "-user_agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "-rw_timeout",
        "15000000",
        "-analyzeduration",
        "5000000",
        "-probesize",
        "5000000",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        url,
      ],
      { timeout: 15000 }
    )
    const lines = stdout.trim().split("\n")
    for (const line of lines) {
      const parsed = parseFloat(line.trim())
      if (!isNaN(parsed) && parsed > 0) {
        duration = Math.round(parsed)
        break
      }
    }
  } catch (err) {
    const errorMsg = err instanceof Error ? err.message : String(err)
    console.warn(`ffprobe direct video duration probe failed for ${url}: ${errorMsg}`)
  }

  return {
    videoId: `media_${Date.now()}`,
    title: decodeURIComponent(filename),
    duration: duration > 0 ? duration : 60,
    thumbnail: "",
    author: null,
    platform: "direct",
  }
}

/**
 * Universal metadata resolver for all Tier 1 & Tier 2 platforms (server-only).
 */
export async function fetchUniversalVideoMetadata(
  url: string
): Promise<UniversalVideoMetadata> {
  const normalized = normalizeVideoUrl(url)
  const platform = detectPlatform(normalized)

  switch (platform) {
    case "youtube": {
      const yt = await fetchYouTubeMetadata(normalized)
      return {
        videoId: yt.videoId,
        title: yt.title,
        duration: yt.duration,
        thumbnail: yt.thumbnail,
        author: yt.author,
        platform: "youtube",
      }
    }
    case "vimeo":
      return await fetchVimeoMetadata(normalized)
    case "loom":
      return await fetchLoomMetadata(normalized)
    case "twitch":
      return await fetchTwitchMetadata(normalized)
    case "google_drive":
      return await fetchGoogleDriveMetadata(normalized)
    case "direct":
      return await fetchDirectMediaMetadata(normalized)
    default:
      throw new Error(
        "Unsupported video URL. We support YouTube, Google Drive, Vimeo, Loom, Twitch, and direct video links."
      )
  }
}

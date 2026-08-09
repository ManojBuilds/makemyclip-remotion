/**
 * Lightweight YouTube helpers.
 *
 * No API key required: we extract the video ID from common URL shapes,
 * then scrape `lengthSeconds` and `title` from the public watch page's
 * `ytInitialPlayerResponse` JSON. oEmbed is used as a title fallback.
 */

/**
 * Returns true if the value parses as an http(s) URL.
 */
export function isHttpUrl(value: string): boolean {
  try {
    const u = new URL(value)
    return u.protocol === "http:" || u.protocol === "https:"
  } catch {
    return false
  }
}

export type YouTubeMetadata = {
  videoId: string
  title: string
  /** Total video duration in seconds. */
  duration: number
  thumbnail: string
  author: string | null
}

/**
 * Returns the 11-character video ID from any of the common YouTube URL shapes,
 * or `null` if the input isn't a recognizable YouTube URL.
 *
 * Supported:
 *   - https://www.youtube.com/watch?v=ID
 *   - https://youtu.be/ID
 *   - https://www.youtube.com/shorts/ID
 *   - https://www.youtube.com/embed/ID
 *   - https://www.youtube.com/live/ID
 *   - https://m.youtube.com / music.youtube.com variants
 */
export function extractYouTubeVideoId(url: string): string | null {
  let parsed: URL
  try {
    let urlString = url.trim()
    if (!/^https?:\/\//i.test(urlString)) {
      urlString = "https://" + urlString
    }
    parsed = new URL(urlString)
  } catch {
    return null
  }

  const host = parsed.hostname.replace(/^www\./, "").toLowerCase()

  if (host === "youtu.be") {
    const id = parsed.pathname.slice(1).split("/")[0]
    return isValidVideoId(id) ? id : null
  }

  if (
    host === "youtube.com" ||
    host === "m.youtube.com" ||
    host === "music.youtube.com" ||
    host === "youtube-nocookie.com"
  ) {
    if (parsed.pathname === "/watch") {
      const id = parsed.searchParams.get("v")
      return id && isValidVideoId(id) ? id : null
    }
    const m = parsed.pathname.match(/^\/(?:shorts|embed|live|v)\/([^/?#]+)/)
    if (m && isValidVideoId(m[1])) return m[1]
  }

  return null
}

function isValidVideoId(id: string | undefined | null): id is string {
  return !!id && /^[a-zA-Z0-9_-]{11}$/.test(id)
}

/**
 * Decode a JSON-encoded string fragment (handles \", \\, \uXXXX, \n, etc.)
 * by routing it through `JSON.parse`.
 */
function decodeJsonString(raw: string): string {
  try {
    return JSON.parse(`"${raw}"`)
  } catch {
    return raw
  }
}

/**
 * Parse an ISO 8601 duration string (e.g. "PT1H2M30S", "PT4M13S", "PT45S")
 * into total seconds. YouTube Data API v3 returns durations in this format.
 */
function parseISO8601Duration(iso: string): number {
  const match = iso.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/)
  if (!match) return 0
  const hours = parseInt(match[1] || "0", 10)
  const minutes = parseInt(match[2] || "0", 10)
  const seconds = parseInt(match[3] || "0", 10)
  return hours * 3600 + minutes * 60 + seconds
}

import { unstable_cache } from "next/cache"

const YOUTUBE_METADATA_CACHE_TTL_SECONDS = 60 * 60 * 24
const inFlightMetadataRequests = new Map<string, Promise<YouTubeMetadata>>()

/**
 * Fetch title + duration for a YouTube video. Throws if the URL is invalid
 * or the video is private/age-restricted/unavailable.
 *
 * Internal direct fetching method.
 */
async function fetchYouTubeMetadataDirect(
  url: string
): Promise<YouTubeMetadata> {
  const videoId = extractYouTubeVideoId(url)
  if (!videoId) {
    throw new Error("That doesn't look like a valid YouTube URL.")
  }

  let apiErrorDetails: string | null = null

  // 1. Try YouTube Data API v3 (most reliable for production)
  const ytApiKey = process.env.YOUTUBE_DATA_API_KEY
  if (ytApiKey) {
    try {
      const apiUrl = `https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails&id=${videoId}&key=${ytApiKey}`
      console.log(`[fetchYouTubeMetadata] Requesting from YouTube Data API v3`)
      const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000"
      const apiRes = await fetch(apiUrl, {
        cache: "no-store",
        headers: {
          Referer: appUrl,
        },
      })

      if (apiRes.ok) {
        const data = await apiRes.json()
        const item = data.items?.[0]
        if (item) {
          const duration = parseISO8601Duration(item.contentDetails.duration)
          if (duration > 0) {
            console.log(
              `[fetchYouTubeMetadata] YouTube Data API returned: title="${item.snippet.title}", duration=${duration}s`
            )
            console.log({
              videoId,
              title: item.snippet.title || "YouTube Video",
              duration,
              thumbnail: `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`,
              author: item.snippet.channelTitle || null,
            })
            return {
              videoId,
              title: item.snippet.title || "YouTube Video",
              duration,
              thumbnail: `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`,
              author: item.snippet.channelTitle || null,
            }
          }
        } else {
          console.warn(
            `[fetchYouTubeMetadata] YouTube Data API returned no items — video may be private or deleted`
          )
          apiErrorDetails = "API returned no items (video may be private, deleted, or region-restricted)"
        }
      } else {
        const errBody = await apiRes.text()
        console.warn(
          `[fetchYouTubeMetadata] YouTube Data API returned status ${apiRes.status}: ${errBody}`
        )
        apiErrorDetails = `API returned status ${apiRes.status}: ${errBody}`
      }
    } catch (apiErr) {
      console.error(`[fetchYouTubeMetadata] YouTube Data API failed:`, apiErr)
      apiErrorDetails = `API request failed: ${apiErr instanceof Error ? apiErr.message : String(apiErr)}`
    }
  } else {
    apiErrorDetails = "YOUTUBE_DATA_API_KEY environment variable is not configured."
  }

  // 2. Try Modal yt-downloader-metadata endpoint as fallback
  const downloaderEndpoint = process.env.MODAL_YT_DOWNLOADER_ENDPOINT
  const metadataEndpoint =
    process.env.MODAL_YT_METADATA_ENDPOINT ||
    (downloaderEndpoint
      ? downloaderEndpoint.replace("-download.modal.run", "-metadata.modal.run")
      : null)

  if (metadataEndpoint) {
    try {
      console.log(
        `[fetchYouTubeMetadata] Falling back to Modal endpoint: ${metadataEndpoint}`
      )
      const modalRes = await fetch(metadataEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      })

      if (modalRes.ok) {
        const data = await modalRes.json()
        if (data.success && data.duration) {
          console.log(`[fetchYouTubeMetadata] Modal returned metadata:`, data)
          return {
            videoId,
            title: data.title || "YouTube Video",
            duration: Math.ceil(data.duration),
            thumbnail:
              data.thumbnail ||
              `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`,
            author: data.author || null,
          }
        } else {
          console.warn(
            `[fetchYouTubeMetadata] Modal endpoint returned unsuccessful:`,
            data.error
          )
        }
      } else {
        console.warn(
          `[fetchYouTubeMetadata] Modal endpoint returned status ${modalRes.status}`
        )
      }
    } catch (modalErr) {
      console.error(
        `[fetchYouTubeMetadata] Failed to fetch metadata from Modal:`,
        modalErr
      )
    }
  }

  // 3. Last resort — scrape the watch page HTML directly
  console.log(
    `[fetchYouTubeMetadata] Last resort: scraping watch page for ${url}`
  )
  const watchUrl = `https://www.youtube.com/watch?v=${videoId}`

  const res = await fetch(watchUrl, {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9",
    },
    cache: "no-store",
  })

  if (!res.ok) {
    throw new Error(`Failed to load YouTube video (status ${res.status}).`)
  }

  const html = await res.text()

  // `"lengthSeconds":"123"` lives inside `videoDetails` in ytInitialPlayerResponse.
  const lengthMatch = html.match(/"lengthSeconds":"(\d+)"/)
  if (!lengthMatch) {
    let errorMsg = "Couldn't read this video's duration. The video may be private, age-restricted, region-locked, or direct YouTube scraping is blocked by YouTube on your hosting provider."
    if (apiErrorDetails) {
      errorMsg += ` (YouTube API Key Error: ${apiErrorDetails})`
    }
    throw new Error(errorMsg)
  }
  const duration = parseInt(lengthMatch[1], 10)
  if (!Number.isFinite(duration) || duration <= 0) {
    throw new Error("This video has an invalid duration.")
  }

  // Pull title from the same videoDetails block; fall back to oEmbed if needed.
  const titleMatch = html.match(
    /"videoDetails"\s*:\s*\{[^}]*?"title"\s*:\s*"((?:\\.|[^"\\])*)"/
  )
  const authorMatch = html.match(
    /"videoDetails"\s*:\s*\{[^}]*?"author"\s*:\s*"((?:\\.|[^"\\])*)"/
  )

  let title = titleMatch ? decodeJsonString(titleMatch[1]) : ""
  if (!title) {
    try {
      const oembed = await fetch(
        `https://www.youtube.com/oembed?url=${encodeURIComponent(watchUrl)}&format=json`,
        { cache: "no-store" }
      )
      if (oembed.ok) {
        const data = (await oembed.json()) as { title?: string }
        if (data?.title) title = data.title
      }
    } catch {
      // ignore — fall through to default
    }
  }
  if (!title) title = "YouTube Video"

  return {
    videoId,
    title,
    duration,
    thumbnail: `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`,
    author: authorMatch ? decodeJsonString(authorMatch[1]) : null,
  }
}

/**
 * Cached helper that fetches YouTube metadata by video ID.
 */
const getCachedMetadataByVideoId = unstable_cache(
  async (videoId: string): Promise<YouTubeMetadata> => {
    const watchUrl = `https://www.youtube.com/watch?v=${videoId}`
    return fetchYouTubeMetadataDirect(watchUrl)
  },
  ["youtube-metadata-cache"],
  {
    revalidate: YOUTUBE_METADATA_CACHE_TTL_SECONDS,
    tags: ["youtube-metadata"],
  }
)

/**
 * Fetch title, duration, author, and thumbnail for a YouTube URL,
 * using Next.js caching to prevent redundant API/scraping requests.
 */
export async function fetchYouTubeMetadata(
  url: string
): Promise<YouTubeMetadata> {
  const videoId = extractYouTubeVideoId(url)
  if (!videoId) {
    throw new Error("That doesn't look like a valid YouTube URL.")
  }

  const existingRequest = inFlightMetadataRequests.get(videoId)
  if (existingRequest) {
    return existingRequest
  }

  const request = getCachedMetadataByVideoId(videoId).finally(() => {
    inFlightMetadataRequests.delete(videoId)
  })

  inFlightMetadataRequests.set(videoId, request)
  return request
}

# Video Source Compatibility & Multi-Platform Expansion Plan

This document details the video source compatibility for MakeMyClip (`modal/` backend and Next.js frontend), analyzing which platforms `yt-dlp` supports, which ones it does not, how the current codebase behaves, and an end-to-end engineering plan to add multi-platform support.

---

## 1. Executive Summary: Current Codebase vs. `yt-dlp`

| Capability | Current MakeMyClip Implementation | Native `yt-dlp` Capability |
| :--- | :--- | :--- |
| **YouTube** |  Fully supported with multi-client rotation |  Fully supported |
| **Vimeo** | ❌ Blocked (falls back to `requests.get` and crashes) |  Native extractor available |
| **Twitch** | ❌ Blocked (falls back to `requests.get` and crashes) |  Native extractor available |
| **Loom** | ❌ Blocked (falls back to `requests.get` and crashes) |  Native extractor available |
| **Google Drive** | ❌ Blocked (fails on Google Drive HTML viewer) |  Native extractor available for public shared files |
| **TikTok / Twitter / Instagram** | ❌ Blocked |  Native extractors available |
| **Direct MP4 / WebM URLs** |  Supported via HTTP streaming & FFmpeg |  Supported (generic extractor) |
| **DRM Services (Netflix, Disney+)** | ❌ Not supported | ❌ Impossible (DRM-protected) |

### Why Non-YouTube Sources Fail in MakeMyClip Today

Even though `yt-dlp` is installed in the Modal container:

1. **Modal is hard-gated to YouTube:** In [`modal/utils.py`](file:///home/manoj/Developer/makemyclip-remotion/modal/utils.py#L29-L33):
   ```python
   def is_youtube_url(url: str) -> bool:
       normalized = normalize_url(url)
       return "youtube.com" in normalized or "youtu.be" in normalized
   ```
2. **Pipelines bypass `yt-dlp` for non-YouTube links:**
   - In [`modal/transcriber.py`](file:///home/manoj/Developer/makemyclip-remotion/modal/transcriber.py#L310-L336), [`modal/reframer.py`](file:///home/manoj/Developer/makemyclip-remotion/modal/reframer.py#L1805-L1834), and [`modal/analyzer.py`](file:///home/manoj/Developer/makemyclip-remotion/modal/analyzer.py#L255-L295), any URL where `is_youtube_url()` is `False` is treated as a static file link and downloaded via `requests.get(vurl)` or FFmpeg.
   - For Vimeo, Twitch, Loom, or Google Drive, `requests.get()` downloads the HTML webpage rather than video data, causing an immediate crash or corrupted file error.
3. **Frontend & Next.js API are restricted to YouTube:**
   - [`components/video/unified-input.tsx`](file:///home/manoj/Developer/makemyclip-remotion/components/video/unified-input.tsx#L91-L97) validates with `isValidYoutubeUrl()`.
   - [`app/api/video/metadata/route.ts`](file:///home/manoj/Developer/makemyclip-remotion/app/api/video/metadata/route.ts) and [`app/api/projects/create-from-url/route.ts`](file:///home/manoj/Developer/makemyclip-remotion/app/api/projects/create-from-url/route.ts) call `fetchYouTubeMetadata()`.

---

## 2. Source Breakdown: Supported vs. Not Supported by `yt-dlp`

### A. Sources That `yt-dlp` HAS Native Support For

| Source | URL Examples | `yt-dlp` Extractor | Practical Considerations & Caveats |
| :--- | :--- | :--- | :--- |
| **YouTube** | `youtube.com/watch?v=...`<br>`youtu.be/...`<br>`youtube.com/shorts/...` | `youtube.py` | Requires client rotation (`tv`, `web_safari`, `mweb`) and cookies to bypass bot detection. |
| **Vimeo** | `vimeo.com/123456789`<br>`player.vimeo.com/video/...` | `vimeo.py` | Works reliably for public and unlisted videos. Password-protected videos require the `--video-password` flag. Videos restricted by domain referer require `--referer`. |
| **Twitch** | `twitch.tv/videos/123456789`<br>`clips.twitch.tv/...` | `twitch.py` | Works for VODs, highlights, and clips. Subscriber-only VODs require an OAuth token or cookies. |
| **Loom** | `loom.com/share/...` | `loom.py` | Works smoothly for all public and "Anyone with link" Loom videos. Private workspace-only videos fail without session cookies. |
| **Google Drive** | `drive.google.com/file/d/<id>/view` | `googledrive.py` | Must be set to **"Anyone with the link can view"**. `yt-dlp` automatically handles Google Drive's large-file download virus-scan confirmation token. |
| **TikTok** | `tiktok.com/@user/video/...` | `tiktok.py` | Works for public videos. May encounter occasional CAPTCHA or CDN rate limits from data-center IPs. |
| **Twitter / X** | `x.com/user/status/...`<br>`twitter.com/user/status/...` | `twitter.py` | Works well for public tweets containing video attachments. |
| **Instagram** | `instagram.com/reel/...`<br>`instagram.com/p/...` | `instagram.py` | Works for public reels, but Meta aggressively blocks data-center IPs; often requires cookies for stability. |
| **Facebook** | `facebook.com/watch/?v=...`<br>`facebook.com/reel/...` | `facebook.py` | Works for public videos and reels. |
| **Reddit** | `reddit.com/r/.../comments/...`<br>`v.redd.it/...` | `reddit.py` | Separate audio and video DASH streams are automatically merged by `yt-dlp` using FFmpeg. |
| **Dropbox** | `dropbox.com/s/...`<br>`dropbox.com/scl/fi/...` | `dropbox.py` | Shared links work reliably. |
| **Streamable** | `streamable.com/...` | `streamable.py` | Fast and reliable. |
| **Dailymotion** | `dailymotion.com/video/...` | `dailymotion.py` | Works reliably. |
| **Direct Media / Streams** | `*.mp4`, `*.webm`, `*.m3u8`, `*.mpd` | `generic.py` | `yt-dlp` can download raw files, HLS streams, and DASH manifests. |

---

### B. Sources That `yt-dlp` DOES NOT Support (Or Cannot Practically Download)

| Source | Why It Does NOT Work | Workaround / Alternative |
| :--- | :--- | :--- |
| **Netflix, Disney+, Prime Video, Apple TV+, Hulu** | **DRM Encryption (Widevine / PlayReady):** `yt-dlp` does not decrypt DRM-protected commercial media streams by design and policy. | Users must capture screen or upload pre-recorded local files. |
| **Spotify Video Podcasts** | Video streams use Widevine DRM encryption. | Not extractable. |
| **Private Google Drive Links** | "Restricted" Google Drive links that require signing into a specific Google account. | User must change sharing to "Anyone with the link can view" or use Google Drive OAuth picker to download using user token. |
| **Private Loom Links** | Loom recordings restricted to "Only people in your workspace". | User must toggle link sharing to "Anyone with link" or upload the exported `.mp4`. |
| **Private Zoom Cloud Recordings** | Recordings protected by meeting passcodes or enterprise SSO authentication. | User must download recording from Zoom and upload `.mp4` directly. |
| **Canva Project Links** | Unrendered Canva design canvas links (`canva.com/design/...`) are dynamic web apps, not media streams. | User must render/export the video in Canva first. |
| **Cloud Storage Folders** | Linking to an entire Google Drive folder (`/drive/folders/...`) or Dropbox folder downloads a playlist/batch, which conflicts with single-video processing pipelines. | Users must link to a specific file or single asset. |
| **Figma / Frame.io Workspace Links** | Require team authentication or API tokens. | User must export and upload `.mp4` or provide pre-signed asset download URLs. |

---

## 3. End-to-End Implementation Plan for Multi-Source Support

Adding multi-source support requires changes across three layers:
1. **Modal Backend (`modal/`)**
2. **Next.js Metadata & Project Creation API (`lib/` & `app/api/`)**
3. **Frontend Input UX (`components/video/unified-input.tsx`)**

```mermaid
flowchart TD
    UI[Unified Input Box] -->|Validate URL| API[Next.js API: /api/video/metadata]
    API -->|Probe Info| ModalMeta[Modal: get_media_info]
    ModalMeta -->|yt-dlp / ffprobe| MetaRes[Return Duration, Title, Thumbnail]
    MetaRes --> UI
    UI -->|Create Project| CreateProj[/api/projects/create-from-url]
    CreateProj --> Inngest[Inngest Pipeline]
    Inngest --> Transcriber[Modal Transcriber]
    Inngest --> Analyzer[Modal Analyzer]
    Inngest --> Reframer[Modal Reframer]
    Transcriber --> YTHelper[modal/ytdlp_helper.py]
    Analyzer --> YTHelper
    Reframer --> YTHelper
    YTHelper -->|Auto-detect source| Download[yt-dlp Universal Downloader]
```

---

### Step 1: Generalize URL Detection & Helper in Modal

#### 1.1 Replace `is_youtube_url` with Generic Detector in [`modal/utils.py`](file:///home/manoj/Developer/makemyclip-remotion/modal/utils.py)
Replace hardcoded YouTube checks with a flexible extractor check:
```python
# modal/utils.py

YTDLP_SUPPORTED_DOMAINS = (
    "youtube.com", "youtu.be",
    "vimeo.com",
    "twitch.tv",
    "loom.com",
    "drive.google.com",
    "tiktok.com",
    "twitter.com", "x.com",
    "instagram.com",
    "facebook.com", "fb.watch",
    "reddit.com", "v.redd.it",
    "streamable.com",
    "dropbox.com",
)

def is_ytdlp_supported_url(url: str) -> bool:
    """Return True if url belongs to a platform supported by yt-dlp."""
    normalized = normalize_url(url).lower()
    return any(domain in normalized for domain in YTDLP_SUPPORTED_DOMAINS)
```

#### 1.2 Update [`modal/ytdlp_helper.py`](file:///home/manoj/Developer/makemyclip-remotion/modal/ytdlp_helper.py)
In `ytdlp_helper.py`:
- Keep YouTube client rotation (`tv`, `web_safari`, `mweb`) **only** when `is_youtube_url(vurl)` is true.
- For non-YouTube URLs (Vimeo, Twitch, Loom, Drive), execute a clean standard `yt-dlp` run without YouTube-specific `extractor_args`.
- Add Google Drive query parameter cleaning (e.g. converting `drive.google.com/file/d/<id>/view?usp=sharing` to standard format).
- Generalize `get_youtube_info(vurl)` to `get_media_info(vurl)` so it extracts title, duration, fps, width, and height from any platform.

#### 1.3 Update Modal Call Sites
In:
- [`modal/transcriber.py`](file:///home/manoj/Developer/makemyclip-remotion/modal/transcriber.py)
- [`modal/reframer.py`](file:///home/manoj/Developer/makemyclip-remotion/modal/reframer.py)
- [`modal/analyzer.py`](file:///home/manoj/Developer/makemyclip-remotion/modal/analyzer.py)

Change:
```python
# Before:
if is_youtube_url(vurl):
    ...
else:
    # Direct requests.get()

# After:
if is_ytdlp_supported_url(vurl):
    download_media_video(...)
elif vurl.startswith("http://") or vurl.startswith("https://"):
    # Raw direct media file (.mp4/.webm from S3/R2)
    requests.get(...)
```

---

### Step 2: Next.js API & Metadata Fetching

Currently, [`app/api/video/metadata/route.ts`](file:///home/manoj/Developer/makemyclip-remotion/app/api/video/metadata/route.ts) scrapes YouTube HTML directly via `lib/youtube.ts`. This works for YouTube, but does not scale to Vimeo, Loom, or Google Drive.

#### 2.1 Strategy for Non-YouTube Metadata
Two options exist:
1. **Option A (Recommended - Leverage Modal):** Create a fast lightweight Modal function `get_media_info` that runs `yt_dlp.YoutubeDL({'skip_download': True}).extract_info(url)`. This automatically handles metadata for all 1,000+ sites without maintaining individual scrapers.
2. **Option B (Serverless oEmbed):** Use standard oEmbed APIs for Vimeo, Loom, and YouTube:
   - Vimeo: `https://vimeo.com/api/oembed.json?url={url}`
   - Loom: `https://www.loom.com/v1/oembed?url={url}`
   - YouTube: `https://www.youtube.com/oembed?url={url}&format=json`

#### 2.2 Update [`app/api/projects/create-from-url/route.ts`](file:///home/manoj/Developer/makemyclip-remotion/app/api/projects/create-from-url/route.ts)
- Accept any URL that passes `isSupportedVideoUrl()`.
- Store the platform type (e.g. `youtube`, `vimeo`, `loom`, `drive`, `direct`) in the database project record for diagnostics.

---

### Step 3: Frontend Validation & UX

#### 3.1 Update [`components/video/unified-input.tsx`](file:///home/manoj/Developer/makemyclip-remotion/components/video/unified-input.tsx)
- Broaden the input validator:
  ```typescript
  export type VideoSourceType = "youtube" | "vimeo" | "loom" | "twitch" | "drive" | "direct" | "unknown"

  export function detectVideoSource(url: string): VideoSourceType {
    const u = url.toLowerCase()
    if (u.includes("youtube.com") || u.includes("youtu.be")) return "youtube"
    if (u.includes("vimeo.com")) return "vimeo"
    if (u.includes("loom.com")) return "loom"
    if (u.includes("twitch.tv")) return "twitch"
    if (u.includes("drive.google.com")) return "drive"
    if (/\.(mp4|webm|mov|mkv)(\?.*)?$/i.test(u)) return "direct"
    return "unknown"
  }
  ```
- **Platform Badges:** Display a small platform badge (YouTube, Vimeo, Loom, Google Drive) next to the input box when a valid link is pasted.
- **Friendly Warnings:**
  - If a user pastes a Google Drive link: *"Ensure sharing is set to 'Anyone with the link can view'"*.
  - If a user pastes a private/unsupported link (e.g., Netflix): *"Streaming services with DRM cannot be imported. Please upload a local file."*

---

### Step 4: Testing & Verification Matrix

| Target Platform | Test Case | Success Criteria |
| :--- | :--- | :--- |
| **YouTube** | Standard watch link, Shorts link | Retains existing fast multi-strategy download. |
| **Vimeo** | Standard public video (`vimeo.com/67019023`) | Metadata fetched, video downloaded at 720p/1080p. |
| **Twitch** | Public clip (`clips.twitch.tv/...`) | Audio and video downloaded and synced. |
| **Loom** | Public recording (`loom.com/share/...`) | Metadata fetched, 720p MP4 retrieved. |
| **Google Drive** | Public shared video (`drive.google.com/file/d/...`) | Large file confirmation token passed; MP4 downloaded. |
| **Direct MP4** | Direct URL to `.mp4` file on CDN / R2 | FFmpeg single-pass proxy download succeeds. |
| **Error Handling** | Private Drive link / 404 URL | Clean user-facing error message returned without infinite retries. |

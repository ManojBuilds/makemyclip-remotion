# YouTube Auto-Post — Implementation Plan

> **Status:** 📋 Planned (not started)
> **Priority:** Post-launch — build after core product has paying users
> **Estimated effort:** ~3–4 days of focused development
> **Decided on:** 2026-09-01

---

## Summary

Add the ability for **paid users** to publish rendered clips directly to YouTube Shorts from the clip detail page. Metadata (title, description, tags) is AI-generated via Gemini and editable before publishing. Supports scheduled publishing via YouTube's native `publishAt` API.

### Scope (MVP)

- ✅ YouTube Shorts only (single platform)
- ✅ Single clip at a time (from clip detail/preview page)
- ✅ AI-generated metadata with user edit
- ✅ Scheduled posting (pick a date/time)
- ✅ Paid plans only (creator + power)
- ❌ No batch posting (future enhancement)
- ❌ No Instagram / TikTok / X (future enhancement)
- ❌ No analytics dashboard (future enhancement)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Clip Detail Page                     │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  "Post to YouTube" button (paid users only)         │ │
│  └──────────────────────┬──────────────────────────────┘ │
│                         │                                │
│  ┌──────────────────────▼──────────────────────────────┐ │
│  │  YouTube Post Modal                                  │ │
│  │  - Connect YouTube account (if not connected)        │ │
│  │  - AI-generated title, description, tags             │ │
│  │  - Editable fields                                   │ │
│  │  - Date/time picker for scheduled publish            │ │
│  │  - "Publish" / "Schedule" button                     │ │
│  └──────────────────────┬──────────────────────────────┘ │
└─────────────────────────┼───────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   POST /api/youtube/  │
              │       publish         │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Inngest: youtube.    │
              │   upload.requested    │
              │                       │
              │  1. Fetch video from  │
              │     R2 (presigned)    │
              │  2. Resumable upload  │
              │     to YouTube API    │
              │  3. Set metadata +    │
              │     publishAt         │
              │  4. Update DB status  │
              └───────────────────────┘
```

---

## Phase 1: Google Cloud Setup (~2 hours)

### Prerequisites
- Existing GCP project ✅

### Steps

1. **Enable YouTube Data API v3** in GCP Console → APIs & Services
2. **Configure OAuth Consent Screen**
   - App name: MakeMyClip
   - Scopes needed: `https://www.googleapis.com/auth/youtube.upload`
   - User type: External
   - Add test users for development

> [!WARNING]
> **OAuth Verification Required for Production**
> Google requires app verification for apps with >100 users. This process takes **2–6 weeks** and requires:
> - A privacy policy URL (you have `/privacy`)
> - A terms of service URL (you have `/terms`)
> - A demo video showing how the OAuth scope is used
> - A written explanation of why you need `youtube.upload` scope
>
> **Start the verification process early** — even before you start coding.

3. **Create OAuth 2.0 Client ID**
   - Type: Web application
   - Authorized redirect URI: `https://makemyclip.com/api/youtube/callback`
   - Save `client_id` and `client_secret` to `.env`

4. **Request Quota Increase**
   - Default quota: 10,000 units/day
   - Each video upload costs ~1,600 units = ~6 uploads/day for ALL users
   - Request increase to 100,000+ units via GCP Console quota page

### New Environment Variables

```env
# YouTube OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
YOUTUBE_REDIRECT_URI=https://makemyclip.com/api/youtube/callback
```

---

## Phase 2: Database Schema (~1–2 hours)

### New Tables

Add to [`lib/db/schema.ts`](file:///home/manoj/Developer/makemyclip-remotion/lib/db/schema.ts):

```typescript
// ─────────────────────────────────────────────
// YouTube Connected Accounts
// ─────────────────────────────────────────────

export const youtubeAccounts = pgTable("youtube_accounts", {
  id: text("id")
    .primaryKey()
    .$defaultFn(() => createId()),
  userId: text("user_id")
    .notNull()
    .references(() => user.id, { onDelete: "cascade" }),
  channelId: text("channel_id").notNull(),        // YouTube channel ID
  channelTitle: text("channel_title"),              // Display name
  channelThumbnail: text("channel_thumbnail"),      // Avatar URL
  accessToken: text("access_token").notNull(),      // Encrypted
  refreshToken: text("refresh_token").notNull(),    // Encrypted
  tokenExpiresAt: timestamp("token_expires_at"),
  createdAt: timestamp("created_at").notNull().defaultNow(),
  updatedAt: timestamp("updated_at").notNull().defaultNow(),
})

// ─────────────────────────────────────────────
// YouTube Post History
// ─────────────────────────────────────────────

export const youtubePosts = pgTable("youtube_posts", {
  id: text("id")
    .primaryKey()
    .$defaultFn(() => createId()),
  clipId: text("clip_id")
    .notNull()
    .references(() => clips.id, { onDelete: "cascade" }),
  youtubeAccountId: text("youtube_account_id")
    .notNull()
    .references(() => youtubeAccounts.id, { onDelete: "cascade" }),
  youtubeVideoId: text("youtube_video_id"),         // Returned after upload
  title: text("title").notNull(),
  description: text("description"),
  tags: jsonb("tags").$type<string[]>(),
  privacyStatus: text("privacy_status", {
    enum: ["public", "unlisted", "private"],
  }).notNull().default("public"),
  scheduledAt: timestamp("scheduled_at"),            // null = publish immediately
  status: text("status", {
    enum: ["pending", "uploading", "published", "scheduled", "failed"],
  }).notNull().default("pending"),
  errorMessage: text("error_message"),
  publishedAt: timestamp("published_at"),
  createdAt: timestamp("created_at").notNull().defaultNow(),
})
```

### Migration

```bash
npx drizzle-kit push
```

---

## Phase 3: YouTube OAuth Flow (~4–5 hours)

### New Files

#### `lib/youtube-oauth.ts` — OAuth helper utilities

```
Functions:
├── getAuthUrl()           → Generate Google OAuth URL with youtube.upload scope
├── exchangeCode(code)     → Exchange auth code for access + refresh tokens
├── refreshAccessToken()   → Refresh expired tokens using refresh_token
├── getChannelInfo(token)  → Fetch channel name/avatar from YouTube API
└── revokeToken(token)     → Disconnect account
```

#### `app/api/youtube/connect/route.ts` — Initiate OAuth

- Check user is authenticated (Clerk)
- Check user is on paid plan
- Generate OAuth URL with `state` = encrypted user ID
- Redirect to Google consent screen

#### `app/api/youtube/callback/route.ts` — OAuth callback

- Validate `state` parameter
- Exchange `code` for tokens
- Fetch channel info from YouTube
- Store in `youtubeAccounts` table (encrypt tokens at rest)
- Redirect back to dashboard/settings with success toast

#### `app/api/youtube/disconnect/route.ts` — Disconnect account

- Revoke token with Google
- Delete from `youtubeAccounts`
- Return success

### Token Encryption

> [!IMPORTANT]
> **Never store OAuth tokens in plaintext.** Use AES-256-GCM encryption with a key stored in env vars.

```env
YOUTUBE_TOKEN_ENCRYPTION_KEY=  # 32-byte hex key
```

Create `lib/encryption.ts`:
```typescript
// encrypt(plaintext: string): string  — returns base64 ciphertext
// decrypt(ciphertext: string): string — returns original plaintext
```

---

## Phase 4: YouTube Upload via Inngest (~3–4 hours)

### New Inngest Function

Add to [`lib/inngest/functions.ts`](file:///home/manoj/Developer/makemyclip-remotion/lib/inngest/functions.ts):

```typescript
export const uploadToYouTube = inngest.createFunction(
  {
    id: "upload-to-youtube",
    triggers: [{ event: "youtube.upload.requested" }],
    retries: 2,
  },
  async ({ event, step }) => {
    const { postId, clipId, youtubeAccountId } = event.data

    // Step 1: Fetch clip + account data from DB
    // Step 2: Refresh YouTube access token if expired
    // Step 3: Download rendered video from R2 (presigned URL)
    // Step 4: Resumable upload to YouTube Data API v3
    //         - POST https://www.googleapis.com/upload/youtube/v3/videos
    //         - Set snippet (title, desc, tags, categoryId=22 for People & Blogs)
    //         - Set status.privacyStatus + status.publishAt for scheduling
    //         - Use #Shorts in title/description to classify as Short
    // Step 5: Update youtubePosts with youtubeVideoId + status
    // Step 6: Track analytics event via PostHog
  }
)
```

### YouTube Data API v3 — Upload Reference

```
POST https://www.googleapis.com/upload/youtube/v3/videos
  ?uploadType=resumable
  &part=snippet,status

Headers:
  Authorization: Bearer {access_token}
  Content-Type: application/json

Body:
{
  "snippet": {
    "title": "Your AI-generated title #Shorts",
    "description": "Generated description with hashtags",
    "tags": ["shorts", "clips", "podcast"],
    "categoryId": "22"
  },
  "status": {
    "privacyStatus": "private",          // "private" when scheduling
    "publishAt": "2026-09-15T10:00:00Z", // ISO 8601 — YouTube auto-publishes
    "selfDeclaredMadeForKids": false
  }
}
```

> [!NOTE]
> **Scheduling trick:** Upload as `privacyStatus: "private"` with a `publishAt` timestamp. YouTube automatically makes it public at the scheduled time. No need to build your own scheduler.

### New API Route

#### `app/api/youtube/publish/route.ts`

- Validate user is on paid plan
- Validate clip exists and is rendered
- Validate YouTube account is connected
- Create `youtubePosts` record with status `"pending"`
- Fire Inngest event `youtube.upload.requested`
- Return post ID for frontend polling

---

## Phase 5: Gemini Metadata Generation (~2–3 hours)

### New Function in `lib/gemini.ts`

Add to [`lib/gemini.ts`](file:///home/manoj/Developer/makemyclip-remotion/lib/gemini.ts):

```typescript
export async function generateYouTubeMetadata(params: {
  clipTitle: string
  clipDescription: string
  transcript: string
  hookText: string
  clipType: string
  hashtags: string
}): Promise<{
  title: string       // Max 100 chars, includes #Shorts
  description: string // Max 5000 chars, with hashtags
  tags: string[]      // Max 500 chars total, relevant keywords
}>
```

### Prompt Strategy

```
You are a YouTube Shorts SEO expert. Generate metadata for a short-form video clip.

Context:
- Clip title: {clipTitle}
- Hook: {hookText}
- Type: {clipType}
- Transcript excerpt: {transcript (first 500 chars)}

Generate:
1. TITLE: Catchy, SEO-friendly, max 100 chars. Must end with #Shorts
2. DESCRIPTION: Engaging, 2-3 sentences + relevant hashtags. Max 5000 chars.
3. TAGS: 5-10 relevant keywords as an array.

Rules:
- Use power words that drive clicks (revealed, secret, truth, etc.)
- Include relevant hashtags in description
- Tags should include both broad and niche keywords
- Don't use clickbait that misrepresents the content
```

---

## Phase 6: Frontend UI (~4–5 hours)

### Components to Build

#### 1. YouTube Account Connection (Settings Page)

Location: [`app/(dashboard)/settings/`](file:///home/manoj/Developer/makemyclip-remotion/app/(dashboard)/settings)

- "Connected Accounts" section
- "Connect YouTube" button → initiates OAuth flow
- Show connected channel name + avatar once connected
- "Disconnect" button with confirmation dialog

#### 2. "Post to YouTube" Button (Clip Detail Page)

Location: Clip preview/detail page (wherever the download button is)

- Show only for paid users with rendered clips
- Disabled state with tooltip for free users: "Upgrade to post directly"
- If no YouTube account connected → prompt to connect first

#### 3. YouTube Post Modal

```
┌──────────────────────────────────────────┐
│  Post to YouTube                    [×]  │
├──────────────────────────────────────────┤
│                                          │
│  Channel: ▸ @ChannelName  [Connected ✓]  │
│                                          │
│  Title ✨ (AI-generated)                 │
│  ┌──────────────────────────────────────┐│
│  │ The Truth About Starting a Busine.. ││
│  └──────────────────────────────────────┘│
│                                          │
│  Description ✨                          │
│  ┌──────────────────────────────────────┐│
│  │ In this clip, we reveal the number  ││
│  │ one mistake entrepreneurs make...   ││
│  │ #entrepreneur #business #shorts     ││
│  └──────────────────────────────────────┘│
│                                          │
│  Tags ✨                                 │
│  ┌──────────────────────────────────────┐│
│  │ business, entrepreneur, startup,... ││
│  └──────────────────────────────────────┘│
│                                          │
│  Visibility                              │
│  ○ Public  ○ Unlisted  ○ Private         │
│                                          │
│  ☐ Schedule for later                    │
│    📅 Sept 15, 2026   🕐 10:00 AM       │
│                                          │
│  ┌──────────────────────────────────────┐│
│  │   🚀 Publish to YouTube             ││
│  └──────────────────────────────────────┘│
│                                          │
│  ✨ = AI-generated, click to edit        │
└──────────────────────────────────────────┘
```

#### 4. Post Status Indicator

After posting, show status on the clip card:
- 🔄 Uploading...
- ✅ Published — [View on YouTube →]
- 📅 Scheduled for Sept 15 — [View on YouTube →]
- ❌ Failed — [Retry]

---

## Phase 7: Plan Gating (~1 hour)

### Config Update

Add to [`lib/config.ts`](file:///home/manoj/Developer/makemyclip-remotion/lib/config.ts) `PLAN_LIMITS`:

```typescript
free: {
  // ...existing
  youtubePosting: false,
},
creator: {
  // ...existing
  youtubePosting: true,
  monthlyYouTubePosts: 30,
},
power: {
  // ...existing
  youtubePosting: true,
  monthlyYouTubePosts: -1, // unlimited
},
```

### Feature Lists Update

Add to creator features: `"Auto-post to YouTube Shorts"`
Add to power features: `"Unlimited YouTube auto-posting"`

---

## File Summary — All New & Modified Files

### New Files (8)

| File | Purpose |
|---|---|
| `lib/youtube-oauth.ts` | OAuth utilities (auth URL, token exchange, refresh, revoke) |
| `lib/encryption.ts` | AES-256-GCM encrypt/decrypt for OAuth tokens |
| `app/api/youtube/connect/route.ts` | Initiate OAuth redirect |
| `app/api/youtube/callback/route.ts` | Handle OAuth callback, store tokens |
| `app/api/youtube/disconnect/route.ts` | Revoke & delete connected account |
| `app/api/youtube/publish/route.ts` | Accept publish request, fire Inngest event |
| `app/api/youtube/status/[postId]/route.ts` | Poll upload status |
| `components/youtube-post-modal.tsx` | The publish modal UI |

### Modified Files (5)

| File | Changes |
|---|---|
| [`lib/db/schema.ts`](file:///home/manoj/Developer/makemyclip-remotion/lib/db/schema.ts) | Add `youtubeAccounts` + `youtubePosts` tables |
| [`lib/inngest/functions.ts`](file:///home/manoj/Developer/makemyclip-remotion/lib/inngest/functions.ts) | Add `uploadToYouTube` function |
| [`lib/gemini.ts`](file:///home/manoj/Developer/makemyclip-remotion/lib/gemini.ts) | Add `generateYouTubeMetadata()` |
| [`lib/config.ts`](file:///home/manoj/Developer/makemyclip-remotion/lib/config.ts) | Add `youtubePosting` + `monthlyYouTubePosts` to plan limits |
| `.env` | Add Google OAuth + encryption key vars |

---

## Known Gotchas & Risks

> [!CAUTION]
> **API Quota is the #1 operational risk.** Default YouTube Data API quota is 10,000 units/day. Each upload = ~1,600 units. That's only 6 uploads/day across ALL users. You MUST request a quota increase before launching this feature to paying users.

> [!WARNING]
> **OAuth verification takes 2–6 weeks.** You cannot have more than 100 users use YouTube login until Google verifies your app. Start the verification process the moment you decide to build this.

> [!IMPORTANT]
> **Token refresh is critical.** Google OAuth access tokens expire after 1 hour. The Inngest upload function MUST check expiry and refresh before uploading, or uploads will silently fail. Always refresh proactively before each upload.

### Other Gotchas

- **#Shorts classification:** YouTube classifies a video as a Short based on aspect ratio (9:16) AND duration (≤60s). Since MakeMyClip already outputs 9:16 vertical video, you just need to ensure clips are ≤60s. Adding `#Shorts` to the title/description helps but isn't required.
- **Duplicate uploads:** Add a check — if a clip already has a successful `youtubePosts` entry, confirm before re-uploading.
- **Large file uploads:** Use YouTube's resumable upload protocol. For a 60s 1080p clip (~15–30MB), this should complete in under a minute, but handle network interruptions gracefully.
- **Rate limiting:** YouTube API has per-user rate limits. If a user tries to post many clips quickly, queue them and process sequentially.

---

## Future Enhancements (Post-MVP)

| Feature | Effort | Notes |
|---|---|---|
| Batch scheduling (post 5 clips, one per day) | ~2 days | Multi-select UI + staggered `publishAt` timestamps |
| Instagram Reels | ~1 week | Meta App Review required (weeks–months), needs Business account |
| TikTok | ~3–4 days | "Intent-based" posting (opens TikTok), not silent upload |
| X / Twitter | ~2 days | Requires paid API tier ($100/mo+) |
| Analytics dashboard (views, likes after posting) | ~2 days | YouTube Analytics API, separate quota |
| Thumbnail selection/upload | ~1 day | YouTube allows custom thumbnails for verified channels |
| Auto-post on render complete | ~0.5 days | Add to Inngest render pipeline as optional final step |

---

## When to Build This

**Build this feature when:**
- ✅ You have 10+ paying users on creator/power plans
- ✅ Users are actively requesting it (track with PostHog feature request events)
- ✅ Your core clip-creation pipeline is stable and reliable
- ✅ You've started the Google OAuth verification process (2–6 weeks lead time)

**Don't build this if:**
- ❌ You're still iterating on the core clip detection / reframing quality
- ❌ You have zero paying users
- ❌ You haven't applied for YouTube API quota increase yet

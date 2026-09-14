/**
 * ─────────────────────────────────────────────────────────────────────────────
 * KIVIO MARKETING ASSETS CONFIGURATION
 * ─────────────────────────────────────────────────────────────────────────────
 * This file is the single source of truth for all videos, images, caption
 * demos, and testimonial assets used across the marketing landing page.
 *
 * To swap any video or image:
 * 1. Place your new file in `/public/previews/landing_page_assets/` (or `/public/assets/`).
 * 2. Update the corresponding path or URL in this file.
 * ─────────────────────────────────────────────────────────────────────────────
 */

export interface MarketingVideoAsset {
  id: string
  title: string
  src: string
  poster?: string
  aspectRatio?: "16:9" | "9:16" | "1:1"
  badge?: string
  author?: string
}

export interface CaptionStyleAsset {
  id: string
  name: string
  tag: string
  description: string
  videoSrc: string
  posterSrc?: string
}

export interface TestimonialAsset {
  id: string
  name: string
  handle: string
  role: string
  avatar: string
  content: string
  stats?: string
  stars: number
}

const R2_PUBLIC_URL =
  process.env.NEXT_PUBLIC_R2_PUBLIC_URL ||
  "https://pub-dab84dec13074258806f788a00943c46.r2.dev"

export const MARKETING_ASSETS = {
  // ── 1. HERO INLINE VIDEO CHIPS ─────────────────────────────────────────────
  // These are the small animated video chips rendered directly inside the hero headline.
  // Recommended: Lightweight, looped, silent WebM clips (under 500KB).
  hero: {
    // 16:9 horizontal chip inside "Turn videos [chip]"
    horizontalVideo: `${R2_PUBLIC_URL}/landing_page_assets/hero_horizontal.webm`,
    horizontalDurationBadge: "2h49",

    // 9:16 vertical chip inside "viral [chip] shorts"
    verticalVideo: `${R2_PUBLIC_URL}/landing_page_assets/hero_short.webm`,

    // Sub-headline copy
    tagline: "Create TikToks, Reels, and Shorts from your long videos in just one click.",
    freeTierNotice: "Try for free. No credit card required.",
  },

  // ── 2. BEFORE & AFTER REFRAME SHOWCASE ──────────────────────────────────────
  // The side-by-side comparison demonstrating Kivio's AI Face Tracking and Auto-Reframe.
  reframeShowcase: {
    badge: "Auto Reframe",
    heading: "Turn any landscape video into vertical shorts",
    subheading:
      "Kivio identifies active speakers, tracks movement across widescreen shots, and crafts dynamic vertical framing with burned captions.",
    
    // Original 16:9 landscape input video
    before: {
      title: "Original Widescreen (16:9)",
      src: `${R2_PUBLIC_URL}/landing_page_assets/reframe_landscape.webm`,
      label: "Full 16:9 Podcast / Video",
    },

    // Kivio 9:16 reframed output video with captions
    after: {
      title: "Kivio Reframed (9:16)",
      src: `${R2_PUBLIC_URL}/landing_page_assets/reframe_vertical.webm`,
      label: "Auto-Centered + Captions",
    },
  },

  // ── 3. SHOWCASE VIDEO MARQUEE ───────────────────────────────────────────────
  // Dual-track infinite scrolling rows of 9:16 clips made with Kivio.
  // Hosted on Cloudflare R2 with optimized VP9 WebM streaming.
  marquee: {
    heading: "Formatted for vertical from the start",
    subheading:
      "Kivio centers the speaker, cuts between hosts during multi-person interviews, and generates engaging word-by-word subtitles.",
    
    // Top scrolling track (Moving left)
    topTrack: [
      {
        id: "clip-ali-abdaal",
        title: "Ali Abdaal Productive Habits",
        src: `${R2_PUBLIC_URL}/landing_page_assets/marquee_ali_abdaal.webm`,
        badge: "TikTok",
      },
      {
        id: "clip-modern-wisdom",
        title: "Modern Wisdom Insight",
        src: `${R2_PUBLIC_URL}/landing_page_assets/marquee_modern_wisdom.webm`,
        badge: "Reels",
      },
      {
        id: "clip-marketing-rules",
        title: "YouTube Marketing Rules",
        src: `${R2_PUBLIC_URL}/landing_page_assets/marquee_marketing_rules.webm`,
        badge: "Shorts",
      },
      {
        id: "clip-opportunity",
        title: "Seizing Big Opportunities",
        src: `${R2_PUBLIC_URL}/landing_page_assets/marquee_opportunity.webm`,
        badge: "TikTok",
      },
      {
        id: "clip-advice-rich",
        title: "Advice for Entrepreneurs",
        src: `${R2_PUBLIC_URL}/landing_page_assets/marquee_entrepreneur_advice.webm`,
        badge: "Reels",
      },
    ],

    // Bottom scrolling track (Moving right)
    bottomTrack: [
      {
        id: "clip-gravy",
        title: "Creator Breakdown",
        src: `${R2_PUBLIC_URL}/landing_page_assets/marquee_creator_breakdown.webm`,
        badge: "Shorts",
      },
      {
        id: "clip-batch-split",
        title: "Dual Speaker Split-Screen",
        src: `${R2_PUBLIC_URL}/landing_page_assets/marquee_dual_split.webm`,
        badge: "TikTok",
      },
      {
        id: "clip-emma-interview",
        title: "Interview Deep Dive",
        src: `${R2_PUBLIC_URL}/landing_page_assets/marquee_interview_deepdive.webm`,
        badge: "Reels",
      },
      {
        id: "clip-skateboarding",
        title: "Action & Lifestyle Story",
        src: `${R2_PUBLIC_URL}/landing_page_assets/marquee_action_lifestyle.webm`,
        badge: "Shorts",
      },
      {
        id: "clip-export-hd",
        title: "High Definition Export",
        src: `${R2_PUBLIC_URL}/landing_page_assets/marquee_export_hd.webm`,
        badge: "TikTok",
      },
    ],
  },

  // ── 4. HOW IT WORKS STEPS & VIDEOS ─────────────────────────────────────────
  // Videos for the 3-step cards with hover-to-play interaction (Klap style).
  howItWorks: {
    headingPrefix: "Wondering",
    headingHighlight: "how Kivio works?",
    steps: [
      {
        step: "01",
        title: "Start by uploading a video",
        description:
          "Simply paste a link to your YouTube video, or upload a video file into Kivio. Our AI transcribes and analyzes the full context in seconds.",
        videoSrc: `${R2_PUBLIC_URL}/landing_page_assets/marquee_interview_deepdive.webm`,
      },
      {
        step: "02",
        title: "Let Kivio's AI magically create vertical videos for you",
        description:
          "Just sit back and relax, while Kivio does all the work for you. In a matter of minutes, we will give you multiple viral-worthy clips from your original video with dynamic captions and speaker reframing.",
        videoSrc: `${R2_PUBLIC_URL}/landing_page_assets/marquee_dual_split.webm`,
      },
      {
        step: "03",
        title: "Trim, edit captions, and export in 1080p",
        description:
          "Fine-tune your video length with precision trimming, edit transcript words, switch dynamic caption styles, and export crisp high-definition clips in one click.",
        videoSrc: `${R2_PUBLIC_URL}/landing_page_assets/marquee_export_hd.webm`,
      },
    ],
  },

  // ── 5. CAPTION STYLES SHOWCASE ─────────────────────────────────────────────
  // High-converting subtitle styles available in Kivio, using generated preview clips.
  captionStyles: [
    {
      id: "hormozi",
      name: "Hormozi",
      tag: "High Energy",
      description: "Yellow active word highlight with punchy bold font.",
      videoSrc: `${R2_PUBLIC_URL}/previews/caption_hormozi.webm`,
      posterSrc: `${R2_PUBLIC_URL}/previews/caption_hormozi.jpg`,
    },
    {
      id: "minimal",
      name: "Minimal Clean",
      tag: "Klap Signature",
      description: "Subtle dimmed inactive text with crisp white active word.",
      videoSrc: `${R2_PUBLIC_URL}/previews/caption_minimal.webm`,
      posterSrc: `${R2_PUBLIC_URL}/previews/caption_minimal.jpg`,
    },
    {
      id: "growth",
      name: "Growth",
      tag: "Finance & Tech",
      description: "Electric neon green highlight with italicized emphasis.",
      videoSrc: `${R2_PUBLIC_URL}/previews/caption_growth.webm`,
      posterSrc: `${R2_PUBLIC_URL}/previews/caption_growth.jpg`,
    },
    {
      id: "billy",
      name: "Billy",
      tag: "Top Purple",
      description: "Top-placed headline style with deep 3D purple outline.",
      videoSrc: `${R2_PUBLIC_URL}/previews/caption_billy.webm`,
      posterSrc: `${R2_PUBLIC_URL}/previews/caption_billy.jpg`,
    },
    {
      id: "creator",
      name: "Creator Bold",
      tag: "Modern Vlogger",
      description: "Contrasting color pop with clean background pill badge.",
      videoSrc: `${R2_PUBLIC_URL}/previews/caption_creator.webm`,
      posterSrc: `${R2_PUBLIC_URL}/previews/caption_creator.jpg`,
    },
  ],

  // ── 5. CREATOR TESTIMONIALS ────────────────────────────────────────────────
  // Real or synthesized social proof cards highlighting creator outcomes.
  testimonials: [
    {
      id: "test-1",
      name: "Alex Rivera",
      handle: "@alexcreates",
      role: "Tech YouTuber (240k subs)",
      avatar: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80",
      content:
        "Kivio cut our short-form editing time from 8 hours per week to literally 10 minutes. The auto-reframing on podcast interviews is uncanny.",
      stats: "Saved 30+ hrs/month",
      stars: 5,
    },
    {
      id: "test-2",
      name: "Sarah Jenkins",
      handle: "@thegrowthshow",
      role: "Podcast Host & Producer",
      avatar: "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=120&auto=format&fit=crop&q=80",
      content:
        "The caption styles and speaker split-screens look like they were hand-crafted by an elite agency editor. Our Shorts views tripled in 30 days.",
      stats: "+320% Shorts Reach",
      stars: 5,
    },
    {
      id: "test-3",
      name: "Marcus Vance",
      handle: "@vancemedia",
      role: "Content Agency Director",
      avatar: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=120&auto=format&fit=crop&q=80",
      content:
        "We manage 12 client channels. Being able to drop a YouTube link and get 10 ready-to-post clips with virality scores is a complete superpower.",
      stats: "12 Client Accounts",
      stars: 5,
    },
  ],
}

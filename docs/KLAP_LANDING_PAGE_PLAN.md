# Klap-Inspired Landing Page Overhaul for Kivio (Hero Focus)

We analyzed **[Klap.app](https://klap.app)** (layout, visual badges, copy, feature spotlight, Before/After reframing comparison, social proof). This plan details the architectural and UI upgrades for Kivio's **Hero section** on `app/(marketing)/page.tsx`.

---

## Key Inspirations from Klap.app (Hero Section)

1. **Top Social Trust Badge**: Creator avatar group + *"⭐ Trusted by 10,000+ creators & podcasters"*.
2. **Dynamic Inline Badge Headline**: *"Turn [16:9 chip] long videos into viral [9:16 chip] **shorts**"* with vibrant accent gradient.
3. **Single High-Converting Input Box**: Streamlined YouTube URL paste / file drop input (`UnifiedInput`) with instant action CTA and free-minutes reassurance.
4. **Hero Before/After Visual Proof**:
   - Signature spotlight showing **Horizontal Input Video (16:9)** vs **Created Vertical Short (9:16)**:
     - **Before**: 16:9 widescreen video with detected AI face bounding boxes / speaker labels (`marketing_rules_horizontal_compressed.mp4`).
     - **Center**: "AI Reframed by Kivio" badge with animated processing indicators and Virality Score (98/100).
     - **After**: 9:16 vertical split-screen/reframe with burned animated captions (`marketing_rules_clip_compressed.mp4`).

---

## Video Proof Assets

1. **Horizontal (16:9 Input)**: `public/previews/landing_page_assets/marketing_rules_horizontal_compressed.mp4` (1.4 MB, H.264, fast-start)
2. **Created Clip Proof (9:16 Short)**: `public/previews/landing_page_assets/marketing_rules_clip_compressed.mp4` (975 KB, H.264, fast-start)

---

## User Review Required

> [!NOTE]
> As requested, only the **Hero section** of `app/(marketing)/page.tsx` will be updated in this phase. The rest of the page (marquee, pricing, FAQ) remains intact.

---

## Proposed Changes

### Marketing Components

#### [NEW] [hero-proof-spotlight.tsx](file:///home/manoj/Developer/makemyclip-remotion/components/marketing/hero-proof-spotlight.tsx)
- The flagship Before/After AI Reframe hero demonstration card:
  - High-contrast container matching Klap's spotlight hero style
  - Left: "Before" landscape video with AI speaker detection bounding box (`marketing_rules_horizontal_compressed.mp4`)
  - Center: "AI Reframed by Kivio" badge with Virality Score (98/100)
  - Right: "After" vertical reel with burned animated captions (`marketing_rules_clip_compressed.mp4`)

#### [MODIFY] [page.tsx](file:///home/manoj/Developer/makemyclip-remotion/app/(marketing)/page.tsx)
- Upgrade the Hero section with Klap-inspired headline, trust badge, input CTA, and the `HeroProofSpotlight` component.

---

## Verification Plan

### Automated / Build Verification
- Run `pnpm run build` or `npx tsc --noEmit` to verify zero TypeScript or build errors.

### Visual Verification
- Verify Hero section rendering:
  - Trust badge, headline, and `UnifiedInput` layout.
  - Smooth side-by-side / responsive stacked video playback of horizontal source vs vertical clip proof.tates.

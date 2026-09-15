# Implementation Plan - Step 2: Top Hook Headline Bar Overlay

> **Status:** Saved for later execution. User requested: *"use good colors"* for pill / badge styling.

Implement professional top hook headline bar overlays matching competitor standards (OpusClip, Submagic, Klap) to drastically boost viewer retention in the critical first 3–5 seconds of short-form videos (TikTok, Instagram Reels, YouTube Shorts).

---

## 1. Problem & Motivation

In viral short-form video algorithms, 80%+ of swiping decisions happen in the first **3 seconds**. Competitors like OpusClip and Submagic overlay a high-contrast headline or hook badge near the top of the video that immediately conveys the premise or emotional hook (e.g. *"THE $10,000 MISTAKE"*, *"WAIT FOR IT 😱"*).

Currently, MakeMyClip extracts `title` and `hookText` during AI discovery, but displays them only as metadata in the UI without burning them into the video frames.

Adding an automated, sleek top hook headline overlay will:
1. Immediately communicate context before the viewer swipes away.
2. Maintain clean separation from bottom-aligned spoken captions.
3. Fit comfortably in the upper-third headroom (which we established in Step 1) without obscuring the speaker's face or colliding with TikTok/IG UI safe zones.

---

## 2. Technical Architecture & Design

### A. Subtitle Engine Integration (Zero Extra Encoding Cost)
Instead of adding an expensive extra FFmpeg filter pass or re-encoding video twice, the headline is rendered directly inside the **ASS subtitle stream** (`pysubs2`):
- **Independent Layer**: Uses ASS layers (`Layer=2` for text, `Layer=0/1` for background pill) to avoid any style or alignment collisions with the spoken captions on `Layer=0/1`.
- **Top-Center Alignment**: Anchored at `\an8` (top-center) at `(X=540, Y=210)` on the 1080×1920 canvas.
- **Single Pass Burn**: Burned alongside the captions in the exact same FFmpeg libass step — **0 extra seconds** added to render times.

### B. Safe Zone Compliance
```
┌──────────────────────────────────────────────────┐ Y = 0
│    TikTok / Instagram Status & Account Safe Zone  │ (0 - 150px: DO NOT PLACE)
├──────────────────────────────────────────────────┤ Y = 150
│        [ TOP HOOK HEADLINE PILL / BAR ]          │ (Y = 190 - 270px: SWEET SPOT)
├──────────────────────────────────────────────────┤ Y = 300
│                                                  │
│          Subject Head / Upper Third Area         │ (Top of head ~ Y=380-450)
│                                                  │
│          Spoken Word Captions (Bottom Third)     │ (Y = 1300 - 1550)
│                                                  │
│    TikTok / Reels Caption & Action Buttons Safe  │ (Y = 1650 - 1920)
└──────────────────────────────────────────────────┘ Y = 1920
```

### C. Visual Styles & Premium Color Palettes
*(Refined based on user feedback: "use good colors")*
1. **`pill` (Default & Recommended)**:
   - Modern curved aesthetic with curated premium palettes:
     - **Obsidian Dark**: Sleek `#0F1117` with subtle `#1E2230` border glow and pure `#FFFFFF` bold text.
     - **Cyber Yellow Pop**: Deep black `#0A0A0A` backing with vivid electric gold `#FFE500` / `#FACC15` text.
     - **Emerald / Cyan Accent**: Dark slate `#0B131B` pill with `#00F0FF` or `#34D399` text.
   - Generous rounded padding (`xbord=24`, `ybord=12`) with `\blur2`.
   - Crisp bold text with subtle shadow.
2. **`banner`**:
   - Clean wide banner across the upper bar with subtle gradient or semi-transparent backing.
3. **`clean`**:
   - Transparent background, bold uppercase text with deep stroke and ambient drop shadow (`\shad3\blur4`).

### D. Intelligent Auto-Wrapping & Sizing
- **Short Hooks** ($\le 24$ chars, e.g. *"STOP WASTING TIME"*): Single-line at 46pt.
- **Longer Titles** ($> 24$ chars): Split intelligently into 2 balanced lines using `\N` at word boundaries, scaled to 40pt to preserve headroom.
- **Max Length**: Clamped to 2 lines maximum (safe truncation guard if $> 55$ chars).

### E. Timing & Fade-Out
- **Intro Hook Mode (Default)**:
  - Appears at $t = 0.0\text{s}$.
  - Stays active for $4.5\text{s}$ (configurable via `headline_duration`).
  - At the end of the duration, exits with a silky smooth $350\text{ms}$ fade-out (`{\fad(150, 350)}`), allowing the viewer's focus to seamlessly shift to the speaker and word captions.
- **Persistent Mode**:
  - If `headline_duration` is $0$ or `None`, it remains pinned at the top for the entire clip.

---

## 3. Integration Points

- `modal/models.py`: Add `headline`, `headline_style`, `headline_duration`, `headline_position_y` to `CaptionStyle`, `BatchClipItem`, `BurnCaptionsRequest`, `ReframeRequest`.
- `modal/ass_builder.py`: Implement `_format_headline_text()`, `HeadlineStyle`, `HeadlineBoxStyle`, and layer generation in `generate_ass()`.
- `modal/burner.py`: Forward headline parameters into `generate_ass()`.
- `modal/reframer.py`: Forward `clip_req.headline` into `styling`.
- `lib/inngest/functions.ts`: Pass `clip.hookText || clip.title` into payload.

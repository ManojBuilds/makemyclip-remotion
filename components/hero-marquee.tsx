"use client"

import React from "react"

interface VideoCardProps {
  videoUrl: string
  posterUrl: string
  rotation: string
}

export function MarqueeVideoCard({
  videoUrl,
  posterUrl,
  rotation,
}: VideoCardProps) {
  return (
    <div
      className={`relative h-[370px] w-[210px] flex-shrink-0 cursor-pointer overflow-hidden rounded-3xl border-4 border-white bg-slate-900 shadow-[0_15px_35px_rgba(0,0,0,0.15)] transition-all duration-500 ease-out hover:z-50 hover:-translate-y-6 hover:scale-110 hover:shadow-[0_30px_60px_rgba(0,0,0,0.4)] ${rotation}`}
    >
      {/* Video Preview (Autoplaying, Muted, Loop) */}
      <video
        src={videoUrl}
        poster={posterUrl}
        loop
        muted
        playsInline
        autoPlay
        className="pointer-events-none absolute inset-0 z-0 h-full w-full object-cover"
      />
    </div>
  )
}

const HERO_CLIPS = [
  {
    videoUrl:
      "https://pub-dab84dec13074258806f788a00943c46.r2.dev/hero_interview_preview.mp4",
    posterUrl:
      "https://pub-dab84dec13074258806f788a00943c46.r2.dev/hero_interview_poster.jpg",
    rotation: "rotate-[4deg]",
  },
  {
    videoUrl:
      "https://pub-dab84dec13074258806f788a00943c46.r2.dev/hero_course_preview.mp4",
    posterUrl:
      "https://pub-dab84dec13074258806f788a00943c46.r2.dev/hero_course_poster.jpg",
    rotation: "rotate-[-3deg]",
  },
  {
    videoUrl:
      "https://pub-dab84dec13074258806f788a00943c46.r2.dev/hero_panel_preview.mp4",
    posterUrl:
      "https://pub-dab84dec13074258806f788a00943c46.r2.dev/hero_panel_poster.jpg",
    rotation: "rotate-[6deg]",
  },
  {
    videoUrl:
      "https://pub-dab84dec13074258806f788a00943c46.r2.dev/hero_podcast_preview.mp4",
    posterUrl:
      "https://pub-dab84dec13074258806f788a00943c46.r2.dev/hero_podcast_poster.jpg",
    rotation: "rotate-[-4deg]",
  },
  {
    videoUrl:
      "https://pub-dab84dec13074258806f788a00943c46.r2.dev/hero_ufc_preview.mp4",
    posterUrl:
      "https://pub-dab84dec13074258806f788a00943c46.r2.dev/hero_ufc_poster.jpg",
    rotation: "rotate-[3deg]",
  },
]

export function HeroMarquee() {
  // Repeat the items list multiple times to fill the viewport and wrap seamlessly
  const repeatedClips = [
    ...HERO_CLIPS,
    ...HERO_CLIPS,
    ...HERO_CLIPS,
    ...HERO_CLIPS,
  ]

  return (
    <div className="animate-marquee-paused relative w-full overflow-hidden bg-gradient-to-b from-transparent via-slate-100/50 to-transparent py-12 select-none">
      {/* Decorative Blur/Vignette Edges for premium feel */}
      <div className="pointer-events-none absolute top-0 bottom-0 left-0 z-30 w-24 bg-gradient-to-r from-[#f6f5f4] to-transparent" />
      <div className="pointer-events-none absolute top-0 right-0 bottom-0 z-30 w-24 bg-gradient-to-l from-[#f6f5f4] to-transparent" />

      {/* Marquee Track */}
      <div className="animate-marquee flex items-center gap-6 px-4">
        {repeatedClips.map((clip, index) => (
          <MarqueeVideoCard
            key={`clip-${index}`}
            videoUrl={clip.videoUrl}
            posterUrl={clip.posterUrl}
            rotation={clip.rotation}
          />
        ))}
      </div>
    </div>
  )
}

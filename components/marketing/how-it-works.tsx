"use client"

import { useRef, useEffect } from "react"
import { MARKETING_ASSETS } from "@/lib/marketing-assets"

interface StepItem {
  step: string
  title: string
  description: string
  videoSrc: string
  posterSrc?: string
}

function StepCard({ item }: { item: StepItem }) {
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    // Ensure muted is set at DOM node level for browser autoplay permissions
    if (videoRef.current) {
      videoRef.current.muted = true
    }
  }, [])

  const handleMouseEnter = () => {
    const video = videoRef.current
    if (video) {
      video.muted = true
      const playPromise = video.play()
      if (playPromise !== undefined) {
        playPromise.catch((err) => {
          console.warn("Video hover playback error:", err)
        })
      }
    }
  }

  const handleMouseLeave = () => {
    const video = videoRef.current
    if (video) {
      video.pause()
    }
  }

  return (
    <div
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onPointerEnter={handleMouseEnter}
      onPointerLeave={handleMouseLeave}
      className="group flex flex-col cursor-pointer select-none"
    >
      {/* Outer rounded gray container matching Klap.app */}
      <div className="relative mb-5 overflow-hidden rounded-[24px] sm:rounded-[28px] bg-[#ECEEF1] p-3 sm:p-4 transition-all duration-300 group-hover:bg-[#E3E6EB]">
        <div className="relative overflow-hidden rounded-[16px] sm:rounded-[20px] bg-white border border-slate-200/70 shadow-sm aspect-video">
          <video
            ref={videoRef}
            src={item.videoSrc}
            poster={item.posterSrc}
            loop
            muted
            playsInline
            preload="metadata"
            className="pointer-events-none h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.02]"
          />
        </div>
      </div>

      {/* Title & Description below the visual box */}
      <div className="px-1">
        <h3 className="text-base sm:text-lg font-bold text-slate-900 mb-2 leading-snug group-hover:text-[#0075de] transition-colors">
          {item.title}
        </h3>
        <p className="text-xs sm:text-sm text-slate-600 font-medium leading-relaxed">
          {item.description}
        </p>
      </div>
    </div>
  )
}

export function HowItWorks() {
  const { howItWorks } = MARKETING_ASSETS

  return (
    <section className="relative mx-auto max-w-[1200px] px-6 py-20">
      <div className="mx-auto max-w-3xl text-center mb-16">
        <h2 className="text-3xl sm:text-4xl md:text-5xl font-black tracking-tight text-slate-900">
          <span>{howItWorks.headingPrefix} </span>
          <span className="text-[#0075de]">{howItWorks.headingHighlight}</span>
        </h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {howItWorks.steps.map((item) => (
          <StepCard key={item.step} item={item} />
        ))}
      </div>
    </section>
  )
}

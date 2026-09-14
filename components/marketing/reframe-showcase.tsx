"use client"

import { useState, useRef } from "react"
import { motion } from "framer-motion"
import { Play, Pause, Sparkles, Video, Smartphone } from "lucide-react"
import { MARKETING_ASSETS } from "@/lib/marketing-assets"

export function ReframeShowcase() {
  const { reframeShowcase } = MARKETING_ASSETS
  const [isPlaying, setIsPlaying] = useState(true)
  const beforeVideoRef = useRef<HTMLVideoElement>(null)
  const afterVideoRef = useRef<HTMLVideoElement>(null)

  const togglePlayback = () => {
    if (beforeVideoRef.current && afterVideoRef.current) {
      if (isPlaying) {
        beforeVideoRef.current.pause()
        afterVideoRef.current.pause()
      } else {
        beforeVideoRef.current.play()
        afterVideoRef.current.play()
      }
      setIsPlaying(!isPlaying)
    }
  }

  return (
    <section className="relative mx-auto max-w-[1200px] px-6 py-20">
      <div className="mx-auto max-w-3xl text-center mb-12">
        <div className="inline-flex items-center gap-1.5 rounded-full border border-[#0075de]/20 bg-[#0075de]/5 px-3 py-1 text-xs font-semibold text-[#0075de] mb-4">
          <Sparkles className="h-3.5 w-3.5" />
          <span>{reframeShowcase.badge}</span>
        </div>
        <h2 className="text-2xl sm:text-3xl md:text-4xl font-extrabold tracking-tight text-slate-900 mb-3">
          {reframeShowcase.heading}
        </h2>
        <p className="text-sm sm:text-base font-medium text-slate-600 max-w-2xl mx-auto leading-relaxed">
          {reframeShowcase.subheading}
        </p>
      </div>

      <div className="relative rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 shadow-xl shadow-slate-200/50">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
          
          {/* Left: Original 16:9 Landscape Video */}
          <div className="lg:col-span-7 flex flex-col">
            <div className="flex items-center justify-between mb-3 px-1">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-md bg-slate-100 text-slate-700">
                  <Video className="h-3.5 w-3.5" />
                </span>
                <span className="text-xs font-semibold text-slate-800 uppercase tracking-wider">
                  {reframeShowcase.before.title}
                </span>
              </div>
              <span className="text-[11px] font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                Landscape Raw
              </span>
            </div>

            <div className="relative overflow-hidden rounded-xl border border-slate-200/90 bg-slate-900 aspect-video shadow-sm">
              <video
                ref={beforeVideoRef}
                src={reframeShowcase.before.src}
                autoPlay
                loop
                muted
                playsInline
                className="h-full w-full object-cover"
              />
              
              {/* Speaker Detection Marker Box */}
              <div className="absolute inset-y-8 left-[18%] w-[24%] border-2 border-dashed border-[#0075de] rounded-lg bg-[#0075de]/10 pointer-events-none transition-all duration-300">
                <span className="absolute -top-3 left-2 rounded bg-[#0075de] px-1.5 py-0.5 text-[9px] font-bold text-white uppercase tracking-wider">
                  Speaker 1
                </span>
              </div>
            </div>
          </div>

          {/* Center Divider / Indicator */}
          <div className="hidden lg:flex lg:col-span-1 justify-center items-center">
            <div className="flex flex-col items-center gap-2">
              <div className="h-12 w-px bg-slate-200" />
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#0075de] text-white shadow-md shadow-[#0075de]/20">
                <Sparkles className="h-4 w-4" />
              </div>
              <div className="h-12 w-px bg-slate-200" />
            </div>
          </div>

          {/* Right: Kivio Reframed 9:16 Vertical Video */}
          <div className="lg:col-span-4 flex flex-col items-center">
            <div className="w-full flex items-center justify-between mb-3 px-1">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-md bg-[#0075de]/10 text-[#0075de]">
                  <Smartphone className="h-3.5 w-3.5" />
                </span>
                <span className="text-xs font-semibold text-slate-800 uppercase tracking-wider">
                  {reframeShowcase.after.title}
                </span>
              </div>
              <span className="text-[11px] font-semibold text-[#0075de] bg-[#0075de]/10 px-2 py-0.5 rounded">
                1080x1920
              </span>
            </div>

            <div className="relative overflow-hidden rounded-xl border border-slate-200/90 bg-slate-900 w-[240px] sm:w-[260px] aspect-[9/16] shadow-md">
              <video
                ref={afterVideoRef}
                src={reframeShowcase.after.src}
                autoPlay
                loop
                muted
                playsInline
                className="h-full w-full object-cover"
              />
            </div>
          </div>

        </div>

        {/* Bottom Playback Sync Control Bar */}
        <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
          <button
            onClick={togglePlayback}
            className="inline-flex items-center gap-2 rounded-lg bg-slate-100 hover:bg-slate-200 px-3 py-1.5 font-medium text-slate-800 transition-colors"
          >
            {isPlaying ? (
              <>
                <Pause className="h-3.5 w-3.5" />
                <span>Pause Demo</span>
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5" />
                <span>Play Demo</span>
              </>
            )}
          </button>
          <span className="hidden sm:inline-block font-medium">
            Synced real-time speaker tracking & subtitle preview
          </span>
        </div>
      </div>
    </section>
  )
}

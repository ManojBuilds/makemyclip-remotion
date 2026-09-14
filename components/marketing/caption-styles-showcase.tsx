"use client"

import { useState } from "react"
import { Sparkles, Check, Flame, Sliders } from "lucide-react"
import { MARKETING_ASSETS } from "@/lib/marketing-assets"

export function CaptionStylesShowcase() {
  const { captionStyles } = MARKETING_ASSETS
  const [selectedStyleId, setSelectedStyleId] = useState(captionStyles[0].id)
  const activeStyle = captionStyles.find((s) => s.id === selectedStyleId) || captionStyles[0]

  return (
    <section className="relative mx-auto max-w-[1200px] px-6 py-20">
      <div className="mx-auto max-w-2xl text-center mb-16">
        <div className="inline-flex items-center gap-1.5 rounded-full border border-[#0075de]/20 bg-[#0075de]/5 px-3 py-1 text-xs font-semibold text-[#0075de] mb-4">
          <Sparkles className="h-3.5 w-3.5" />
          <span>Caption Engine</span>
        </div>
        <h2 className="text-2xl sm:text-3xl md:text-4xl font-extrabold tracking-tight text-slate-900 mb-3">
          Word-by-word dynamic animated subtitles
        </h2>
        <p className="text-sm sm:text-base font-medium text-slate-600 leading-relaxed">
          Choose from viral caption presets or customize your brand colors, fonts, and emoji placement.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        {/* Left: Style Selector List */}
        <div className="lg:col-span-6 flex flex-col gap-3">
          {captionStyles.map((style) => {
            const isSelected = style.id === selectedStyleId
            return (
              <button
                key={style.id}
                onClick={() => setSelectedStyleId(style.id)}
                className={`text-left p-4 sm:p-5 rounded-xl border transition-all duration-200 ${
                  isSelected
                    ? "border-[#0075de] bg-blue-50/40 shadow-sm"
                    : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-base font-bold text-slate-900">
                      {style.name}
                    </span>
                    <span className="text-[11px] font-semibold text-[#0075de] bg-[#0075de]/10 px-2 py-0.5 rounded">
                      {style.tag}
                    </span>
                  </div>
                  {isSelected && (
                    <div className="flex h-5 w-5 items-center justify-center rounded-full bg-[#0075de] text-white">
                      <Check className="h-3 w-3 stroke-[3]" />
                    </div>
                  )}
                </div>
                <p className="text-xs sm:text-sm text-slate-600 font-medium">
                  {style.description}
                </p>
              </button>
            )
          })}
        </div>

        {/* Right: Live Caption Video Preview */}
        <div className="lg:col-span-6 flex flex-col items-center justify-center">
          <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-slate-900 w-[260px] sm:w-[300px] aspect-[9/16] shadow-xl shadow-slate-200/50">
            <video
              key={activeStyle.videoSrc}
              src={activeStyle.videoSrc}
              poster={activeStyle.posterSrc}
              autoPlay
              loop
              muted
              playsInline
              className="h-full w-full object-cover"
            />
            <div className="absolute top-3 left-3 right-3 flex items-center justify-between">
              <div className="rounded-full bg-black/60 backdrop-blur-md px-2.5 py-1 text-[11px] font-semibold text-white/90">
                Preset: {activeStyle.name}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

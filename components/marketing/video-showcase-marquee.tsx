"use client"

import { Marquee } from "@/components/shadcn-space/animations/marquee"
import { MARKETING_ASSETS } from "@/lib/marketing-assets"

export function VideoShowcaseMarquee() {
  const { marquee } = MARKETING_ASSETS

  return (
    <section className="relative w-full bg-slate-50/80 py-14 sm:py-16 border-y border-slate-200/80">
      <div className="mx-auto max-w-[1200px] px-6 mb-12 text-center">
        <h2 className="text-2xl sm:text-3xl md:text-4xl font-extrabold tracking-tight text-slate-900 mb-3">
          {marquee.heading}
        </h2>
        <p className="mx-auto max-w-2xl text-sm sm:text-base font-medium text-slate-600 leading-relaxed">
          {marquee.subheading}
        </p>
      </div>

      <div className="relative flex flex-col gap-4 sm:gap-6 w-screen overflow-hidden select-none left-1/2 right-1/2 -ml-[50vw] -mr-[50vw]">
        {/* Top Video Track (Moving Left) */}
        <Marquee className="[--duration:100s] [--gap:16px] sm:[--gap:20px] p-0" pauseOnHover>
          {marquee.topTrack.map((clip, i) => (
            <div
              key={`top-${clip.id}-${i}`}
              className="relative h-[300px] sm:h-[380px] md:h-[440px] lg:h-[480px] aspect-[9/16] shrink-0 overflow-hidden rounded-2xl bg-slate-900 border border-slate-200/80 shadow-lg group"
            >
              <video
                src={clip.src}
                autoPlay
                loop
                muted
                playsInline
                className="h-full w-full object-cover"
              />
              {clip.badge && (
                <div className="absolute top-3 left-3 rounded-full bg-black/60 backdrop-blur-md px-2.5 py-1 text-xs font-semibold text-white/90">
                  {clip.badge}
                </div>
              )}
            </div>
          ))}
        </Marquee>

        {/* Bottom Video Track (Moving Right) */}
        <Marquee className="[--duration:100s] [--gap:16px] sm:[--gap:20px] p-0" reverse pauseOnHover>
          {marquee.bottomTrack.map((clip, i) => (
            <div
              key={`bottom-${clip.id}-${i}`}
              className="relative h-[300px] sm:h-[380px] md:h-[440px] lg:h-[480px] aspect-[9/16] shrink-0 overflow-hidden rounded-2xl bg-slate-900 border border-slate-200/80 shadow-lg group"
            >
              <video
                src={clip.src}
                autoPlay
                loop
                muted
                playsInline
                className="h-full w-full object-cover"
              />
              {clip.badge && (
                <div className="absolute top-3 left-3 rounded-full bg-black/60 backdrop-blur-md px-2.5 py-1 text-xs font-semibold text-white/90">
                  {clip.badge}
                </div>
              )}
            </div>
          ))}
        </Marquee>
      </div>

      {/* Made with Kivio Badge */}
      <div className="mt-10 flex items-center justify-center px-6">
        <div className="inline-flex items-center gap-2 rounded-full border border-slate-200/90 bg-white px-4 py-2 shadow-sm text-xs font-semibold text-slate-700">
          <span className="text-slate-500 font-medium">Made with</span>
          <div className="flex items-center gap-1">
            <img
              src="https://res.cloudinary.com/dc6yzmwrq/image/upload/v1786372588/logo_only_ezfvyn.png"
              alt="kivio"
              className="h-4 w-auto object-contain"
            />
            <span className="font-sans font-black tracking-tight text-slate-900 text-sm leading-none">
              kivio
            </span>
          </div>
        </div>
      </div>
    </section>
  )
}

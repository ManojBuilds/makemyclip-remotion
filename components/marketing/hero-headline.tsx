"use client"

import { MARKETING_ASSETS } from "@/lib/marketing-assets"

export function HeroHeadline() {
  const { hero } = MARKETING_ASSETS

  return (
    <h1 className="mb-6 text-3xl sm:text-5xl md:text-6xl lg:text-[4.25rem] font-black tracking-tight text-slate-900 leading-[1.2] sm:leading-[1.22]">
      <span className="inline-flex flex-wrap items-center justify-center gap-x-2 sm:gap-x-3 align-middle">
        <span>Turn videos</span>
        <span className="relative inline-flex items-center align-middle overflow-hidden rounded-lg sm:rounded-xl border border-slate-200/90 shadow-sm sm:shadow-md w-[64px] h-[36px] sm:w-[90px] sm:h-[51px] md:w-[112px] md:h-[63px] lg:w-[124px] lg:h-[70px] shrink-0 bg-slate-100">
          <video
            src={hero.horizontalVideo}
            autoPlay
            loop
            muted
            playsInline
            className="h-full w-full object-cover"
          />
          <span className="absolute bottom-1 right-1 sm:bottom-1.5 sm:right-1.5 inline-flex items-center rounded sm:rounded-[4px] bg-black/80 px-1 py-0.5 sm:px-1.5 sm:py-0.5 text-[7px] sm:text-[9px] md:text-[10px] font-semibold text-white/95 leading-none tracking-tight tabular-nums shadow-xs backdrop-blur-[2px] border border-white/10 select-none pointer-events-none">
            {hero.horizontalDurationBadge}
          </span>
        </span>
        <span>into</span>
      </span>
      <br />
      <span className="inline-flex flex-wrap items-center justify-center gap-x-2 sm:gap-x-3 align-middle">
        <span>viral</span>
        <span className="relative inline-flex items-center align-middle shrink-0 my-0.5">
          <span className="absolute -inset-0.5 sm:-inset-1 -left-1 sm:-left-1.5 rounded-lg sm:rounded-xl bg-slate-100/90 border border-slate-200/80 -rotate-2 pointer-events-none" />
          <span className="relative overflow-hidden rounded-lg sm:rounded-xl border border-slate-200/90 shadow-md sm:shadow-lg w-[30px] h-[53px] sm:w-[42px] sm:h-[75px] md:w-[52px] md:h-[92px] lg:w-[58px] lg:h-[103px] bg-slate-100">
            <video
              src={hero.verticalVideo}
              autoPlay
              loop
              muted
              playsInline
              className="h-full w-full object-cover"
            />
          </span>
        </span>
        <span className="text-[#0075de]">shorts</span>
      </span>
    </h1>
  )
}

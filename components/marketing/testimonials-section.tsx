"use client"

import { Star } from "lucide-react"
import { MARKETING_ASSETS } from "@/lib/marketing-assets"

export function TestimonialsSection() {
  const { testimonials } = MARKETING_ASSETS

  return (
    <section className="relative mx-auto max-w-[1200px] px-6 py-20">
      <div className="mx-auto max-w-2xl text-center mb-16">
        <h2 className="text-2xl sm:text-3xl md:text-4xl font-extrabold tracking-tight text-slate-900 mb-3">
          Loved by creators and editors
        </h2>
        <p className="text-sm sm:text-base font-medium text-slate-600 leading-relaxed">
          See how creators use Kivio to turn long videos into viral growth channels.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {testimonials.map((t) => (
          <div
            key={t.id}
            className="flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow"
          >
            <div>
              <div className="flex items-center gap-1 mb-4 text-amber-400">
                {Array.from({ length: t.stars }).map((_, idx) => (
                  <Star key={idx} className="h-4 w-4 fill-amber-400 text-amber-400" />
                ))}
              </div>
              <p className="text-sm text-slate-700 font-medium leading-relaxed mb-6">
                &ldquo;{t.content}&rdquo;
              </p>
            </div>

            <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
              <div>
                <h4 className="text-sm font-bold text-slate-900">{t.name}</h4>
                <p className="text-xs text-slate-500 font-medium">{t.role}</p>
              </div>
              {t.stats && (
                <span className="text-[11px] font-semibold text-[#0075de] bg-[#0075de]/10 px-2 py-1 rounded-md">
                  {t.stats}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

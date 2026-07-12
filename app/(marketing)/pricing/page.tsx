"use client"

import { PricingSection, SparkleStar } from "@/components/pricing-section"
import { Button } from "@/components/ui/button"

// Icons and FAQItem are now imported from @/components/pricing-section

export default function PricingPage() {
  return (
    <>
      <div className="relative min-h-screen overflow-hidden bg-white pb-24 text-foreground selection:bg-[#0075de]/20">
        {/* Subtle Background Gradients */}
        <div className="pointer-events-none fixed inset-0 flex justify-between">
          <div className="h-[800px] w-[800px] -translate-x-[20%] -translate-y-[40%] rounded-full bg-[#e8f4fd]/60 blur-[130px]" />
          <div className="h-[800px] w-[800px] translate-x-[30%] translate-y-[20%] rounded-full bg-[#e8f4fd]/50 blur-[130px]" />
        </div>

        <div className="relative z-10 mx-auto flex max-w-[1080px] flex-col items-center px-6 pt-24 pb-16">
          {/* Header Section */}
          <div className="relative mb-12 flex max-w-3xl flex-col items-center text-center">
            {/* Sparkles */}
            <SparkleStar className="absolute top-8 -left-16 h-5 w-5 text-[#cce3f9]" />
            <SparkleStar className="absolute -top-2 right-4 h-3 w-3 text-[#cce3f9]" />
            <SparkleStar className="absolute top-36 -right-6 h-6 w-6 text-[#cce3f9]" />

            <div className="mb-6 inline-flex items-center gap-[6px] rounded-full border border-[#0075de]/20 bg-[#e8f4fd] px-4 py-1.5 text-[13px] font-bold text-[#0075de]">
              Simple pricing{" "}
              <span className="text-[16px] leading-[0] text-[#0075de]">
                &bull;
              </span>{" "}
              No hidden fees
            </div>
            <h1 className="text-[64px] leading-[1.05] font-[800] tracking-[-0.03em] text-[#111827] md:text-[72px]">
              Simple pricing <br />
              <span className="text-[#0075de]">for creators</span>
            </h1>
            <p className="mx-auto mt-6 max-w-[580px] text-[17px] leading-[1.6] font-medium text-[#4B5563]">
              Turn long videos into viral social clips with AI-powered editing,
              captions, reframing, and viral highlight detection.
            </p>
          </div>

          {/* Pricing Section Component */}
          <PricingSection showFAQ={true} showPacks={true} />

          {/* Bottom CTA */}
          <div className="mt-8 w-full rounded-[28px] bg-gradient-to-r from-[#0075de] via-[#0086ff] to-[#3b82f6] px-8 py-14 text-center md:px-16 md:py-16">
            <h2 className="mx-auto max-w-[500px] text-[32px] leading-[1.15] font-[800] tracking-tight text-white md:text-[38px]">
              Ready to make viral clips?
            </h2>
            <p className="mt-3 mb-8 text-[16px] font-medium text-white/85">
              Start creating for free. No credit card required.
            </p>
            <Button className="h-[52px] rounded-full bg-white px-10 text-[15px] font-bold text-[#0075de] shadow-sm transition-all hover:scale-105 hover:bg-gray-50 active:scale-100">
              Get Started Free
            </Button>
          </div>
        </div>
      </div>
    </>
  )
}

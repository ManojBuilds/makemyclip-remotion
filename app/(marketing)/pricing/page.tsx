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


            <h1 className="text-[64px] leading-[1.05] font-[800] tracking-[-0.03em] text-[#111827]">
              Plans
            </h1>
            <p className="mx-auto mt-6 max-w-[580px] text-[17px] leading-[1.6] font-medium text-[#4B5563]">
              No hidden fees. Cancel anytime.
            </p>
          </div>

          {/* Pricing Section Component */}
          <PricingSection showFAQ={true} showPacks={true} />


        </div>
      </div>
    </>
  )
}

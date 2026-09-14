"use client"

import { motion } from "framer-motion"
import { PricingSection } from "@/components/pricing-section"
import { UnifiedInput } from "@/components/video/unified-input"
import { HeroHeadline } from "@/components/marketing/hero-headline"
import { VideoShowcaseMarquee } from "@/components/marketing/video-showcase-marquee"
import { HowItWorks } from "@/components/marketing/how-it-works"
import { MARKETING_ASSETS } from "@/lib/marketing-assets"

const fadeIn = {
  initial: { opacity: 0, y: 20 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-100px" },
  transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] },
}

const staggerContainer = {
  initial: { opacity: 0 },
  whileInView: { opacity: 1 },
  viewport: { once: true, margin: "-100px" },
  transition: { staggerChildren: 0.1 },
}

export default function LandingPage() {
  const { hero } = MARKETING_ASSETS

  return (
    <div className="overflow-hidden bg-[#FAFAFA]">
      <main className="relative z-10">

        {/* ── 1. HERO SECTION ──────────────────────────────────────────────── */}
        <section className="relative mx-auto max-w-[1200px] px-6 pt-32 pb-16">
          <motion.div
            variants={staggerContainer}
            initial="initial"
            animate="whileInView"
            className="mx-auto flex max-w-4xl flex-col items-center text-center"
          >
            <motion.div variants={fadeIn}>
              <HeroHeadline />
            </motion.div>

            <motion.p
              variants={fadeIn}
              className="md:text-lg mx-auto mb-6 max-w-2xl text-sm leading-relaxed text-slate-600 font-medium"
            >
              {hero.tagline}
            </motion.p>

            <motion.div variants={fadeIn} className="mt-2 w-full max-w-2xl">
              <UnifiedInput />
            </motion.div>

            <motion.div
              variants={fadeIn}
              className="mt-4 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-slate-500 font-medium"
            >
              <span>{hero.freeTierNotice}</span>
            </motion.div>
          </motion.div>
        </section>


        {/* ── 3. SHOWCASE VIDEO MARQUEE ────────────────────────────────────── */}
        <VideoShowcaseMarquee />

        {/* ── 4. HOW IT WORKS (3 STEPS) ────────────────────────────────────── */}
        <HowItWorks />

        {/* ── 5. PRICING & FAQ ─────────────────────────────────────────────── */}
        <section id="pricing" className="mx-auto max-w-6xl px-6 py-20">
          <PricingSection
            showFAQ={true}
            showPacks={false}
            showPlans={true}
            showExplanation={true}
          />
        </section>

        {/* ── 8. BOTTOM CALL TO ACTION ─────────────────────────────────────── */}
        <section className="relative mx-auto max-w-[1200px] px-6 py-20 text-center">
          <div className="mx-auto max-w-2xl mb-8">
            <h2 className="text-2xl md:text-3xl font-extrabold text-slate-900 tracking-tight mb-3">
              Ready to turn your videos into viral clips?
            </h2>
            <p className="text-sm md:text-base font-medium text-slate-600 leading-relaxed">
              Paste a link below or drop your file to get started.
            </p>
          </div>
          <UnifiedInput className="max-w-2xl mx-auto" />
        </section>

      </main>
    </div>
  )
}

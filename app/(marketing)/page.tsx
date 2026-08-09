"use client"

import { motion } from "framer-motion"
import { PricingSection } from "@/components/pricing-section"
import { UnifiedInput } from "@/components/video/unified-input"
import { Marquee } from "@/components/shadcn-space/animations/marquee"

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
  return (
    <div className="overflow-hidden">
      <main className="relative z-10">
        {/* 2. HERO SECTION */}
        <section className="relative mx-auto max-w-[1200px] px-6 pt-32 pb-16">


          <motion.div
            variants={staggerContainer}
            initial="initial"
            animate="whileInView"
            className="mx-auto flex max-w-4xl flex-col items-center text-center"
          >
            <motion.h1
              variants={fadeIn}
              className="mb-6 text-2xl leading-[1.05] font-black tracking-tight text-slate-900 md:text-4xl lg:text-[3.2rem]"
            >
              Turn long videos into short clips <br className="hidden md:block" />{" "}
              <span className="text-[#0075de]">ready for social media.</span>
            </motion.h1>

            <motion.p
              variants={fadeIn}
              className="md:text-lg mx-auto mb-4 max-w-4xl text-sm leading-relaxed text-muted-foreground"
            >
              Paste a YouTube link or upload a file. The app finds the best parts, crops them to vertical, and generates styled captions. Ready for TikTok, Reels, and Shorts.
            </motion.p>

            <motion.div variants={fadeIn} className="mt-4 w-full max-w-2xl">
              <UnifiedInput />
            </motion.div>
          </motion.div>

          {/* Hero Video Demo */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
            className="mx-auto mt-8 w-full max-w-3xl px-4"
          >
            <div className="relative rounded-[24px] border border-slate-200/80 bg-white/50 p-2">

              <div className="overflow-hidden rounded-[18px]">
                <video
                  src="https://res.cloudinary.com/dc6yzmwrq/video/upload/v1784086787/hero-demo_mlmvlg.mp4"
                  autoPlay
                  loop
                  muted
                  playsInline
                  className="w-full object-cover shadow-inner"
                />
              </div>
            </div>
          </motion.div>
        </section>

        {/* 3. SHOWCASE / VIDEO SCROLL SECTION */}
        <section className="relative w-full bg-slate-50/50 py-20">
          <div className="mx-auto max-w-[1200px] px-6 mb-16 text-center">
            <h2 className="text-[36px] md:text-[44px] leading-tight font-extrabold tracking-tight text-slate-900 mb-4">
              Cut long videos into shorts
            </h2>
            <p className="mx-auto max-w-[640px] text-[16px] md:text-[17px] font-medium text-slate-500 leading-relaxed">
              Extract clips, generate captions, and export in 9:16. No manual editing needed.
            </p>
          </div>

          <div className="relative flex flex-col gap-6 w-screen overflow-hidden select-none left-1/2 right-1/2 -ml-[50vw] -mr-[50vw]">
            {/* Top Video Track (Moving Left) */}
            <Marquee className="[--duration:100s] [--gap:10px] p-0" pauseOnHover>
              {Array(6).fill("https://res.cloudinary.com/dc6yzmwrq/video/upload/v1785748265/top_web_mtve5g.webm").map((src, i) => (
                <video
                  key={`top-${i}`}
                  src={src}
                  autoPlay
                  loop
                  muted
                  playsInline
                  className="h-[400px] md:h-[575px] w-auto object-cover shrink-0 rounded-none"
                />
              ))}
            </Marquee>

            {/* Bottom Video Track (Moving Right) */}
            <Marquee className="[--duration:100s] [--gap:10px] p-0" reverse pauseOnHover>
              {Array(6).fill("https://res.cloudinary.com/dc6yzmwrq/video/upload/v1785748247/bottom_web_ta2ulm.webm").map((src, i) => (
                <video
                  key={`bottom-${i}`}
                  src={src}
                  autoPlay
                  loop
                  muted
                  playsInline
                  className="h-[400px] md:h-[575px] w-auto object-cover shrink-0 rounded-none"
                />
              ))}
            </Marquee>
          </div>
        </section>
        <UnifiedInput className="max-w-2xl mx-auto" />

        {/* 8. FAQ */}
        <section id="faq" className="mx-auto max-w-4xl px-6 py-24">
          <PricingSection
            showFAQ={true}
            showPacks={false}
            showPlans={false}
            showExplanation={false}
          />
          <UnifiedInput className="max-w-2xl mx-auto" />
        </section>
      </main>
    </div>
  )
}

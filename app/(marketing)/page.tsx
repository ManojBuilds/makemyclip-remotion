"use client"

import { Sparkles, Scissors, Download, CheckCircle2 } from "lucide-react"
import Image from "next/image"
import Link from "next/link"
import { motion } from "framer-motion"
import { Button } from "@/components/ui/button"
import { PricingSection } from "@/components/pricing-section"
import { UnifiedInput } from "@/components/video/unified-input"
import { HeroMarquee } from "@/components/hero-marquee"

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
          {/* Abstract background elements */}
          <div className="absolute top-20 left-10 hidden opacity-40 lg:block">
            <svg
              width="80"
              height="80"
              viewBox="0 0 100 100"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M50 0L55 45L100 50L55 55L50 100L45 55L0 50L45 45L50 0Z"
                fill="#FDBA74"
              />
            </svg>
          </div>
          <div className="absolute top-40 right-10 hidden opacity-40 lg:block">
            <svg
              width="60"
              height="60"
              viewBox="0 0 100 100"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M50 0L55 45L100 50L55 55L50 100L45 55L0 50L45 45L50 0Z"
                fill="#FDBA74"
              />
            </svg>
          </div>

          <div className="absolute top-60 left-0 hidden lg:block">
            <svg
              width="120"
              height="120"
              viewBox="0 0 120 120"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M10 110C40 110 60 80 80 40C90 20 100 10 110 10"
                stroke="#FDBA74"
                strokeWidth="4"
                strokeLinecap="round"
                className="opacity-50"
              />
              <path
                d="M95 10L110 10L110 25"
                stroke="#FDBA74"
                strokeWidth="4"
                strokeLinecap="round"
                className="opacity-50"
              />
            </svg>
          </div>

          <div className="absolute top-20 right-0 hidden scale-x-[-1] transform lg:block">
            <svg
              width="120"
              height="120"
              viewBox="0 0 120 120"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M10 110C40 110 60 80 80 40C90 20 100 10 110 10"
                stroke="#FDBA74"
                strokeWidth="4"
                strokeLinecap="round"
                className="opacity-50"
              />
              <path
                d="M95 10L110 10L110 25"
                stroke="#FDBA74"
                strokeWidth="4"
                strokeLinecap="round"
                className="opacity-50"
              />
            </svg>
          </div>

          <motion.div
            variants={staggerContainer}
            initial="initial"
            animate="whileInView"
            className="mx-auto flex max-w-4xl flex-col items-center text-center"
          >
            <motion.h1
              variants={fadeIn}
              className="mb-6 text-2xl leading-[1.05] font-extrabold tracking-tight text-slate-900 md:text-4xl lg:text-[2.5rem]"
            >
              1 Video In. <br className="hidden md:block" />{" "}
              <span className="text-[#0075de]">A Week of Clips Out.</span>
            </motion.h1>

            <motion.p
              variants={fadeIn}
              className="md:text-md mx-auto mb-4 max-w-xl text-sm leading-relaxed font-medium text-slate-600"
            >
              Turn a 1-hour podcast into 10+ viral clips. MakeMyClip uses AI to
              identify the best moments, crop to vertical, and add professional
              subtitles in seconds.
            </motion.p>

            <motion.div variants={fadeIn} className="mt-4 w-full max-w-2xl">
              <UnifiedInput />
            </motion.div>
          </motion.div>

          {/* Hero Image / UI Mockup */}
          {/* Infinite Marquee Video Clips */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
            className="relative right-1/2 left-1/2 mt-16 -mr-[50vw] -ml-[50vw] w-screen"
          >
            <HeroMarquee />
          </motion.div>
        </section>

        {/* 3. FEATURES */}
        <section
          id="features"
          className="border-y border-slate-100 bg-white px-6 py-24"
        >
          <div className="mx-auto max-w-6xl">
            <div className="mb-16 text-center">
              <span className="mb-4 block text-xs font-bold tracking-widest text-[#0075de] uppercase">
                Features
              </span>
              <h2 className="text-3xl font-extrabold text-slate-900 md:text-5xl">
                The AI video clipper that does all the work for you
              </h2>
            </div>

            <div className="grid gap-6 md:grid-cols-2 md:gap-8">
              {/* Feature 1 */}
              <div className="p-4 md:p-8">
                <div className="mb-6 flex h-12 w-12 items-center justify-start text-[#0075de]">
                  <div className="flex gap-1">
                    <div className="h-1 w-2 bg-[#0075de]"></div>
                    <div className="h-1 w-4 bg-[#0075de]"></div>
                  </div>
                </div>
                <h3 className="mb-3 text-xl font-bold text-slate-900">
                  Auto-Subtitles & Dynamic Captions
                </h3>
                <p className="mb-8 text-sm leading-relaxed text-slate-600">
                  Auto-transcribe your videos with 97%+ accuracy in 30+
                  languages. Style your captions with trendy templates, custom
                  fonts, and dynamic emojis to keep viewers hooked till the last
                  second.
                </p>
                <div className="mt-8 flex items-center justify-center">
                  <Image
                    src="/assets/ai_caption.webp"
                    alt="AI Captions"
                    width={800}
                    height={450}
                    className="h-auto w-full object-contain"
                  />
                </div>
              </div>

              {/* Feature 2 */}
              <div className="p-4 md:p-8">
                <div className="mb-6 flex h-12 w-12 items-center justify-start text-[#0075de]">
                  <Scissors className="h-6 w-6" />
                </div>
                <h3 className="mb-3 text-xl font-bold text-slate-900">
                  AI Auto-Reframe & Speaker Tracking
                </h3>
                <p className="mb-8 text-sm leading-relaxed text-slate-600">
                  Instantly convert widescreen landscape videos (16:9) into
                  social-ready vertical layouts (9:16). Our smart AI speaker
                  tracking detects faces and keeps the active speaker perfectly
                  in the center.
                </p>
                <div className="mt-8 flex items-center justify-center">
                  <Image
                    src="/assets/turn_one_video_into_multiple_shorts.webp"
                    alt="Auto Reframing"
                    width={800}
                    height={450}
                    className="h-auto w-full object-contain"
                  />
                </div>
              </div>

              {/* Feature 3 */}
              <div className="p-4 md:p-8">
                <div className="mb-6 flex h-12 w-12 items-center justify-start text-[#0075de]">
                  <Sparkles className="h-6 w-6" />
                </div>
                <h3 className="mb-3 text-xl font-bold text-slate-900">
                  AI Highlight & Virality Detector
                </h3>
                <p className="mb-8 text-sm leading-relaxed text-slate-600">
                  No more hours spent scrubbing through timelines. Our AI
                  automatically scans your video, identifies the most engaging
                  highlights, rates their virality potential, and clips them
                  instantly.
                </p>
                <div className="mt-8 flex items-center justify-center">
                  <Image
                    src="/assets/hook_generator.png"
                    alt="Viral Clip Detection"
                    width={800}
                    height={450}
                    className="h-auto w-full object-contain"
                  />
                </div>
              </div>

              {/* Feature 4 */}
              <div className="p-4 md:p-8">
                <div className="mb-6 flex h-12 w-12 items-center justify-start text-[#0075de]">
                  <Download className="h-6 w-6" />
                </div>
                <h3 className="mb-3 text-xl font-bold text-slate-900">
                  Multi-Platform Clip Maker
                </h3>
                <p className="mb-8 text-sm leading-relaxed text-slate-600">
                  Create, customize, and export your video clips in perfect
                  dimensions. Optimize your content for TikTok, YouTube Shorts,
                  Instagram Reels, and LinkedIn — all from a single dashboard.
                </p>
                <div className="mt-12 mb-4 flex justify-center gap-8">
                  <Image
                    src="/assets/icons8-tiktok-logo.svg"
                    alt="TikTok"
                    width={80}
                    height={80}
                    className="h-20 w-20 transform cursor-pointer object-contain transition-transform hover:scale-110"
                  />
                  <Image
                    src="/assets/icons8-instagram-logo.svg"
                    alt="Instagram"
                    width={80}
                    height={80}
                    className="h-20 w-20 transform cursor-pointer object-contain transition-transform hover:scale-110"
                  />
                  <Image
                    src="/assets/icons8-youtube-shorts.svg"
                    alt="YouTube Shorts"
                    width={80}
                    height={80}
                    className="h-20 w-20 transform cursor-pointer object-contain transition-transform hover:scale-110"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 4. HOW IT WORKS */}
        <section className="mx-auto max-w-6xl px-6 py-24">
          <div className="mb-16 text-center">
            <span className="mb-4 block text-xs font-bold tracking-widest text-[#0075de] uppercase">
              HOW IT WORKS
            </span>
            <h2 className="text-3xl font-extrabold text-slate-900 md:text-5xl">
              Turn one long video into viral social clips in 3 steps
            </h2>
          </div>

          <div className="relative flex flex-col items-stretch justify-center gap-8 md:flex-row">
            {/* Dashed line connecting steps (desktop) */}
            <div className="absolute top-12 right-1/4 left-1/4 z-0 hidden h-0 border-t-2 border-dashed border-[#cce3f9] md:block" />

            {/* Step 1 */}
            <div className="relative z-10 flex h-full w-full max-w-sm flex-col rounded-3xl border border-slate-100 bg-white p-8 text-center">
              <div className="mb-6 flex h-[200px] items-center justify-center text-[#0075de]">
                <Image
                  src="/assets/upload_video.png"
                  alt="Upload"
                  width={400}
                  height={300}
                  className="max-h-full w-full object-contain"
                />
              </div>
              <h3 className="mb-2 text-xl font-bold text-slate-900">
                Upload or Import
              </h3>
              <p className="text-sm text-slate-500">
                Drag and drop your video file (up to 4K resolution) or paste a
                YouTube link to import instantly.
              </p>
            </div>

            {/* Step 2 */}
            <div className="relative z-10 flex h-full w-full max-w-sm flex-col rounded-3xl border border-slate-100 bg-white p-8 text-center">
              <div className="mb-6 flex h-[200px] items-center justify-center text-[#0075de]">
                <Image
                  src="/assets/hook_generator.png"
                  alt="AI Detection"
                  width={400}
                  height={300}
                  className="max-h-full w-full object-contain drop-shadow-sm"
                />
              </div>
              <h3 className="mb-2 text-xl font-bold text-slate-900">
                Let AI Work Its Magic
              </h3>
              <p className="text-sm text-slate-500">
                Our AI auto-transcribes, highlights the most viral segments,
                adds dynamic styled captions, and auto-reframes for vertical
                layout.
              </p>
            </div>

            {/* Step 3 */}
            <div className="relative z-10 flex h-full w-full max-w-sm flex-col rounded-3xl border border-slate-100 bg-white p-8 text-center">
              <div className="mt-4 mb-6 flex h-[200px] items-center justify-center gap-6">
                <Image
                  src="/assets/icons8-tiktok-logo.svg"
                  alt="TikTok"
                  width={64}
                  height={64}
                  className="h-16 w-16 object-contain"
                />
                <Image
                  src="/assets/icons8-instagram-logo.svg"
                  alt="Instagram"
                  width={64}
                  height={64}
                  className="h-16 w-16 object-contain"
                />
                <Image
                  src="/assets/icons8-youtube-shorts.svg"
                  alt="YouTube Shorts"
                  width={64}
                  height={64}
                  className="h-16 w-16 object-contain"
                />
              </div>
              <div>
                <h3 className="mb-2 text-xl font-bold text-slate-900">
                  Customize & Export
                </h3>
                <p className="text-sm text-slate-500">
                  Fine-tune caption styles, adjust templates or speaker
                  tracking, and export high-quality, social-ready clips.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* 6. PRICING */}
        <section id="pricing" className="mx-auto max-w-6xl px-6 py-24">
          <div className="mb-16 text-center">
            <span className="mb-4 block text-xs font-bold tracking-widest text-[#0075de] uppercase">
              PRICING
            </span>
            <h2 className="mb-6 text-4xl font-[800] tracking-tight text-slate-900 md:text-6xl">
              Flexible plans{" "}
              <span className="text-[#0075de]">for all creators</span>
            </h2>
            <p className="mx-auto mb-12 max-w-xl font-medium text-slate-600">
              Repurpose long videos at scale. Start free, upgrade as your
              channel grows.
            </p>
          </div>
          <PricingSection
            showFAQ={false}
            showPacks={true}
            showPlans={true}
            showExplanation={true}
          />
        </section>

        {/* 8. FAQ */}
        <section id="faq" className="mx-auto max-w-4xl px-6 py-24">
          <PricingSection
            showFAQ={true}
            showPacks={false}
            showPlans={false}
            showExplanation={false}
          />
        </section>

        {/* 9. BOTTOM CTA */}
        <section className="mx-auto mb-16 max-w-6xl px-6 py-24">
          <div className="relative flex w-full flex-col items-center overflow-hidden rounded-[3rem] border border-slate-100 bg-white px-0 pt-12 pb-0 text-center md:pt-20">
            <div className="relative z-10 flex w-full max-w-4xl flex-col items-center px-6 md:px-10">
              <span className="mb-6 block text-sm font-bold tracking-widest text-[#0075de] uppercase md:text-xs">
                START FOR FREE
              </span>

              <h2 className="mb-8 text-4xl leading-tight font-extrabold tracking-tight text-slate-900 md:text-6xl">
                Repurpose your long videos
                <br className="hidden md:block" /> into viral shorts today
              </h2>

              <Button
                asChild
                size="lg"
                className="mb-10 flex h-14 cursor-pointer items-center gap-3 rounded-2xl bg-primary px-6 font-bold text-white transition-transform hover:scale-105 hover:bg-[#005bab] md:h-16 md:px-8"
              >
                <Link href="/signup">
                  <span className="text-lg">Get Started Now</span>
                  <span className="rounded-lg border border-white/10 bg-white/20 px-3 py-1 text-sm font-semibold">
                    Try for free
                  </span>
                </Link>
              </Button>

              <div className="mb-12 flex flex-col items-center justify-center gap-4 text-sm font-bold text-slate-900 md:mb-16 md:flex-row md:gap-8 md:text-base">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-6 w-6 fill-[#0075de] text-white" />{" "}
                  AI Highlight & Hook Finder
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-6 w-6 fill-[#0075de] text-white" />{" "}
                  AI Auto-Reframe (9:16)
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-6 w-6 fill-[#0075de] text-white" />{" "}
                  Trendy Styled Captions
                </div>
              </div>
            </div>

            {/* Bottom Image Component */}
            <div className="relative mt-auto flex w-full justify-center overflow-hidden px-4 md:px-10">
              <Image
                src="/assets/cta.png"
                alt="MakeMyClip creators"
                width={1000}
                height={600}
                className="mt-4 h-auto w-full max-w-4xl object-contain"
              />
              <div className="pointer-events-none absolute right-0 bottom-0 left-0 h-24 bg-gradient-to-t from-white to-transparent md:h-40"></div>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}

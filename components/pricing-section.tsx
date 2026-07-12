"use client"

import { useState } from "react"
import { Check, Info, Zap, Leaf, Crown, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { PLAN_LIMITS } from "@/lib/config"

// Custom SVG Icons
export const CoinStackIcon = ({ className }: { className?: string }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
  >
    <path
      d="M12 8C15.866 8 19 6.65685 19 5C19 3.34315 15.866 2 12 2C8.13401 2 5 3.34315 5 5C5 6.65685 8.13401 8 12 8Z"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M5 5V9C5 10.6569 8.13401 12 12 12C15.866 12 19 10.6569 19 9V5"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M5 9V13C5 14.6569 8.13401 16 12 16C15.866 12 19 10.6569 19 13V9"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M5 13V17C5 18.6569 8.13401 20 12 20C15.866 20 19 17V13"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
)

export const SparkleStar = ({ className }: { className?: string }) => (
  <svg
    viewBox="0 0 24 24"
    fill="currentColor"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
  >
    <path d="M12 0C12 6.62742 17.3726 12 24 12C17.3726 12 12 17.3726 12 24C12 17.3726 6.62742 12 0 12C6.62742 12 12 6.62742 12 0Z" />
  </svg>
)

export const StarIcon = ({ className }: { className?: string }) => (
  <svg
    viewBox="0 0 24 24"
    fill="currentColor"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
  >
    <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
  </svg>
)

export const ShieldCheckIcon = ({ className }: { className?: string }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
  >
    <path
      d="M12 22C12 22 20 18 20 12V5L12 2L4 5V12C4 18 12 22 12 22Z"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M9 12L11 14L15 10"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
)

export function FAQItem({
  question,
  answer,
}: {
  question: string
  answer: React.ReactNode
}) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div
      className="mb-4 flex cursor-pointer flex-col rounded-[16px] bg-[#F8F9FA] px-6 py-[18px] transition-colors hover:bg-gray-100"
      onClick={() => setIsOpen(!isOpen)}
    >
      <div className="flex items-center justify-between">
        <span className="text-[15px] font-bold text-[#111827]">{question}</span>
        <div className="text-xl font-light text-slate-400">
          {isOpen ? "−" : "+"}
        </div>
      </div>
      <div
        className={`overflow-hidden transition-all duration-300 ease-in-out ${isOpen ? "mt-3 max-h-[300px] opacity-100" : "max-h-0 opacity-0"}`}
      >
        <div className="pr-6 text-[14px] leading-relaxed text-[#4B5563]">
          {answer}
        </div>
      </div>
    </div>
  )
}

const DODO_PRODUCT_CREATOR =
  process.env.NEXT_PUBLIC_DODO_PRODUCT_CREATOR || "pdt_0NeAL7ABiEx4ZLymAhpQq"
const DODO_PRODUCT_STARTER =
  process.env.NEXT_PUBLIC_DODO_PRODUCT_STARTER || "pdt_0NeANLYHzcSM9kxNMXr1h"
const DODO_PRODUCT_GROWTH =
  process.env.NEXT_PUBLIC_DODO_PRODUCT_GROWTH || "pdt_0NeANjqG7wNUSJlRNpSJ8"
const DODO_PRODUCT_POWER =
  process.env.NEXT_PUBLIC_DODO_PRODUCT_POWER || "pdt_0NeANzWl0m2Mn1lFOW5yD"

export function PricingSection({
  showFAQ = true,
  showPacks = true,
  showPlans = true,
  showExplanation = true,
}: {
  showFAQ?: boolean
  showPacks?: boolean
  showPlans?: boolean
  showExplanation?: boolean
}) {
  const [loading, setLoading] = useState<string | null>(null)

  const handleSubscribe = async (productId: string, key?: string) => {
    const loadingKey = key || productId
    setLoading(loadingKey)
    try {
      const res = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ productId }),
      })
      const data = await res.json()
      if (data.url) {
        window.location.href = data.url
      } else {
        toast.error("Error creating checkout session")
      }
    } catch (err: unknown) {
      console.error(err)
      toast.error("Something went wrong")
    } finally {
      setLoading(null)
    }
  }

  const featureCheck = (
    <div className="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full border border-[#0075de]">
      <Check className="h-2.5 w-2.5 text-[#0075de]" strokeWidth={3} />
    </div>
  )

  const bulletCheck = (
    <div className="flex h-[18px] w-[18px] flex-shrink-0 items-center justify-center rounded-full bg-[#e8f4fd]">
      <Check className="h-3 w-3 text-[#0075de]" strokeWidth={3} />
    </div>
  )

  return (
    <div className="w-full">
      {/* Pricing Model Explanation */}
      {showExplanation && (
        <div className="relative z-20 mb-16 flex w-full flex-col items-center justify-between gap-6 rounded-[24px] border border-[#E5E7EB] bg-white p-6 shadow-[0_4px_24px_rgba(0,0,0,0.02)] md:flex-row">
          <div className="flex w-full flex-col items-center gap-6 md:flex-row md:items-start">
            <div className="flex h-[68px] w-[68px] flex-shrink-0 items-center justify-center rounded-[20px] bg-[#e8f4fd]">
              <CoinStackIcon className="h-[34px] w-[34px] text-[#0075de]" />
            </div>
            <div className="mt-1 flex-1 space-y-3 text-center md:text-left">
              <h3 className="text-[20px] font-[800] text-[#111827]">
                1 credit = 1 minute of video processing
              </h3>
              <div className="flex flex-col flex-wrap gap-x-6 gap-y-3 text-[13px] font-bold text-[#4B5563] md:flex-row">
                <div className="flex items-center justify-center gap-2 md:justify-start">
                  {bulletCheck}
                  60-min video = 60 credits
                </div>
                <div className="flex items-center justify-center gap-2 md:justify-start">
                  {bulletCheck}
                  Credits used only when processing
                </div>
                <div className="flex items-center justify-center gap-2 md:justify-start">
                  {bulletCheck}
                  Exporting clips does not consume credits
                </div>
              </div>
            </div>
          </div>
          <div className="flex w-full max-w-[280px] flex-shrink-0 items-start gap-3 rounded-[16px] border border-[#cce3f9] bg-white p-4 shadow-sm md:w-auto">
            <div className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border border-[#0075de]">
              <Info className="h-3 w-3 text-[#0075de]" strokeWidth={3} />
            </div>
            <p className="text-[12px] leading-[1.5] font-medium text-[#6B7280]">
              Credits power AI transcription, viral detection, caption
              generation, and reframing.
            </p>
          </div>
        </div>
      )}

      {/* Plans */}
      {showPlans && (
        <div className="relative mb-24 grid w-full grid-cols-1 items-stretch gap-6 md:grid-cols-3">
          {/* Free Plan */}
          <div className="flex flex-col overflow-hidden rounded-[32px] border border-[#E5E7EB] bg-white p-10 shadow-[0_4px_24px_rgba(0,0,0,0.02)]">
            <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-full border border-[#cce3f9] bg-[#e8f4fd]/50 text-[#0075de]">
              <Leaf className="h-6 w-6" strokeWidth={2} />
            </div>
            <h3 className="mb-2 text-[28px] leading-none font-[800] text-[#111827]">
              Free
            </h3>
            <p className="mb-6 text-[14px] font-medium text-[#6B7280]">
              Try MakeMyClip for free
            </p>
            <div className="mb-8 flex items-baseline gap-1">
              <span className="text-[56px] leading-none font-[800] tracking-tight text-[#111827]">
                $0
              </span>
              <span className="text-[15px] font-semibold text-[#6B7280]">
                /month
              </span>
            </div>
            <div className="mb-8 w-full rounded-full border border-[#0075de] py-3 text-center text-[14px] font-bold text-[#0075de]">
              {PLAN_LIMITS.free.monthlyCreditsMinutes} minutes/month
            </div>
            <ul className="flex-1 space-y-[18px] text-[14px] font-bold text-[#374151]">
              {[
                `Max ${PLAN_LIMITS.free.label} video duration`,
                "Watermarked exports",
                "Standard 720p output",
                "Basic subtitle templates only",
                "3-day video storage policy",
                "Upload YouTube links & videos",
                "AI viral moment detection",
              ].map((feature) => (
                <li
                  key={feature}
                  className="flex items-start gap-3 leading-tight"
                >
                  <div className="mt-0.5">{featureCheck}</div>
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
            <Button
              variant="outline"
              className="mt-10 h-[52px] w-full rounded-full border border-[#0075de] text-[15px] font-bold text-[#0075de] transition-colors hover:bg-[#e8f4fd]"
            >
              Get Started Free
            </Button>
          </div>

          {/* Creator Plan */}
          <div className="relative z-10 flex flex-col rounded-[32px] border-2 border-[#0075de] bg-white p-10 shadow-[0_12px_40px_rgba(0,117,222,0.1)] md:-mt-4 md:-mb-4">
            <div className="absolute inset-x-0 -top-4 flex justify-center">
              <div className="flex items-center gap-1.5 rounded-full bg-[#0075de] px-5 py-[6px] text-[13px] font-[800] tracking-wide text-white shadow-md">
                <StarIcon className="h-[14px] w-[14px]" /> Most Popular
              </div>
            </div>
            <div className="mt-2 mb-6 flex h-14 w-14 items-center justify-center rounded-full border border-[#cce3f9] bg-[#e8f4fd]/50 text-[#0075de]">
              <Zap className="h-6 w-6 fill-[#0075de]" strokeWidth={1} />
            </div>
            <h3 className="mb-2 text-[28px] leading-none font-[800] text-[#111827]">
              Creator
            </h3>
            <p className="mb-6 text-[14px] leading-tight font-medium text-[#6B7280]">
              For content creators, marketers & social editors
            </p>
            <div className="mb-8 flex items-baseline gap-1">
              <span className="text-[56px] leading-none font-[800] tracking-tight text-[#111827]">
                $19
              </span>
              <span className="text-[15px] font-semibold text-[#6B7280]">
                /month
              </span>
            </div>
            <div className="mb-8 w-full rounded-full bg-[#0075de] py-3 text-center text-[14px] font-bold text-white shadow-sm">
              {PLAN_LIMITS.creator.monthlyCreditsMinutes} minutes/month
            </div>
            <ul className="flex-1 space-y-[18px] text-[14px] font-bold text-[#374151]">
              {[
                `Max ${PLAN_LIMITS.creator.label} video duration`,
                "No watermarks on export",
                "Full HD (1080p) & 4K exports",
                "Premium template presets",
                "Advanced crop modes",
                "Permanent video hosting",
                "Creates ~150 clips / month",
                "Faster processing queue",
              ].map((feature) => (
                <li
                  key={feature}
                  className="flex items-start gap-3 leading-tight"
                >
                  <div className="mt-0.5">{featureCheck}</div>
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
            <div className="mt-10 flex flex-col items-center">
              <Button
                className="h-[52px] w-full rounded-full bg-[#0075de] text-[15px] font-bold text-white shadow-md transition-all hover:bg-[#005bab]"
                onClick={() => handleSubscribe(DODO_PRODUCT_CREATOR, "creator")}
                disabled={loading === "creator"}
              >
                {loading === "creator"
                  ? "Redirecting..."
                  : "Start Creator Plan"}
              </Button>
            </div>
          </div>

          {/* Power Plan */}
          <div className="flex flex-col rounded-[32px] border border-[#E5E7EB] bg-white p-10 shadow-[0_4px_24px_rgba(0,0,0,0.02)]">
            <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-full border border-[#cce3f9] bg-[#e8f4fd]/50 text-[#0075de]">
              <Crown className="h-6 w-6 fill-[#0075de]" strokeWidth={1} />
            </div>
            <h3 className="mb-2 text-[28px] leading-none font-[800] text-[#111827]">
              Power
            </h3>
            <p className="mb-6 text-[14px] leading-tight font-medium text-[#6B7280]">
              For agencies & high-volume creators
            </p>
            <div className="mb-8 flex items-baseline gap-1">
              <span className="text-[56px] leading-none font-[800] tracking-tight text-[#111827]">
                $49
              </span>
              <span className="text-[15px] font-semibold text-[#6B7280]">
                /month
              </span>
            </div>
            <div className="mb-8 w-full rounded-full border border-[#0075de] py-3 text-center text-[14px] font-bold text-[#0075de]">
              {PLAN_LIMITS.power.monthlyCreditsMinutes} minutes/month
            </div>
            <ul className="flex-1 space-y-[18px] text-[14px] font-bold text-[#374151]">
              {[
                `Max ${PLAN_LIMITS.power.label} video duration`,
                "No watermarks on export",
                "Full HD (1080p) & 4K exports",
                "Premium template presets",
                "Advanced crop modes",
                "Permanent video hosting",
                "Creates ~500 clips / month",
                "Faster processing queue",
              ].map((feature) => (
                <li
                  key={feature}
                  className="flex items-start gap-3 leading-tight"
                >
                  <div className="mt-0.5">{featureCheck}</div>
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
            <Button
              variant="outline"
              className="mt-10 h-[52px] w-full rounded-full border border-[#0075de] text-[15px] font-bold text-[#0075de] transition-colors hover:bg-[#e8f4fd]"
              onClick={() => handleSubscribe(DODO_PRODUCT_POWER, "power")}
              disabled={loading === "power"}
            >
              {loading === "power" ? "Redirecting..." : "Start Power Plan"}
            </Button>
          </div>
        </div>
      )}

      {/* Extra Credit Packs */}
      {showPacks && (
        <div id="packs" className="mb-32 flex w-full flex-col items-center">
          <div className="mb-10 text-center">
            <h2 className="mb-2 text-[32px] font-[800] text-[#111827]">
              Need more processing credits?
            </h2>
            <p className="text-[15px] font-medium text-[#6B7280]">
              Purchase extra credits anytime without upgrading your
              subscription.
            </p>
          </div>
          <div className="grid w-full max-w-3xl grid-cols-1 gap-6 md:grid-cols-2">
            {[
              {
                id: DODO_PRODUCT_STARTER,
                name: "100 Minute Pack",
                price: "5.00",
                credits: "100 credits",
              },
              {
                id: DODO_PRODUCT_GROWTH,
                name: "500 Minute Pack",
                price: "20.00",
                credits: "500 credits",
                bestValue: true,
              },
            ].map((pack) => {
              const isLoading = loading === pack.name
              return (
                <Button
                  key={pack.name}
                  disabled={!!loading}
                  variant="ghost"
                  className={`h-auto w-full border bg-white text-left ${pack.bestValue ? "border-[#0075de] shadow-[0_8px_30px_rgba(0,117,222,0.08)]" : "border-[#E5E7EB] shadow-[0_4px_24px_rgba(0,0,0,0.02)]"} group relative flex items-center justify-between rounded-[24px] p-8 transition-all duration-300 ${isLoading ? "pointer-events-none opacity-70" : "cursor-pointer hover:-translate-y-1"}`}
                  onClick={() => handleSubscribe(pack.id, pack.name)}
                >
                  {pack.bestValue && (
                    <div className="absolute -top-4 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full bg-[#0075de] px-4 py-1.5 text-[12px] font-[800] text-white shadow-md">
                      <StarIcon className="h-3.5 w-3.5 text-white" /> Best Value
                    </div>
                  )}
                  <div className="flex flex-col pt-1">
                    <h4 className="mb-1.5 text-[18px] leading-none font-[800] text-[#111827]">
                      {pack.name}
                    </h4>
                    <p className="mb-5 text-[14px] font-medium text-[#6B7280]">
                      {pack.credits}
                    </p>
                    <div className="text-[40px] leading-none font-[800] text-[#111827]">
                      ${pack.price}
                    </div>
                  </div>
                  <div className="flex h-[68px] w-[68px] items-center justify-center rounded-[20px] border border-[#cce3f9] bg-[#e8f4fd]/50 text-[#0075de] transition-transform group-hover:scale-105">
                    {isLoading ? (
                      <Loader2 className="h-[34px] w-[34px] animate-spin" />
                    ) : (
                      <CoinStackIcon className="h-[34px] w-[34px]" />
                    )}
                  </div>
                </Button>
              )
            })}
          </div>
          <div className="mt-8 flex items-center justify-center gap-2.5 text-center text-[15px] font-medium text-[#6B7280]">
            <ShieldCheckIcon className="h-5 w-5 text-[#0075de]" />
            Purchased credits roll over and never expire.
          </div>
        </div>
      )}

      {/* FAQs */}
      {showFAQ && (
        <div className="mx-auto mb-12 w-full max-w-4xl">
          <div className="mb-10 text-center">
            <h2 className="text-[32px] font-[800] text-[#111827]">
              Frequently asked <span className="text-[#0075de]">questions</span>
            </h2>
          </div>
          <div className="grid grid-cols-1 gap-x-6 md:grid-cols-2">
            <div className="flex flex-col">
              <FAQItem
                question="How many clips will I get?"
                answer={
                  <div className="space-y-2">
                    <p>
                      We only surface moments strong enough to post — we skip
                      the rest so every clip is worth your time. On average, you
                      can expect:
                    </p>
                    <ul className="list-disc space-y-1 pl-4 font-semibold text-slate-700">
                      <li>Under 10 minutes: 2-4 clips</li>
                      <li>10-30 minutes: 4-7 clips</li>
                      <li>30-60 minutes: 8-10 clips</li>
                      <li>60+ minutes: 10-15+ clips</li>
                    </ul>
                  </div>
                }
              />
              <FAQItem
                question="How do credits work?"
                answer="1 credit equals 1 minute of video processing. When you upload a video, we deduct credits based on the length of the original video."
              />
              <FAQItem
                question="Do exports consume credits?"
                answer="No! Credits are only used when the AI processes your video. You can export the generated clips as many times as you like without using any extra credits."
              />
              <FAQItem
                question="What happens if I run out of credits?"
                answer="You can easily purchase additional credit packs anytime without changing your subscription plan. These credits never expire."
              />
            </div>
            <div className="flex flex-col">
              <FAQItem
                question="What video formats are supported?"
                answer="We currently support MP4, MOV, and WebM formats, as well as direct YouTube links."
              />
              <FAQItem
                question="Do unused credits roll over?"
                answer="Subscription credits do not roll over to the next month, but purchased extra credit packs roll over and never expire as long as your account is active."
              />
              <FAQItem
                question="Can I cancel anytime?"
                answer="Yes, you can cancel your subscription at any time from your billing portal. You will continue to have access to your plan until the end of your billing cycle."
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

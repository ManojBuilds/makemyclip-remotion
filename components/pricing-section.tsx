"use client"

import { useState } from "react"
import { Check, Info, Loader2, ChevronDown } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
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
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M5 5V9C5 10.6569 8.13401 12 12 12C15.866 12 19 10.6569 19 9V5"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M5 9V13C5 14.6569 8.13401 16 12 16C15.866 12 19 10.6569 19 13V9"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M5 13V17C5 18.6569 8.13401 20 12 20C15.866 20 19 17V13"
      stroke="currentColor"
      strokeWidth="2"
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
  bgColor?: string
}) {
  const [isOpen, setIsOpen] = useState(true)

  return (
    <div
      className="mb-3 flex cursor-pointer flex-col rounded-2xl border border-slate-200/80 bg-slate-50/50 p-5 md:p-6 transition-all duration-200 hover:border-slate-300 hover:bg-slate-50"
      onClick={() => setIsOpen(!isOpen)}
    >
      <div className="flex items-center justify-between gap-4">
        <span className="text-[15px] md:text-[16px] font-semibold text-slate-900 leading-snug">
          {question}
        </span>
        <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-slate-200/70 text-slate-700 transition-transform duration-200">
          <ChevronDown
            className={`h-4 w-4 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
          />
        </div>
      </div>
      <div
        className={`overflow-hidden transition-all duration-200 ease-in-out ${isOpen ? "mt-3 max-h-[300px] opacity-100" : "max-h-0 opacity-0"}`}
      >
        <div className="text-[14px] font-normal leading-relaxed text-slate-600">
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
  showPowerPlan = false,
}: {
  showFAQ?: boolean
  showPacks?: boolean
  showPlans?: boolean
  showExplanation?: boolean
  showPowerPlan?: boolean
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

  const checkIcon = (
    <Check className="h-4 w-4 flex-shrink-0 text-[#0075de]" strokeWidth={2.5} />
  )

  return (
    <div className="w-full">
      {/* Minimal Pricing Model Explanation */}
      {showExplanation && (
        <div className="mx-auto mb-10 flex max-w-xl items-center justify-center">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="cursor-pointer flex items-center justify-center gap-2 rounded-full border border-slate-200/80 bg-slate-50 px-5 py-2.5 text-center text-[13px] font-medium text-slate-600 shadow-sm transition-all hover:bg-slate-100 hover:border-slate-300">
                  <Info className="h-4 w-4 text-[#0075de] flex-shrink-0" />
                  <span>
                    <strong className="text-slate-900 font-semibold">1 credit = 1 minute</strong> of long-form source video.
                  </span>
                </div>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-sm p-3.5 text-center text-xs bg-slate-900 text-slate-100 shadow-lg rounded-xl leading-relaxed">
                <p>
                  <strong>1 credit = 1 minute</strong> of long-form source video (YouTube link or MP4 upload). Generating and exporting short viral clips from your videos is <strong>unlimited</strong>.
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      )}

      {/* Plans */}
      {showPlans && (
        <div className={`relative mb-16 grid w-full items-stretch gap-6 mx-auto ${showPowerPlan ? "grid-cols-1 md:grid-cols-3 max-w-6xl" : "grid-cols-1 md:grid-cols-2 max-w-4xl"}`}>
          {/* Free Plan */}
          <div className="flex flex-col rounded-3xl border border-slate-200 bg-white p-7 shadow-sm transition-all hover:shadow-md">
            <div className="mb-4">
              <h3 className="text-xl font-bold text-slate-900">Free</h3>
              <p className="text-xs text-slate-500 mt-1">Get started with basic clipping</p>
            </div>
            <div className="mb-6 flex items-baseline gap-1">
              <span className="text-4xl font-extrabold text-slate-900">$0</span>
              <span className="text-sm font-medium text-slate-500">/month</span>
            </div>

            <div className="mb-6 text-xs font-semibold uppercase tracking-wider text-slate-500">
              {PLAN_LIMITS.free.monthlyProcessingMinutes} mins video processing / mo
            </div>

            <ul className="mb-8 flex-1 space-y-3 text-sm text-slate-700">
              <li className="flex items-center gap-2.5">
                {checkIcon}
                <span>Up to 30 min source videos</span>
              </li>
              <li className="flex items-center gap-2.5">
                {checkIcon}
                <span>Automatic clipping & vertical reframing</span>
              </li>
              <li className="flex items-center gap-2.5">
                {checkIcon}
                <span>Automatic captions</span>
              </li>
              <li className="flex items-center gap-2.5 text-slate-400">
                <span className="h-4 w-4 flex-shrink-0 rounded-full border border-slate-300 flex items-center justify-center text-[10px]">&times;</span>
                <span className="line-through">720p with watermark</span>
              </li>
              <li className="flex items-center gap-2.5 text-slate-400">
                <span className="h-4 w-4 flex-shrink-0 rounded-full border border-slate-300 flex items-center justify-center text-[10px]">&times;</span>
                <span className="line-through">3-day video storage</span>
              </li>
            </ul>

            <Button
              variant="outline"
              className="h-11 w-full rounded-full border-slate-300 font-semibold text-slate-700 hover:bg-slate-50"
              onClick={() => {
                window.location.href = "/projects"
              }}
            >
              Get Started Free
            </Button>
          </div>

          {/* Creator Plan (Popular Hero Tier) */}
          <div className="relative flex flex-col rounded-3xl border-2 border-[#0075de] bg-white p-7 shadow-lg shadow-[#0075de]/5">
            <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 rounded-full bg-[#0075de] px-3.5 py-1 text-xs font-semibold text-white shadow-sm flex items-center gap-1.5 whitespace-nowrap">
              <SparkleStar className="h-3.5 w-3.5 fill-white" />
              <span>Most Popular • 2x Opus Clip Minutes</span>
            </div>

            <div className="mb-4 mt-1">
              <h3 className="text-xl font-bold text-slate-900">Creator</h3>
              <p className="text-xs text-slate-500 mt-1">For active creators & podcasters</p>
            </div>
            <div className="mb-6 flex items-baseline gap-1">
              <span className="text-4xl font-extrabold text-slate-900">{PLAN_LIMITS.creator.price}</span>
              <span className="text-sm font-medium text-slate-500">/month</span>
            </div>

            <div className="mb-6 text-xs font-semibold uppercase tracking-wider text-[#0075de]">
              {PLAN_LIMITS.creator.monthlyProcessingMinutes} mins video processing / mo
            </div>

            <ul className="mb-8 flex-1 space-y-3 text-sm text-slate-700">
              <li className="flex items-center gap-2.5">
                {checkIcon}
                <span>Up to {PLAN_LIMITS.creator.maxUploadDurationSeconds / 3600} hour source videos</span>
              </li>
              <li className="flex items-center gap-2.5">
                {checkIcon}
                <span className="font-semibold text-slate-900">300 minutes / month (2x Opus Clip Starter)</span>
              </li>
              <li className="flex items-center gap-2.5">
                {checkIcon}
                <span>No watermark, 1080p Full HD export</span>
              </li>
              <li className="flex items-center gap-2.5">
                {checkIcon}
                <span>Automatic clipping & AI virality scoring</span>
              </li>
              <li className="flex items-center gap-2.5">
                {checkIcon}
                <span>All dynamic Remotion caption styles</span>
              </li>
              <li className="flex items-center gap-2.5">
                {checkIcon}
                <span>Permanent video storage</span>
              </li>
              <li className="flex items-center gap-2.5">
                {checkIcon}
                <span>Fast rendering queue</span>
              </li>
            </ul>

            <Button
              className="h-11 w-full rounded-full bg-[#0075de] font-semibold text-white hover:bg-[#0060b8] shadow-sm transition-all"
              onClick={() => handleSubscribe(DODO_PRODUCT_CREATOR, "creator")}
              disabled={loading === "creator"}
            >
              {loading === "creator" ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" /> Redirecting...
                </span>
              ) : (
                "Start Creator Plan ($15/mo)"
              )}
            </Button>
          </div>

          {/* Power Plan (Preserved for future tier expansion) */}
          {showPowerPlan && (
            <div className="flex flex-col rounded-3xl border border-slate-200 bg-white p-7 shadow-sm transition-all hover:shadow-md">
              <div className="mb-4">
                <h3 className="text-xl font-bold text-slate-900">Power</h3>
                <p className="text-xs text-slate-500 mt-1">For heavy users & agencies</p>
              </div>
              <div className="mb-6 flex items-baseline gap-1">
                <span className="text-4xl font-extrabold text-slate-900">{PLAN_LIMITS.power.price}</span>
                <span className="text-sm font-medium text-slate-500">/month</span>
              </div>

              <div className="mb-6 text-xs font-semibold uppercase tracking-wider text-slate-500">
                {PLAN_LIMITS.power.monthlyProcessingMinutes} mins video processing / mo
              </div>

              <ul className="mb-8 flex-1 space-y-3 text-sm text-slate-700">
                <li className="flex items-center gap-2.5">
                  {checkIcon}
                  <span>Up to 2 hours source videos</span>
                </li>
                <li className="flex items-center gap-2.5">
                  {checkIcon}
                  <span>600 mins processing / month</span>
                </li>
                <li className="flex items-center gap-2.5">
                  {checkIcon}
                  <span>No watermark, 1080p HD export</span>
                </li>
                <li className="flex items-center gap-2.5">
                  {checkIcon}
                  <span>Automatic clipping & vertical reframing</span>
                </li>
                <li className="flex items-center gap-2.5">
                  {checkIcon}
                  <span>All caption styles</span>
                </li>
                <li className="flex items-center gap-2.5">
                  {checkIcon}
                  <span>Priority processing</span>
                </li>
              </ul>

              <Button
                variant="outline"
                className="h-11 w-full rounded-full border-slate-300 font-semibold text-slate-700 hover:bg-slate-50"
                onClick={() => handleSubscribe(DODO_PRODUCT_POWER, "power")}
                disabled={loading === "power"}
              >
                {loading === "power" ? (
                  <span className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" /> Redirecting...
                  </span>
                ) : (
                  "Start Power Plan"
                )}
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Credit Packs */}
      {showPacks && (
        <div id="packs" className="mb-16 flex w-full flex-col items-center">
          <div className="mb-6 text-center max-w-xl">
            <h3 className="text-2xl font-bold text-slate-900">Need extra processing minutes?</h3>
            <p className="mt-1 text-xs text-slate-500">
              Add processing credits on demand. <strong>1 credit = 1 minute</strong> of video.
            </p>
          </div>

          <div className="grid w-full max-w-2xl grid-cols-1 gap-4 md:grid-cols-2">
            {[
              {
                id: DODO_PRODUCT_STARTER,
                name: "100 Minutes",
                price: "$6",
                unitPrice: "$0.06 / min",
                credits: "100 video processing credits",
              },
              {
                id: DODO_PRODUCT_GROWTH,
                name: "250 Minutes",
                price: "$12",
                unitPrice: "$0.048 / min",
                credits: "250 video processing credits",
                bestValue: true,
                discountBadge: "Save 20%",
              },
            ].map((pack) => {
              const isLoading = loading === pack.name
              return (
                <div
                  key={pack.name}
                  className={`relative flex items-center justify-between rounded-2xl border p-5 bg-white transition-all ${pack.bestValue ? "border-[#0075de] shadow-md ring-1 ring-[#0075de]/20" : "border-slate-200 shadow-sm"
                    }`}
                >
                  {pack.bestValue && (
                    <div className="absolute -top-2.5 right-4 flex items-center gap-1 rounded-full bg-[#0075de] px-2.5 py-0.5 text-[10px] font-bold text-white shadow-sm">
                      <span>{pack.discountBadge}</span>
                      <span>•</span>
                      <span>Best Value</span>
                    </div>
                  )}

                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-base font-bold text-slate-900">{pack.name}</h4>
                      <span className="text-[10px] font-semibold text-[#0075de] bg-[#0075de]/10 px-2 py-0.5 rounded-full">
                        {pack.unitPrice}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">{pack.credits}</p>
                    <div className="mt-1 text-xl font-extrabold text-slate-900">{pack.price}</div>
                  </div>

                  <Button
                    size="sm"
                    variant={pack.bestValue ? "default" : "outline"}
                    className={`rounded-full px-5 font-bold text-xs ${pack.bestValue
                      ? "bg-[#0075de] hover:bg-[#0060b8] text-white shadow-sm"
                      : "border-slate-300 text-slate-700 hover:bg-slate-50"
                      }`}
                    onClick={() => handleSubscribe(pack.id, pack.name)}
                    disabled={!!loading}
                  >
                    {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Buy Pack"}
                  </Button>
                </div>
              )
            })}
          </div>

          <div className="mt-4 flex items-center gap-2 text-xs font-medium text-slate-500">
            <ShieldCheckIcon className="h-4 w-4 text-[#0075de] flex-shrink-0" />
            <span>Credits never expire & roll over indefinitely.</span>
          </div>
        </div>
      )}

      {/* FAQs */}
      {showFAQ && (
        <div className="mx-auto mb-8 w-full max-w-3xl">
          <div className="mb-6 text-center">
            <h3 className="text-2xl font-bold text-slate-900">Frequently Asked Questions</h3>
          </div>

          <div className="space-y-3">
            <FAQItem
              question="What does Kivio do?"
              answer="It automatically cuts your long videos into short clips, adds styled captions, reframes the video to 9:16 vertical, and lets you download them ready to post."
            />
            <FAQItem
              question="How do credits work?"
              answer="1 credit = 1 minute of source video. A 10-minute video uses 10 credits. Editing captions or downloading your clips doesn't cost extra credits."
            />
            <FAQItem
              question="Do unused credits roll over?"
              answer="Monthly plan credits reset each month. Credit packs you purchase separately never expire."
            />
            <FAQItem
              question="What video formats and platforms are supported?"
              answer="You can upload MP4, MOV, or WebM files, or paste a YouTube link. The exported clips are optimized for TikTok, Reels, and Shorts."
            />
            <FAQItem
              question="Can I cancel my subscription?"
              answer="Yes, you can cancel or change your plan anytime from your settings page."
            />
          </div>
        </div>
      )}
    </div>
  )
}


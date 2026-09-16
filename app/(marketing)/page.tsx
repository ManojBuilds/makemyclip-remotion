import type { Metadata } from "next"
import { LandingPageContent } from "@/components/marketing/landing-page-content"
import { FaqJsonLd } from "@/components/seo/json-ld"

export const metadata: Metadata = {
  title: "Kivio #1 AI Video Clipping Agent | Turn Long Videos into Viral Shorts",
  description:
    "AI Agent that automatically transforms your long YouTube videos and podcasts into viral TikToks, Instagram Reels, and YouTube Shorts with face tracking, auto reframing, and animated captions.",
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "Kivio #1 AI Video Clipping Agent",
    description:
      "Transform long videos into viral social clips with intelligent editing, captions, and 9:16 vertical reframing.",
    url: "/",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Kivio #1 AI Video Clipping Agent",
    description:
      "Transform long videos into viral social clips with intelligent editing, captions, and 9:16 vertical reframing.",
  },
}

export default function LandingPage() {
  return (
    <>
      <FaqJsonLd />
      <LandingPageContent />
    </>
  )
}

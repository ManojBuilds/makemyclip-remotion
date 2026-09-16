import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Pricing & Plans - Kivio AI Video Clipping",
  description:
    "Explore transparent pricing plans and pay-as-you-go credit packs for creators, agencies, and video editors. Turn long videos into viral social clips with AI.",
  alternates: {
    canonical: "/pricing",
  },
  openGraph: {
    title: "Pricing & Plans | Kivio AI Video Clipping",
    description:
      "Explore transparent pricing plans and pay-as-you-go credit packs for creators, agencies, and video editors.",
    url: "/pricing",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Pricing & Plans | Kivio AI Video Clipping",
    description:
      "Explore transparent pricing plans and pay-as-you-go credit packs for creators, agencies, and video editors.",
  },
}

export default function PricingLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return <>{children}</>
}

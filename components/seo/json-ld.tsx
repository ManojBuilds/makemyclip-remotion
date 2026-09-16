import React from "react"

interface JsonLdProps {
  data: Record<string, any>
}

export function JsonLd({ data }: JsonLdProps) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  )
}

export function WebsiteJsonLd() {
  const baseUrl = process.env.NEXT_PUBLIC_APP_URL || "https://kivio.pro"

  const schema = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebSite",
        "@id": `${baseUrl}/#website`,
        "url": baseUrl,
        "name": "Kivio",
        "description":
          "AI Agent that transforms your long videos and podcasts into viral social clips with intelligent editing, captions, and auto-reframing.",
        "inLanguage": "en-US",
      },
      {
        "@type": "Organization",
        "@id": `${baseUrl}/#organization`,
        "name": "Kivio",
        "url": baseUrl,
        "logo": {
          "@type": "ImageObject",
          "url":
            "https://res.cloudinary.com/dc6yzmwrq/image/upload/v1786372287/ChatGPT_Image_Aug_10_2026_07_43_43_PM_1_jrlmgz.png",
          "width": 1200,
          "height": 630,
        },
        "contactPoint": {
          "@type": "ContactPoint",
          "email": "support@kivio.pro",
          "contactType": "customer service",
        },
      },
      {
        "@type": "SoftwareApplication",
        "@id": `${baseUrl}/#application`,
        "name": "Kivio - AI Video Clipping Agent",
        "applicationCategory": "MultimediaApplication",
        "operatingSystem": "All",
        "url": baseUrl,
        "description":
          "Turn long videos into viral shorts, TikToks, and Instagram Reels with AI-powered clipping, animated captions, and automatic vertical reframing.",
        "offers": {
          "@type": "Offer",
          "price": "0",
          "priceCurrency": "USD",
          "description": "Free trial with credits included",
        },
        "featureList": [
          "AI-powered viral clip selection",
          "Automatic 9:16 vertical reframing & face tracking",
          "Dynamic animated captions and subtitle styles",
          "Export in 1080p 60fps ready for YouTube Shorts, TikTok & Reels",
          "YouTube link & local file upload support",
        ],
      },
    ],
  }

  return <JsonLd data={schema} />
}

export function FaqJsonLd() {
  const faqSchema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
      {
        "@type": "Question",
        "name": "What does Kivio do?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text":
            "Kivio automatically cuts your long videos into short viral clips, adds styled captions, reframes the video to 9:16 vertical with face tracking, and lets you download them ready to post on TikTok, Reels, and YouTube Shorts.",
        },
      },
      {
        "@type": "Question",
        "name": "How do credits work?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text":
            "1 credit = 1 minute of source video. A 10-minute video uses 10 credits. Editing captions or downloading your clips doesn't cost extra credits.",
        },
      },
      {
        "@type": "Question",
        "name": "Do unused credits roll over?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text":
            "Monthly plan credits reset each month. Credit packs you purchase separately never expire.",
        },
      },
      {
        "@type": "Question",
        "name": "What video formats and platforms are supported?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text":
            "You can upload MP4, MOV, or WebM files, or paste a YouTube link. The exported clips are optimized for TikTok, Instagram Reels, and YouTube Shorts.",
        },
      },
      {
        "@type": "Question",
        "name": "Can I add my own custom brand logo / watermark to clips?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text":
            "Yes! Paid plans allow you to upload your custom PNG or SVG brand logo, choose its corner position, and adjust transparency and scale. Free plan clips include standard platform branding.",
        },
      },
      {
        "@type": "Question",
        "name": "Can I cancel my subscription?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text":
            "Yes, you can cancel or change your plan anytime from your account settings page.",
        },
      },
    ],
  }

  return <JsonLd data={faqSchema} />
}

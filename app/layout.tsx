import { Geist_Mono, Poppins } from "next/font/google"
import type { Metadata } from "next"
import { ClerkProvider } from "@clerk/nextjs"

import "./globals.css"
import { Toaster } from "sonner"
import { ThemeProvider } from "@/components/theme-provider"
import { PostHogProvider } from "@/components/providers/posthog-provider"
import { DashboardProvider } from "@/components/dashboard-context"
import { WebsiteJsonLd } from "@/components/seo/json-ld"
import { cn } from "@/lib/utils"

const siteName = "Kivio #1 AI Video Clipping Agent"
const siteDescription =
  "AI Agent that transforms your long videos and podcasts into viral social clips with intelligent editing, captions, and 9:16 vertical auto-reframing."

const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://kivio.pro"
const metadataBase = new URL(appUrl)

export const metadata: Metadata = {
  metadataBase,
  applicationName: "Kivio",
  manifest: "/site.webmanifest",
  appleWebApp: {
    title: "Kivio",
    statusBarStyle: "default",
    capable: true,
  },
  icons: {
    icon: [
      { url: "/favicon-96x96.png", sizes: "96x96", type: "image/png" },
      { url: "/favicon.svg", type: "image/svg+xml" },
    ],
    shortcut: "/favicon.ico",
    apple: [
      { url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" },
    ],
  },
  title: {
    default: siteName,
    template: `%s | Kivio`,
  },
  description: siteDescription,
  keywords: [
    "AI video clipping",
    "video clipping agent",
    "viral clip generator",
    "YouTube shorts generator",
    "TikTok clips maker",
    "Instagram reels generator",
    "auto captions generator",
    "video reframing AI",
    "podcast video clips",
    "Kivio",
    "AI video editor",
  ],
  authors: [{ name: "Kivio Team", url: appUrl }],
  creator: "Kivio",
  publisher: "Kivio",
  category: "technology",
  alternates: {
    canonical: "/",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  verification: {
    google: "WIuA8iRZtBfH9F9Hvl_p71gecHMUMfjMn0Hh5Gm0gEQ",
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: appUrl,
    siteName: "Kivio",
    title: siteName,
    description: siteDescription,
    images: [
      {
        url: "https://res.cloudinary.com/dc6yzmwrq/image/upload/v1786372287/ChatGPT_Image_Aug_10_2026_07_43_43_PM_1_jrlmgz.png",
        width: 1200,
        height: 630,
        alt: "Kivio - #1 AI Video Clipping Agent",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: siteName,
    description: siteDescription,
    images: [
      "https://res.cloudinary.com/dc6yzmwrq/image/upload/v1786372287/ChatGPT_Image_Aug_10_2026_07_43_43_PM_1_jrlmgz.png",
    ],
  },
}

const inter = Poppins({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-sans",
})

const fontMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
})

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <ClerkProvider>
      <html
        lang="en"
        suppressHydrationWarning
        className={cn(
          "antialiased",
          fontMono.variable,
          inter.variable,
          "font-sans"
        )}
      >
        <body>
          <WebsiteJsonLd />
          <PostHogProvider>
            <ThemeProvider defaultTheme="light">
              <DashboardProvider>{children}</DashboardProvider>
            </ThemeProvider>
            <Toaster position="top-right" richColors closeButton />
          </PostHogProvider>
        </body>
      </html>
    </ClerkProvider>
  )
}

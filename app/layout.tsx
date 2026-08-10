import { Geist_Mono, TikTok_Sans } from "next/font/google"
import type { Metadata } from "next"
import { Analytics } from "@vercel/analytics/next"
import { ClerkProvider } from "@clerk/nextjs"

import "./globals.css"
import { Toaster } from "sonner"
import { ThemeProvider } from "@/components/theme-provider"
import { cn } from "@/lib/utils"

const siteName = "Kivio #1 AI Video Clipping Agent"
const siteDescription =
  "AI Agent that transforms your long videos into viral social clips with intelligent editing, captions, reframing, and more"

const metadataBase =
  process.env.NEXT_PUBLIC_APP_URL && process.env.NEXT_PUBLIC_APP_URL.length > 0
    ? new URL(process.env.NEXT_PUBLIC_APP_URL)
    : new URL("http://localhost:3000")

export const metadata: Metadata = {
  metadataBase,
  applicationName: "Kivio",
  manifest: "/site.webmanifest",
  appleWebApp: {
    title: "Kivio",
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
  openGraph: {
    type: "website",
    siteName: "Kivio",
    title: siteName,
    description: siteDescription,
    images: [
      {
        url: "https://res.cloudinary.com/dc6yzmwrq/image/upload/v1786372287/ChatGPT_Image_Aug_10_2026_07_43_43_PM_1_jrlmgz.png",
        width: 1200,
        height: 630,
        alt: "Kivio Logo",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: siteName,
    description: siteDescription,
    images: ["https://res.cloudinary.com/dc6yzmwrq/image/upload/v1786372287/ChatGPT_Image_Aug_10_2026_07_43_43_PM_1_jrlmgz.png"],
  },
  isReadOnly: true, // not a standard Next metadata property, just keeping user changes if any
} as any

const inter = TikTok_Sans({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800", "900"],
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
          <ThemeProvider>{children}</ThemeProvider>
          <Toaster position="top-right" richColors closeButton />
          <Analytics />
        </body>
      </html>
    </ClerkProvider>
  )
}

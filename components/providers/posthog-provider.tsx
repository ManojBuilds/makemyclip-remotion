"use client"

import { useEffect, Suspense } from "react"
import { usePathname, useSearchParams } from "next/navigation"
import { useUser } from "@clerk/nextjs"
import posthog from "posthog-js"
import { PostHogProvider as PHProvider } from "posthog-js/react"

// Initialize PostHog client side once (only in production)
if (typeof window !== "undefined" && process.env.NODE_ENV === "production") {
  const token = process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN
  const posthogHost =
    process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com"

  if (token) {
    posthog.init(token, {
      api_host:
        process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com",
      autocapture: false,
      capture_pageview: false,
      capture_pageleave: true,
    })
  }
}

function PostHogUserSync() {
  const { user, isLoaded, isSignedIn } = useUser()

  useEffect(() => {
    if (!isLoaded) return

    if (isSignedIn && user) {
      const email = user.primaryEmailAddress?.emailAddress
      const name = user.fullName || user.username || undefined

      posthog.identify(user.id, {
        email,
        name,
        created_at: user.createdAt,
      })
    } else {
      posthog.reset()
    }
  }, [user, isLoaded, isSignedIn])

  return null
}

function PostHogPageView() {
  const pathname = usePathname()
  const searchParams = useSearchParams()

  useEffect(() => {
    if (pathname) {
      let url = window.origin + pathname
      if (searchParams && searchParams.toString()) {
        url = `${url}?${searchParams.toString()}`
      }
      posthog.capture("$pageview", {
        $current_url: url,
      })
    }
  }, [pathname, searchParams])

  return null
}

export function PostHogProvider({ children }: { children: React.ReactNode }) {
  return (
    <PHProvider client={posthog}>
      <PostHogUserSync />
      <Suspense fallback={null}>
        <PostHogPageView />
      </Suspense>
      {children}
    </PHProvider>
  )
}

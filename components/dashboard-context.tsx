"use client"

import { useEffect } from "react"
import { useUser } from "@clerk/nextjs"
import { useUserStore, type DashboardUser, type UserStatus } from "@/lib/store/useUserStore"

export type { DashboardUser, UserStatus }

export function DashboardProvider({ children }: { children: React.ReactNode }) {
  const { user: clerkUser, isLoaded, isSignedIn } = useUser()
  const setUser = useUserStore((state) => state.setUser)
  const setStatus = useUserStore((state) => state.setStatus)

  useEffect(() => {
    if (!isLoaded) {
      setStatus("loading")
      return
    }

    if (!isSignedIn || !clerkUser) {
      setStatus("unauthenticated")
      setUser(null)
      return
    }

    let isMounted = true

    const fetchUser = async () => {
      try {
        const res = await fetch("/api/user/me")
        if (!res.ok) {
          throw new Error("Failed to fetch user profile")
        }
        const data = await res.json()
        if (isMounted) {
          setUser({
            name: data.name || "User",
            email: data.email || "",
            plan: data.plan || "free",
            credits: data.credits ?? 30,
            dodoCustomerId: data.dodoCustomerId || null,
            subscriptionStatus: data.subscriptionStatus || "inactive",
          })
          setStatus("authenticated")
        }
      } catch (err) {
        console.error("Error loading user profile:", err)
        if (isMounted) {
          setStatus("error")
        }
      }
    }

    void fetchUser()

    return () => {
      isMounted = false
    }
  }, [clerkUser, isLoaded, isSignedIn, setUser, setStatus])

  return <>{children}</>
}

export function useDashboardUser() {
  const user = useUserStore((state) => state.user)
  const status = useUserStore((state) => state.status)

  return { user, status }
}

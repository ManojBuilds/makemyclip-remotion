"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useUserStore, type DashboardUser, type UserStatus } from "@/lib/store/useUserStore"

export type { DashboardUser, UserStatus }

export function DashboardProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const status = useUserStore((state) => state.status)
  const fetchUser = useUserStore((state) => state.fetchUser)

  useEffect(() => {
    fetchUser()
  }, [fetchUser])

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login")
    }
  }, [status, router])

  return <>{children}</>
}

export function useDashboardUser() {
  const user = useUserStore((state) => state.user)
  const status = useUserStore((state) => state.status)

  return { user, status }
}


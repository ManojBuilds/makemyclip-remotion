import { create } from "zustand"

export type DashboardUser = {
  name: string
  email: string
  plan: string
  credits: number
  dodoCustomerId?: string | null
  subscriptionStatus?: string
}

export type UserStatus = "loading" | "authenticated" | "unauthenticated" | "error"

interface UserStore {
  user: DashboardUser | null
  status: UserStatus
  isLoaded: boolean
  fetchUser: (force?: boolean) => Promise<void>
  setUser: (user: DashboardUser | null) => void
  setStatus: (status: UserStatus) => void
  deductCredits: (amount: number) => void
}

export const useUserStore = create<UserStore>((set, get) => ({
  user: null,
  status: "loading",
  isLoaded: false,
  fetchUser: async (force = false) => {
    // If already loaded and authenticated, skip unless forced
    if (get().isLoaded && get().status === "authenticated" && !force) {
      return
    }

    try {
      const res = await fetch("/api/me")
      if (res.status === 401) {
        set({ user: null, status: "unauthenticated", isLoaded: true })
        return
      }

      if (!res.ok) {
        set({ user: null, status: "error", isLoaded: true })
        return
      }

      const data = (await res.json()) as { user: DashboardUser }
      set({ user: data.user, status: "authenticated", isLoaded: true })
    } catch (error) {
      console.error("Failed to load dashboard user in store:", error)
      set({ user: null, status: "error", isLoaded: true })
    }
  },
  setUser: (user) => set({ user }),
  setStatus: (status) => set({ status }),
  deductCredits: (amount) => {
    const { user } = get()
    if (user) {
      set({
        user: {
          ...user,
          credits: Math.max(0, user.credits - amount),
        },
      })
    }
  },
}))

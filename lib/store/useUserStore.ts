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
  setUser: (user: DashboardUser | null) => void
  setStatus: (status: UserStatus) => void
  deductCredits: (amount: number) => void
}

export const useUserStore = create<UserStore>((set, get) => ({
  user: null,
  status: "loading",
  isLoaded: false,
  setUser: (user) => set({ user, isLoaded: true }),
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

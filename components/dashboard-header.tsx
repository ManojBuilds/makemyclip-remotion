"use client"

import { useMemo } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import Image from "next/image"
import { signOut } from "@/lib/auth-client"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Gem, Sparkles } from "lucide-react"
import { useDashboardUser } from "@/components/dashboard-context"
import { Skeleton } from "@/components/ui/skeleton"

export function DashboardHeader() {
  const router = useRouter()
  const { user: me, status } = useDashboardUser()
  const planLabel = useMemo(() => {
    const plan = (me?.plan || "free").trim()
    if (!plan) return "Free"
    return plan.charAt(0).toUpperCase() + plan.slice(1)
  }, [me?.plan])

  const lowCredits = (me?.credits ?? 0) <= 15
  const topUpHref = "/pricing#packs"

  const userInitials = me?.name
    ? me.name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2)
    : "U"

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex min-h-16 max-w-7xl items-center justify-between gap-3 px-3 py-2 sm:px-4">
        <div className="flex min-w-0 items-center gap-3 sm:gap-6">
          <Link href="/projects" className="flex items-center gap-2">
            <Image
              src="/assets/logo.png"
              alt="MakeMyClip"
              width={32}
              height={32}
              className="h-8 w-auto object-contain"
            />
            <span className="truncate text-lg font-bold tracking-tight text-slate-900 sm:text-xl">
              MakeMyClip
            </span>
          </Link>

        </div>
        <div className="flex flex-1 items-center justify-end gap-2 sm:space-x-4">
          <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white/90 px-2.5 py-1.5 shadow-sm sm:hidden">
            <span className="text-[11px] font-semibold text-slate-900">
              {planLabel}
            </span>
            <span className="text-[11px] text-slate-300">•</span>
            <span
              className={`text-[11px] font-bold whitespace-nowrap ${lowCredits ? "text-amber-800" : "text-slate-700"}`}
            >
              {status === "authenticated" && me ? (
                `${me.credits}`
              ) : (
                <Skeleton className="h-3 w-8 inline-block" />
              )}
            </span>
          </div>

          <div className="hidden items-center gap-3 rounded-2xl border border-slate-200 bg-white/80 px-3 py-2 shadow-sm sm:flex">
            <div
              className={`flex items-center gap-2 rounded-full px-3 py-1.5 ${lowCredits ? "border border-amber-200 bg-amber-50 text-amber-800" : "border border-slate-200 bg-secondary/50 text-foreground"}`}
            >
              <Gem
                className={`h-3.5 w-3.5 ${lowCredits ? "text-amber-600" : "text-primary"}`}
              />
              <span className="text-xs font-bold">
                {status === "authenticated" && me ? (
                  `${me.credits}`
                ) : (
                  <Skeleton className="h-3 w-8 inline-block" />
                )}
              </span>
            </div>
            <Button
              variant={lowCredits ? "default" : "outline"}
              size="sm"
              className={`h-8 rounded-full px-3 text-xs font-semibold ${lowCredits ? "border-0 bg-amber-500 text-white hover:bg-amber-600" : "border-slate-200 text-slate-700 hover:bg-slate-50"}`}
              onClick={() => router.push(topUpHref)}
            >
              {lowCredits ? "Buy credits" : "Top up"}
            </Button>
          </div>
          <Button
            variant={lowCredits ? "default" : "outline"}
            size="sm"
            className={`h-8 rounded-full px-3 text-xs font-semibold sm:hidden ${lowCredits ? "border-0 bg-amber-500 text-white hover:bg-amber-600" : "border-slate-200 text-slate-700 hover:bg-slate-50"}`}
            onClick={() => router.push(topUpHref)}
          >
            {lowCredits ? "Buy credits" : "Top up"}
          </Button>

          <nav className="flex items-center space-x-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  className="relative h-8 w-8 rounded-full"
                >
                  <Avatar className="h-8 w-8">
                    <AvatarFallback>{userInitials}</AvatarFallback>
                  </Avatar>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="w-56" align="end" forceMount>
                <DropdownMenuItem className="flex flex-col items-start gap-1 p-2">
                  <div className="text-sm leading-none font-medium">
                    {me?.name || "User"}
                  </div>
                  <div className="text-xs leading-none text-muted-foreground">
                    {me?.email || ""}
                  </div>
                </DropdownMenuItem>
                <DropdownMenuSeparator />

                {me?.dodoCustomerId && (
                  <DropdownMenuItem asChild>
                    <Link href="/settings">Billing</Link>
                  </DropdownMenuItem>
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={async () => {
                    try {
                      const res = await signOut()
                      console.log(res)
                    } catch (error) {
                      console.log(error)
                    }
                    router.push("/login")
                  }}
                >
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </nav>
        </div>
      </div>
    </header>
  )
}

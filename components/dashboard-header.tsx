"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { useClerk, useUser } from "@clerk/nextjs"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Gem, Sparkles } from "lucide-react"
import { useDashboardUser } from "@/components/dashboard-context"
import { Skeleton } from "@/components/ui/skeleton"
import { Logo } from "./logo"
import { TopUpModal } from "@/components/ui/topup-modal"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

function formatCreditsFull(credits: number = 0): string {
  const totalSeconds = Math.max(0, Math.round(credits * 60))
  if (totalSeconds === 0) {
    return "0 seconds of video processing left"
  }

  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60

  const parts: string[] = []
  if (hours > 0) {
    parts.push(`${hours} ${hours === 1 ? "hour" : "hours"}`)
  }
  if (minutes > 0) {
    parts.push(`${minutes} ${minutes === 1 ? "minute" : "minutes"}`)
  }
  if (seconds > 0) {
    parts.push(`${seconds} ${seconds === 1 ? "second" : "seconds"}`)
  }

  return `${parts.join(", ")} of video processing left`
}

export function DashboardHeader() {
  const { signOut } = useClerk()
  const { user: clerkUser, isLoaded: clerkLoaded } = useUser()
  const [showTopUpModal, setShowTopUpModal] = useState(false)
  const { user: me, status } = useDashboardUser()

  const isDbLoading = status === "loading" || !me

  const isFree = (me?.plan || "free").trim().toLowerCase() === "free"

  const planLabel = useMemo(() => {
    const plan = (me?.plan || "free").trim()
    if (!plan) return "Free"
    return plan.charAt(0).toUpperCase() + plan.slice(1)
  }, [me?.plan])

  const lowCredits = status === "authenticated" && me ? me.credits <= 15 : false

  const creditTooltipText = useMemo(() => {
    if (me?.credits === undefined || me?.credits === null)
      return "0 seconds of video processing left"
    return formatCreditsFull(me.credits)
  }, [me?.credits])

  // Prioritize instant Clerk user profile data
  const userName = me?.name || clerkUser?.fullName || clerkUser?.firstName || "User"
  const userEmail = me?.email || clerkUser?.primaryEmailAddress?.emailAddress || ""
  const userAvatarUrl = clerkUser?.imageUrl

  const userInitials = useMemo(() => {
    if (userName && userName !== "User") {
      return userName
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    }
    return "U"
  }, [userName])

  return (
    <>
      <TopUpModal open={showTopUpModal} onOpenChange={setShowTopUpModal} />
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto flex min-h-16 max-w-7xl items-center justify-between gap-3 px-3 py-2 sm:px-4">
          <div className="flex min-w-0 items-center gap-3 sm:gap-6">
            <Logo href="/projects" />
          </div>
          <div className="flex flex-1 items-center justify-end gap-2 sm:space-x-3">
            {/* Mobile Plan / Credit display */}
            <div className="flex items-center gap-2 sm:hidden">
              {isDbLoading ? (
                <Skeleton className="h-7 w-20 rounded-full" />
              ) : (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="flex cursor-help items-center gap-1.5 rounded-full border border-slate-200 bg-white/90 px-2.5 py-1 shadow-sm">
                        <span
                          className={`text-[11px] font-semibold ${
                            !isFree
                              ? lowCredits
                                ? "text-amber-700"
                                : "text-primary"
                              : "text-slate-900"
                          }`}
                        >
                          {planLabel}
                        </span>
                        <span className="text-[11px] text-slate-300">•</span>
                        <span
                          className={`text-[11px] font-bold whitespace-nowrap ${
                            lowCredits ? "text-amber-800" : "text-slate-700"
                          }`}
                        >
                          {me?.credits ?? 0}
                        </span>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" className="px-2.5 py-1 text-xs font-medium">
                      {creditTooltipText}
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
            </div>

            {/* Desktop Plan / Credit / Upgrade Container */}
            <div className="hidden items-center gap-3 rounded-2xl border border-slate-200 bg-white/80 px-3 py-1.5 shadow-sm sm:flex">
              {isDbLoading ? (
                <div className="flex items-center gap-2">
                  <Skeleton className="h-7 w-20 rounded-full" />
                  <Skeleton className="h-8 w-20 rounded-full" />
                </div>
              ) : (
                <>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div
                          className={`flex cursor-help items-center gap-2 rounded-full px-3 py-1 ${
                            lowCredits
                              ? "border border-amber-200 bg-amber-50 text-amber-800"
                              : "border border-slate-200 bg-secondary/50 text-foreground"
                          }`}
                        >
                          {!isFree ? (
                            <span
                              className={`text-[10px] font-semibold ${
                                lowCredits ? "text-amber-700" : "text-primary"
                              }`}
                            >
                              {planLabel}
                            </span>
                          ) : (
                            <Gem
                              className={`h-3.5 w-3.5 ${
                                lowCredits ? "text-amber-600" : "text-primary"
                              }`}
                            />
                          )}
                          <span className="text-xs font-bold">{me?.credits ?? 0}</span>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent side="bottom" className="px-2.5 py-1 text-xs font-medium">
                        {creditTooltipText}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>

                  {isFree ? (
                    <Button
                      asChild
                      size="sm"
                      className="h-8 rounded-full bg-primary px-3 text-xs font-semibold text-primary-foreground hover:bg-primary/95 border-0 shadow-sm"
                    >
                      <Link href="/pricing">
                        <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                        Upgrade
                      </Link>
                    </Button>
                  ) : (
                    <Button
                      variant={lowCredits ? "default" : "outline"}
                      size="sm"
                      className={`h-8 rounded-full px-3 text-xs font-semibold ${
                        lowCredits
                          ? "border-0 bg-primary text-primary-foreground hover:bg-primary/95 shadow-sm"
                          : "border-slate-200 text-slate-700 hover:bg-slate-50"
                      }`}
                      onClick={() => setShowTopUpModal(true)}
                    >
                      {lowCredits ? "Buy credits" : "Top up"}
                    </Button>
                  )}
                </>
              )}
            </div>

            {/* Mobile Action Button */}
            {!isDbLoading && (
              <>
                {isFree ? (
                  <Button
                    asChild
                    size="sm"
                    className="h-8 rounded-full bg-primary px-3 text-xs font-semibold text-primary-foreground hover:bg-primary/95 border-0 shadow-sm sm:hidden"
                  >
                    <Link href="/pricing">
                      <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                      Upgrade
                    </Link>
                  </Button>
                ) : (
                  <Button
                    variant={lowCredits ? "default" : "outline"}
                    size="sm"
                    className={`h-8 rounded-full px-3 text-xs font-semibold sm:hidden ${
                      lowCredits
                        ? "border-0 bg-primary text-primary-foreground hover:bg-primary/95 shadow-sm"
                        : "border-slate-200 text-slate-700 hover:bg-slate-50"
                    }`}
                    onClick={() => setShowTopUpModal(true)}
                  >
                    {lowCredits ? "Buy credits" : "Top up"}
                  </Button>
                )}
              </>
            )}

            {/* User Profile Dropdown (Renders instantly using Clerk data) */}
            <nav className="flex items-center space-x-2">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    className="relative h-8 w-8 rounded-full p-0 overflow-hidden"
                  >
                    {!clerkLoaded && isDbLoading ? (
                      <Skeleton className="h-8 w-8 rounded-full" />
                    ) : (
                      <Avatar className="h-8 w-8">
                        {userAvatarUrl && <AvatarImage src={userAvatarUrl} alt={userName} />}
                        <AvatarFallback className="text-xs font-bold bg-primary/10 text-primary">
                          {userInitials}
                        </AvatarFallback>
                      </Avatar>
                    )}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent className="w-56" align="end" forceMount>
                  <DropdownMenuItem className="flex flex-col items-start gap-1 p-2">
                    <div className="text-sm leading-none font-medium text-foreground">
                      {userName}
                    </div>
                    {userEmail && (
                      <div className="text-xs leading-none text-muted-foreground">
                        {userEmail}
                      </div>
                    )}
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />

                  <DropdownMenuItem asChild>
                    <Link href="/projects" className="cursor-pointer">Projects</Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link href="/settings" className="cursor-pointer">Settings & Brand Kit</Link>
                  </DropdownMenuItem>

                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={async () => {
                      await signOut()
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
    </>
  )
}

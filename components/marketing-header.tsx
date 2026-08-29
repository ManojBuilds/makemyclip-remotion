"use client"

import React, { useState, useEffect, useMemo } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import { Menu, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Logo } from "@/components/logo"
import { useAuth, useClerk, useUser, SignUpButton } from "@clerk/nextjs"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Skeleton } from "@/components/ui/skeleton"

export function MarketingHeader() {
  const [scrolled, setScrolled] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const { isSignedIn } = useAuth()
  const { signOut } = useClerk()
  const { user: clerkUser, isLoaded: clerkLoaded } = useUser()

  const userName = clerkUser?.fullName || clerkUser?.firstName || "User"
  const userEmail = clerkUser?.primaryEmailAddress?.emailAddress || ""
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

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener("scroll", handleScroll)
    handleScroll()
    return () => window.removeEventListener("scroll", handleScroll)
  }, [])

  return (
    <>
      <header
        className={`fixed top-0 right-0 left-0 z-50 transition-all duration-300 ${scrolled
          ? "border-b border-slate-100 bg-white/80 py-3 shadow-sm backdrop-blur-md"
          : "bg-transparent py-5"
          }`}
      >
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6">

          <Logo />

          <nav className="hidden items-center gap-8 md:flex">

            <Link
              href="/pricing"
              className="text-sm font-medium text-slate-600 transition-colors hover:text-slate-900"
            >
              Pricing
            </Link>
            <Link
              href="/#faq"
              className="text-sm font-medium text-slate-600 transition-colors hover:text-slate-900"
            >
              FAQ
            </Link>
          </nav>

          <div className="hidden items-center gap-3 md:flex">
            {isSignedIn ? (
              <>
                <Link href="/projects">
                  <Button className="rounded-md border-0 bg-primary px-5 font-semibold text-white shadow-sm hover:bg-primary/95">
                    Dashboard
                  </Button>
                </Link>

                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      className="relative h-9 w-9 rounded-full p-0 overflow-hidden border border-slate-200 shadow-sm hover:bg-slate-100"
                    >
                      {!clerkLoaded ? (
                        <Skeleton className="h-9 w-9 rounded-full" />
                      ) : (
                        <Avatar className="h-9 w-9">
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
              </>
            ) : (
              <SignUpButton mode="modal" forceRedirectUrl="/projects">
                <Button className="rounded-md border-0 bg-primary px-5 font-semibold text-white shadow-sm hover:bg-primary/95">
                  Get Started
                </Button>
              </SignUpButton>
            )}
          </div>

          <Button
            variant="ghost"
            size="icon"
            className="z-50 text-slate-600 hover:bg-transparent md:hidden"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            {mobileMenuOpen ? <X /> : <Menu />}
          </Button>
        </div>
      </header>

      {/* Mobile Menu */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="fixed inset-0 z-40 flex flex-col gap-6 bg-white px-6 pt-24 md:hidden"
          >
            <Link
              href="/#features"
              className="text-2xl font-semibold text-slate-800"
              onClick={() => setMobileMenuOpen(false)}
            >
              Features
            </Link>
            <Link
              href="/pricing"
              className="text-2xl font-semibold text-slate-800"
              onClick={() => setMobileMenuOpen(false)}
            >
              Pricing
            </Link>
            <Link
              href="/#faq"
              className="text-2xl font-semibold text-slate-800"
              onClick={() => setMobileMenuOpen(false)}
            >
              FAQ
            </Link>
            <div className="mt-auto flex flex-col gap-4 pb-12">
              {isSignedIn ? (
                <div className="flex flex-col gap-3">
                  <div className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50 p-3">
                    <Avatar className="h-10 w-10">
                      {userAvatarUrl && <AvatarImage src={userAvatarUrl} alt={userName} />}
                      <AvatarFallback className="text-xs font-bold bg-primary/10 text-primary">
                        {userInitials}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex flex-col min-w-0">
                      <span className="text-sm font-semibold text-slate-900 truncate">{userName}</span>
                      {userEmail && <span className="text-xs text-slate-500 truncate">{userEmail}</span>}
                    </div>
                  </div>
                  <Link href="/projects" onClick={() => setMobileMenuOpen(false)}>
                    <Button className="w-full rounded-md border-0 bg-primary py-6 text-lg text-white shadow-sm hover:bg-primary/95">
                      Dashboard
                    </Button>
                  </Link>
                  <Button
                    variant="outline"
                    className="w-full rounded-md border-slate-200 py-3 text-slate-600 hover:bg-slate-100"
                    onClick={async () => {
                      setMobileMenuOpen(false)
                      await signOut()
                    }}
                  >
                    Log out
                  </Button>
                </div>
              ) : (
                <SignUpButton mode="modal" forceRedirectUrl="/projects">
                  <Button
                    className="w-full rounded-md border-0 bg-primary py-6 text-lg text-white shadow-sm hover:bg-primary/95"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    Get Started
                  </Button>
                </SignUpButton>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}

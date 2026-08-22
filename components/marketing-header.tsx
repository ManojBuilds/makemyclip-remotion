"use client"

import React, { useState, useEffect } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import { Menu, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Logo } from "@/components/logo"
import { useAuth, SignUpButton } from "@clerk/nextjs"

export function MarketingHeader() {
  const [scrolled, setScrolled] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const { isSignedIn } = useAuth()

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

          <div className="hidden items-center gap-4 md:flex">
            {isSignedIn ? (
              <Link href="/projects">
                <Button className="rounded-md border-0 bg-primary px-5 font-semibold text-white shadow-sm hover:bg-primary/95">
                  Dashboard
                </Button>
              </Link>
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
                <Link href="/projects" onClick={() => setMobileMenuOpen(false)}>
                  <Button className="w-full rounded-md border-0 bg-primary py-6 text-lg text-white shadow-sm hover:bg-primary/95">
                    Dashboard
                  </Button>
                </Link>
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

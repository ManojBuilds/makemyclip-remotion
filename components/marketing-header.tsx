"use client"

import React, { useState, useEffect } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import { Menu, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useSession } from "@/lib/auth-client"

export function MarketingHeader() {
  const [scrolled, setScrolled] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const { data: session } = useSession()

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener("scroll", handleScroll)
    handleScroll()
    return () => window.removeEventListener("scroll", handleScroll)
  }, [])

  return (
    <>
      <header
        className={`fixed top-0 right-0 left-0 z-50 transition-all duration-300 ${
          scrolled
            ? "border-b border-slate-100 bg-white/80 py-3 shadow-sm backdrop-blur-md"
            : "bg-transparent py-5"
        }`}
      >
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6">
          <Link
            href="/"
            className="z-50 flex cursor-pointer items-center gap-2"
          >
            <img
              src="/assets/logo.png"
              alt="MakeMyClip"
              className="h-8 w-auto object-contain md:h-10"
            />
            <span className="text-xl font-bold tracking-tight text-slate-900">
              MakeMyClip
            </span>
          </Link>

          <nav className="hidden items-center gap-8 md:flex">
            <Link
              href="/#features"
              className="text-sm font-medium text-slate-600 transition-colors hover:text-slate-900"
            >
              Features
            </Link>
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
            {session ? (
              <Link href="/projects">
                <Button className="rounded-md border-0 bg-primary px-5 font-semibold text-white shadow-sm hover:bg-primary/95">
                  Dashboard
                </Button>
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  className="rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:text-slate-900"
                >
                  Log in
                </Link>
                <Link href="/login">
                  <Button className="rounded-md border-0 bg-primary px-5 font-semibold text-white shadow-sm hover:bg-primary/95">
                    Get Started
                  </Button>
                </Link>
              </>
            )}
          </div>

          <Button
            variant="ghost"
            size="icon"
            className="z-50 text-slate-600 hover:bg-transparent focus-visible:ring-0 md:hidden"
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
              {session ? (
                <Link href="/projects" onClick={() => setMobileMenuOpen(false)}>
                  <Button className="w-full rounded-md border-0 bg-primary py-6 text-lg text-white shadow-sm hover:bg-primary/95">
                    Dashboard
                  </Button>
                </Link>
              ) : (
                <>
                  <Link href="/login" onClick={() => setMobileMenuOpen(false)}>
                    <Button
                      variant="outline"
                      className="w-full rounded-md border-slate-200 py-6 text-lg text-slate-700"
                    >
                      Log in
                    </Button>
                  </Link>
                  <Link href="/login" onClick={() => setMobileMenuOpen(false)}>
                    <Button className="w-full rounded-md border-0 bg-primary py-6 text-lg text-white shadow-sm hover:bg-primary/95">
                      Get Started
                    </Button>
                  </Link>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}

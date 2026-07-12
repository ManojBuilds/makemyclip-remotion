import React from "react"
import Link from "next/link"

export function MarketingFooter() {
  return (
    <footer className="border-t border-slate-200 bg-white px-6 py-8">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 sm:flex-row">
        <div className="flex items-center gap-2">
          <img
            src="/assets/logo.png"
            alt="MakeMyClip"
            className="h-7 w-auto object-contain"
          />
          <span className="text-sm font-semibold text-slate-900">
            MakeMyClip
          </span>
        </div>

        <nav className="flex items-center gap-6 text-sm text-slate-500">
          <Link
            href="/#features"
            className="transition-colors hover:text-slate-900"
          >
            Features
          </Link>
          <Link
            href="/pricing"
            className="transition-colors hover:text-slate-900"
          >
            Pricing
          </Link>
          <Link href="/#faq" className="transition-colors hover:text-slate-900">
            FAQ
          </Link>
        </nav>

        <p className="text-sm text-slate-400">
          © {new Date().getFullYear()} MakeMyClip
        </p>
      </div>
    </footer>
  )
}

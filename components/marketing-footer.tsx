import React from "react"
import Link from "next/link"
import { Logo } from "./logo"

export function MarketingFooter() {
  return (
    <footer className="border-t border-slate-200 bg-white px-6 py-8">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 sm:flex-row">
        <Logo />

        <nav className="flex items-center gap-6 text-sm text-slate-500">

          <Link
            href="/privacy"
            className="transition-colors hover:text-slate-900"
          >Privacy Policy</Link>
          <Link href="/terms" className="transition-colors hover:text-slate-900">Terms of Service</Link>
        </nav>

        <p className="text-sm text-slate-400">
          © {new Date().getFullYear()} Kivio
        </p>
      </div>
    </footer>
  )
}

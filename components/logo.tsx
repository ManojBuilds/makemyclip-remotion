import React from "react"
import { cn } from "@/lib/utils"
import Link from "next/link"

interface LogoProps {
  className?: string
  iconClassName?: string
  textClassName?: string
  href?: string
}

export function Logo({ className, iconClassName, textClassName, href = "/"
}: LogoProps) {
  return (
    <Link href={href}>

      <div className={cn("flex items-center select-none", className)}>
        <img
          src="/assets/logo_only.png"
          alt="kivio"
          className={cn("h-8 w-auto object-contain md:h-10", iconClassName)}
        />
        <span className={cn("font-sans text-xl font-black tracking-tight text-slate-900 md:text-3xl leading-none -ml-[0.5]", textClassName)}>
          kivio
        </span>
      </div>
    </Link>
  )
}

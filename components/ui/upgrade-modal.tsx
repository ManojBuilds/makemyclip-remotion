"use client"

import React from "react"
import { Sparkles, Check, ArrowRight, ShieldCheck, Zap } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import {
  UPGRADE_PROMPTS,
  UpgradePrompt,
  dismissPrompt,
} from "@/lib/upgrade-prompts"

interface UpgradeModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  triggerId?: string | null
  customPrompt?: Partial<UpgradePrompt> | null
}

export function UpgradeModal({
  open,
  onOpenChange,
  triggerId,
  customPrompt,
}: UpgradeModalProps) {
  const basePrompt = triggerId ? UPGRADE_PROMPTS[triggerId] : null
  const prompt: UpgradePrompt | null = (customPrompt || basePrompt || null) as UpgradePrompt | null

  if (!prompt) return null

  const handleDismiss = (openState: boolean) => {
    if (!openState && triggerId) {
      dismissPrompt(triggerId)
    }
    onOpenChange(openState)
  }

  const handleUpgrade = () => {
    if (triggerId) {
      dismissPrompt(triggerId)
    }
    onOpenChange(false)
    const targetPlanSlug = prompt.targetPlan ? prompt.targetPlan.toLowerCase() : "creator"
    window.location.href = `/pricing?plan=${targetPlanSlug}`
  }

  return (
    <Dialog open={open} onOpenChange={handleDismiss}>
      <DialogContent className="gap-0 overflow-hidden rounded-3xl bg-background p-0 shadow-2xl sm:max-w-[480px]">
        {/* Header Section in standard App theme */}
        <DialogHeader className="p-6 text-left">
          <DialogTitle className="text-xl font-bold tracking-tight text-foreground">
            {prompt.title}
          </DialogTitle>

          <DialogDescription className="mt-1.5 text-xs font-medium leading-relaxed text-muted-foreground">
            {prompt.description}
          </DialogDescription>
        </DialogHeader>

        <Separator />

        {/* Feature breakdown */}
        <div className="px-6 py-5 space-y-3.5 bg-muted/20">
          <div className="text-[11px] font-black uppercase tracking-wider text-muted-foreground">
            What you gain on {prompt.targetPlan}:
          </div>

          <ul className="space-y-2.5">
            {prompt.highlights.map((highlight, index) => (
              <li
                key={index}
                className="flex items-start gap-3 text-xs font-semibold text-slate-700"
              >
                <div className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <Check className="h-3 w-3 stroke-[3]" />
                </div>
                <span>{highlight}</span>
              </li>
            ))}
          </ul>
        </div>

        <Separator />

        {/* Footer with App Standard Button */}
        <div className="flex flex-col items-center justify-between gap-3 bg-background p-6">
          <Button
            onClick={handleUpgrade}
            className="group h-11 w-full rounded-2xl font-bold transition-all duration-200"
          >
            <span>{prompt.cta}</span>
            <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
          </Button>

          <div className="flex items-center justify-center gap-1.5 text-[11px] text-muted-foreground font-medium">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
            <span>Instant access • Cancel anytime</span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

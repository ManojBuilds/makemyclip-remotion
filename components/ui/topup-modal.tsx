"use client"

import React, { useState } from "react"
import { Loader2, ShieldCheck } from "lucide-react"
import { toast } from "sonner"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { useDashboardUser } from "@/components/dashboard-context"

const DODO_PRODUCT_STARTER =
  process.env.NEXT_PUBLIC_DODO_PRODUCT_STARTER || "pdt_0NeANLYHzcSM9kxNMXr1h"
const DODO_PRODUCT_GROWTH =
  process.env.NEXT_PUBLIC_DODO_PRODUCT_GROWTH || "pdt_0NeANjqG7wNUSJlRNpSJ8"

const CREDIT_PACKS = [
  {
    id: DODO_PRODUCT_STARTER,
    name: "100 Minutes",
    price: "$6",
    unitPrice: "$0.06 / min",
    credits: "100 video processing credits",
  },
  {
    id: DODO_PRODUCT_GROWTH,
    name: "250 Minutes",
    price: "$12",
    unitPrice: "$0.048 / min",
    credits: "250 video processing credits",
    bestValue: true,
    discountBadge: "Save 20%",
  },
]

interface TopUpModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function TopUpModal({ open, onOpenChange }: TopUpModalProps) {
  const { user: me } = useDashboardUser()
  const userPlan = (me?.plan || "free").trim().toLowerCase()
  const [loading, setLoading] = useState<string | null>(null)

  const handleBuyPack = async (productId: string, packName: string) => {
    setLoading(packName)
    try {
      const res = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ productId }),
      })
      const data = await res.json()
      if (data.url) {
        window.location.href = data.url
      } else {
        toast.error("Error creating checkout session")
      }
    } catch (err) {
      console.error(err)
      toast.error("Something went wrong")
    } finally {
      setLoading(null)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="gap-0 overflow-hidden rounded-3xl bg-background p-0 shadow-2xl sm:max-w-[480px]">
        {/* Header */}
        <DialogHeader className="p-6 text-left border-b border-border/50">
          <DialogTitle className="text-xl font-bold tracking-tight text-foreground">
            Top Up Minutes
          </DialogTitle>
          <DialogDescription className="mt-1 text-xs font-medium text-muted-foreground">
            1 credit = 1 minute of video. Add extra processing minutes anytime.
          </DialogDescription>
        </DialogHeader>

        {/* Packs list */}
        <div className="p-6 space-y-3.5 bg-muted/20">
          {CREDIT_PACKS.map((pack) => {
            const isLoading = loading === pack.name
            return (
              <div
                key={pack.name}
                className={`relative flex items-center justify-between rounded-2xl border p-4 bg-background transition-all ${
                  pack.bestValue
                    ? "border-primary shadow-md ring-1 ring-primary/20"
                    : "border-border shadow-sm"
                }`}
              >
                {pack.bestValue && (
                  <div className="absolute -top-2.5 right-4 flex items-center gap-1 rounded-full bg-primary px-2.5 py-0.5 text-[10px] font-bold text-primary-foreground shadow-sm">
                    <span>{pack.discountBadge}</span>
                    <span>•</span>
                    <span>Best Value</span>
                  </div>
                )}

                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-bold text-foreground">{pack.name}</h4>
                    <span className="text-[10px] font-semibold text-primary/90 bg-primary/10 px-2 py-0.5 rounded-full">
                      {pack.unitPrice}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">{pack.credits}</p>
                  <div className="mt-1 text-lg font-extrabold text-foreground">{pack.price}</div>
                </div>

                <Button
                  size="sm"
                  variant={pack.bestValue ? "default" : "outline"}
                  className="rounded-full px-5 text-xs font-bold shrink-0"
                  onClick={() => handleBuyPack(pack.id, pack.name)}
                  disabled={!!loading}
                >
                  {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Buy Pack"}
                </Button>
              </div>
            )
          })}
        </div>

        {/* Upgrade Call to Action if not on Power plan */}
        {userPlan !== "power" && (
          <div className="mx-6 mb-4 p-3.5 rounded-2xl border border-border bg-background flex items-center justify-between gap-3 text-left">
            <div>
              <h4 className="text-xs font-bold text-foreground">Need recurring monthly minutes?</h4>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                Monthly plans offer the lowest rate per minute.
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="rounded-full px-3.5 py-1 text-[11px] font-bold shrink-0"
              onClick={() => {
                onOpenChange(false)
                window.location.href = "/pricing"
              }}
            >
              See Plans
            </Button>
          </div>
        )}

        {/* Footer info */}
        <div className="flex items-center justify-center gap-1.5 p-4 bg-background border-t border-border text-xs text-muted-foreground font-medium">
          <ShieldCheck className="h-4 w-4 text-emerald-600 flex-shrink-0" />
          <span>Credits never expire & roll over indefinitely.</span>
        </div>
      </DialogContent>
    </Dialog>
  )
}

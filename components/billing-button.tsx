"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { createCustomerPortalSession } from "@/lib/actions/billing"
import { Loader2, CreditCard } from "lucide-react"
import { toast } from "sonner"

export function BillingButton({
  variant = "default",
  className = "",
}: {
  variant?: "default" | "outline" | "ghost" | "secondary"
  className?: string
}) {
  const [isLoading, setIsLoading] = useState(false)

  const handleBilling = async () => {
    setIsLoading(true)
    try {
      const result = await createCustomerPortalSession()
      if (result.url) {
        window.location.href = result.url
      }
    } catch (error: unknown) {
      console.error(error)
      const message =
        error instanceof Error ? error.message : "Failed to open billing portal"
      toast.error(message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Button
      variant={variant}
      className={className}
      onClick={handleBilling}
      disabled={isLoading}
    >
      {isLoading ? (
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
      ) : (
        <CreditCard className="mr-2 h-4 w-4" />
      )}
      Manage Billing
    </Button>
  )
}

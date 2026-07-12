"use client"

import { Loader2 } from "lucide-react"
import { BillingButton } from "@/components/billing-button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useDashboardUser } from "@/components/dashboard-context"

export default function SettingsPage() {
  const { user, status } = useDashboardUser()

  if (status !== "authenticated" || !user) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="container mx-auto max-w-4xl space-y-8 py-10">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Manage your account settings and subscription.
        </p>
      </div>

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Profile</CardTitle>
            <CardDescription>Your personal information.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-1">
              <span className="text-sm font-medium">Name</span>
              <span className="text-sm text-muted-foreground">{user.name}</span>
            </div>
            <div className="grid gap-1">
              <span className="text-sm font-medium">Email</span>
              <span className="text-sm text-muted-foreground">
                {user.email}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card id="billing">
          <CardHeader>
            <CardTitle>Subscription & Billing</CardTitle>
            <CardDescription>
              Manage your plan, billing history, and payment methods.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <div className="grid gap-1">
                <span className="text-sm font-medium">Current Plan</span>
                <span className="text-sm text-muted-foreground capitalize">
                  {user.plan || "free"}
                </span>
              </div>
              {user.dodoCustomerId ? (
                <BillingButton variant="outline" />
              ) : (
                <a
                  href="/pricing"
                  className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground ring-offset-background transition-colors hover:bg-primary/90 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50"
                >
                  Upgrade Plan
                </a>
              )}
            </div>
            {user.dodoCustomerId && (
              <p className="text-xs text-muted-foreground">
                You can upgrade, downgrade, or cancel your subscription through
                our secure billing portal.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

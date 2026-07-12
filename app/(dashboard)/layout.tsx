"use client"

import { DashboardHeader } from "@/components/dashboard-header"
import { DashboardProvider } from "@/components/dashboard-context"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <DashboardProvider>
      <div className="min-h-screen bg-background font-sans">
        <DashboardHeader />
        <main className="container mx-auto max-w-7xl px-4 py-8">
          {children}
        </main>
      </div>
    </DashboardProvider>
  )
}

import { MarketingHeader } from "@/components/marketing-header"
import { MarketingFooter } from "@/components/marketing-footer"

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex min-h-screen flex-col overflow-x-hidden bg-[#FAFAFA] font-sans text-slate-900 selection:bg-blue-100 selection:text-blue-900">
      <MarketingHeader />
      <main className="relative z-10 w-full flex-1">{children}</main>
      <MarketingFooter />
    </div>
  )
}

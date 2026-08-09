import type { Metadata } from "next"
import Link from "next/link"
import { ArrowLeft } from "lucide-react"

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "Privacy Policy for Kivio AI video clipping service.",
}

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-[#f6f5f4] text-slate-800 antialiased py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        {/* Minimal top back button */}
        <div className="mb-8">
          <Link
            href="/"
            className="inline-flex items-center text-sm font-medium text-slate-500 hover:text-slate-900 transition-colors gap-1.5"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Kivio
          </Link>
        </div>

        {/* Content Container */}
        <main className="p-6 sm:p-10">
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
            Privacy Policy
          </h1>
          <p className="mt-2 text-sm text-slate-500 border-b border-slate-100 pb-6">
            Last updated: July 31, 2026
          </p>

          <div className="mt-6 space-y-6 text-sm sm:text-base leading-relaxed text-slate-600">
            <section>
              <h2 className="text-lg font-semibold text-slate-900 mb-2">
                1. Overview
              </h2>
              <p>
                Kivio (&quot;we&quot;, &quot;our&quot;, or &quot;us&quot;) respects your privacy and is committed to protecting your personal data. This Privacy Policy explains how we collect, use, store, and safeguard your information when you use our AI video clipping and editing platform.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-slate-900 mb-2">
                2. Information We Collect
              </h2>
              <p className="mb-2">
                We collect information necessary to provide and improve our service, including:
              </p>
              <ul className="list-disc pl-5 space-y-1">
                <li>
                  <strong className="text-slate-800">Account Data:</strong> Email address, name, and login credentials provided during sign-up.
                </li>
                <li>
                  <strong className="text-slate-800">Media Content:</strong> Videos, audio tracks, transcriptions, and assets uploaded to generate video clips.
                </li>
                <li>
                  <strong className="text-slate-800">Usage & Diagnostics:</strong> Log files, browser type, device information, and interaction data to ensure platform stability.
                </li>
              </ul>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-slate-900 mb-2">
                3. How We Use Your Data
              </h2>
              <ul className="list-disc pl-5 space-y-1">
                <li>To generate, process, reframe, and caption your video clips using our AI algorithms.</li>
                <li>To manage your account, billing, and subscription preferences.</li>
                <li>To maintain, troubleshoot, and enhance our services.</li>
                <li>To send important product notifications and updates.</li>
              </ul>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-slate-900 mb-2">
                4. Data Storage & Sharing
              </h2>
              <p>
                We do not sell your personal data or uploaded media content. We share data only with third-party service providers (such as cloud hosting and infrastructure partners) strictly necessary to operate Kivio and render your videos.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-slate-900 mb-2">
                5. Data Security & Retention
              </h2>
              <p>
                We employ standard security practices to protect your data. Your uploaded media files and rendered clips are retained only as long as needed to fulfill our services or until you delete them from your account.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-slate-900 mb-2">
                6. Your Rights & Choices
              </h2>
              <p>
                You have the right to access, update, or request deletion of your account and personal data at any time. To exercise these rights, please contact our support team.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-slate-900 mb-2">
                7. Contact Us
              </h2>
              <p>
                If you have any questions or concerns regarding this Privacy Policy, please reach out to us at{" "}
                <a href="mailto:support@kivio.pro" className="text-blue-600 underline hover:text-blue-800">
                  support@kivio.pro
                </a>.
              </p>
            </section>
          </div>
        </main>

        <div className="mt-8 text-center text-xs text-slate-400">
          © {new Date().getFullYear()} Kivio. All rights reserved.
        </div>
      </div>
    </div>
  )
}

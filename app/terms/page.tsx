import type { Metadata } from "next"
import Link from "next/link"
import { ArrowLeft } from "lucide-react"

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "Terms of Service for Kivio AI video clipping service.",
}

export default function TermsPage() {
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
            Terms of Service
          </h1>
          <p className="mt-2 text-sm text-slate-500 border-b border-slate-100 pb-6">
            Last updated: July 31, 2026
          </p>

          <div className="mt-6 space-y-6 text-sm sm:text-base leading-relaxed text-slate-600">
            <section>
              <h2 className="text-lg font-semibold text-slate-900 mb-2">
                1. Acceptance of Terms
              </h2>
              <p>
                By creating an account, accessing, or using Kivio (&quot;the Service&quot;), you agree to be bound by these Terms of Service. If you do not agree to these terms, please do not access or use the Service.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-slate-900 mb-2">
                2. Description of Service
              </h2>
              <p>
                Kivio provides AI-powered video editing tools, including automatic clipping, reframing, captioning, and social media video export services.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-slate-900 mb-2">
                3. User Accounts & Responsibilities
              </h2>
              <ul className="list-disc pl-5 space-y-1">
                <li>You must be at least 13 years old (or the applicable legal age in your jurisdiction) to use Kivio.</li>
                <li>You are responsible for keeping your login credentials confidential.</li>
                <li>You are solely responsible for all activities and content uploaded under your account.</li>
              </ul>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-slate-900 mb-2">
                4. Content Ownership & License
              </h2>
              <p className="mb-2">
                <strong className="text-slate-800">Your Content:</strong> You retain full ownership of all video and audio files you upload to Kivio.
              </p>
              <p>
                <strong className="text-slate-800">Service License:</strong> You grant Kivio a limited, non-exclusive license to process, render, store, and host your content solely for the purpose of delivering the service to you.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-slate-900 mb-2">
                5. Prohibited Conduct
              </h2>
              <p className="mb-2">You agree not to upload, create, or distribute any content that:</p>
              <ul className="list-disc pl-5 space-y-1">
                <li>Infringes on copyright, trademark, or intellectual property rights of others.</li>
                <li>Contains illegal, harmful, harassing, or defamatory materials.</li>
                <li>Attempts to reverse engineer, abuse, or disrupt the Service infrastructure.</li>
              </ul>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-slate-900 mb-2">
                6. Disclaimer & Limitation of Liability
              </h2>
              <p>
                Kivio is provided on an &quot;AS IS&quot; and &quot;AS AVAILABLE&quot; basis without warranties of any kind. To the fullest extent permitted by law, Kivio shall not be liable for any indirect, incidental, special, or consequential damages resulting from your use of the Service.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-slate-900 mb-2">
                7. Changes to Terms
              </h2>
              <p>
                We reserve the right to modify or replace these terms at any time. Continued use of Kivio after any changes constitutes acceptance of the new terms.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-slate-900 mb-2">
                8. Contact Us
              </h2>
              <p>
                If you have questions regarding these Terms, please contact us at{" "}
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

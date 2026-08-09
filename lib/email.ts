import { Resend } from "resend"

const resend = new Resend(process.env.RESEND_API_KEY)

interface SendClipsReadyEmailParams {
  toEmail: string
  userName?: string
  projectTitle: string
  projectId: string
  clipCount: number
}

export async function sendClipsReadyEmail({
  toEmail,
  userName,
  projectTitle,
  projectId,
  clipCount,
}: SendClipsReadyEmailParams) {
  if (!process.env.RESEND_API_KEY) {
    console.warn(
      "[sendClipsReadyEmail] RESEND_API_KEY is not configured. Skipping email notification."
    )
    return
  }

  const baseUrl =
    process.env.NEXT_PUBLIC_APP_URL ||
    (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "https://makemyclip.com")
  const projectUrl = `${baseUrl}/project/${projectId}`
  const fromEmail =
    process.env.RESEND_FROM_EMAIL || "MakeMyClip <notifications@makemyclip.com>"

  const subject = `Your clips are ready!`

  const html = `
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px 24px; color: #0f172a; background-color: #ffffff;">
      <h2 style="font-size: 20px; font-weight: 700; tracking: -0.02em; margin-top: 0; margin-bottom: 12px; color: #0f172a;">Your clips are ready to view 🎬</h2>
      <p style="font-size: 14px; line-height: 1.5; color: #475569; margin-bottom: 24px;">
        Hi ${userName || "there"},<br/><br/>
        We've finished processing and captioning <strong>${clipCount} clip${clipCount === 1 ? "" : "s"}</strong> from your video <strong>"${projectTitle}"</strong>.
      </p>
      <div style="margin-bottom: 28px;">
        <a href="${projectUrl}" style="background-color: #2563eb; color: #ffffff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px; display: inline-block;">
          View Clips →
        </a>
      </div>
      <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
      <p style="font-size: 12px; color: #94a3b8; margin: 0;">
        Kivio.pro — AI Video Highlights & Captions
      </p>
    </div>
  `

  try {
    const data = await resend.emails.send({
      from: fromEmail,
      to: [toEmail],
      subject,
      html,
    })
    console.log(
      `[sendClipsReadyEmail] Email sent successfully to ${toEmail}. Message ID:`,
      data.data?.id
    )
    return data
  } catch (error) {
    console.error("[sendClipsReadyEmail] Error sending email via Resend:", error)
  }
}

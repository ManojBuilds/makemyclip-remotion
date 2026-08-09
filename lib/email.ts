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
    (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "https://kivio.pro")
  const projectUrl = `${baseUrl}/projects/${projectId}`
  const fromEmail =
    process.env.RESEND_FROM_EMAIL || "Kivio.pro <notifications@mailer.kivio.pro>"

  const subject = `Your clips are ready! 🚀`

  const html = `
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 40px 32px; color: #0f172a; background-color: #ffffff;">
      <!-- Logo / Header -->
      <div style="margin-bottom: 32px;">
        <span style="font-size: 24px; font-weight: 800; color: #4f46e5; letter-spacing: -0.02em;">Kivio<span style="color: #0f172a;">.pro</span></span>
      </div>

      <h1 style="font-size: 32px; font-weight: 800; line-height: 1.25; tracking: -0.03em; margin-top: 0; margin-bottom: 24px; color: #0f172a;">
        Your clips are ready. 🚀
      </h1>
      
      <p style="font-size: 16px; line-height: 1.6; color: #334155; margin-top: 0; margin-bottom: 20px;">
        Hi ${userName || "there"},
      </p>
      
      <p style="font-size: 16px; line-height: 1.6; color: #334155; margin-top: 0; margin-bottom: 16px;">
        We’ve analyzed and clipped your video <strong>"${projectTitle}"</strong>.
      </p>
      
      <p style="font-size: 16px; line-height: 1.6; color: #334155; margin-top: 0; margin-bottom: 32px;">
        <strong>${clipCount} high-potential clip${clipCount === 1 ? "" : "s"}</strong> are ready for you to preview and download.
      </p>

      <div style="text-align: center; margin-bottom: 40px;">
        <a href="${projectUrl}" style="background-color: #4f46e5; color: #ffffff; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px; display: inline-block; box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.1), 0 2px 4px -1px rgba(79, 70, 229, 0.06);">
          View My Clips →
        </a>
      </div>

      <!-- Pro-Tip Card -->
      <table cellpadding="0" cellspacing="0" style="width: 100%; background-color: #f5f3ff; border-radius: 12px; margin-bottom: 32px; border-collapse: collapse;">
        <tr>
          <td style="padding: 16px 0 16px 20px; vertical-align: middle; width: 40px;">
            <div style="background-color: #e0e7ff; width: 36px; height: 36px; border-radius: 18px; text-align: center;">
              <span style="font-size: 18px; line-height: 36px; display: inline-block; vertical-align: middle;">💡</span>
            </div>
          </td>
          <td style="padding: 16px 20px; vertical-align: middle; font-size: 14px; line-height: 1.5; color: #475569; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
            <span style="color: #4f46e5; font-weight: 700;">Pro Tip:</span> Share these clips as Reels, Shorts, or TikToks to instantly boost your reach and engagement.
          </td>
        </tr>
      </table>

      <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 32px 0;" />
      
      <p style="font-size: 13px; color: #64748b; margin: 0 0 8px 0; line-height: 1.5;">
        You’re receiving this because you started a project on Kivio.pro.
      </p>
      <p style="font-size: 13px; color: #64748b; margin: 0; line-height: 1.5;">
        &copy; 2026 <a href="${baseUrl}" style="color: #4f46e5; text-decoration: none; font-weight: 500;">Kivio.pro</a>. All rights reserved.
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

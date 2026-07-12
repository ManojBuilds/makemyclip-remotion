import { NextRequest, NextResponse } from "next/server"

export async function GET(req: NextRequest) {
  const url = req.nextUrl.searchParams.get("url")
  const filename = req.nextUrl.searchParams.get("filename") || "clip.mp4"

  if (!url) {
    return new NextResponse("Missing url parameter", { status: 400 })
  }

  try {
    const res = await fetch(url)
    if (!res.ok) {
      return new NextResponse(`Failed to fetch file: ${res.statusText}`, {
        status: res.status,
      })
    }

    const headers = new Headers()
    // Force browser to download as file attachment
    headers.set(
      "Content-Disposition",
      `attachment; filename="${filename.replace(/"/g, '\\"')}"`
    )
    headers.set("Content-Type", res.headers.get("Content-Type") || "video/mp4")

    const contentLength = res.headers.get("Content-Length")
    if (contentLength) {
      headers.set("Content-Length", contentLength)
    }

    // Set Cache-Control to prevent caching if the download URL is dynamic/temporary
    headers.set(
      "Cache-Control",
      "no-store, no-cache, must-revalidate, proxy-revalidate"
    )

    return new Response(res.body, {
      status: 200,
      headers,
    })
  } catch (error) {
    console.error("Download proxy error:", error)
    return new NextResponse("Error during file download", { status: 500 })
  }
}

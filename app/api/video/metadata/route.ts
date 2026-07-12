import { NextResponse } from "next/server"
import { getServerSession } from "@/lib/auth-server"
import { fetchYouTubeMetadata } from "@/lib/youtube"

export async function POST(request: Request) {
  try {
    const session = await getServerSession()
    if (!session) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const { url } = await request.json()
    if (!url || typeof url !== "string") {
      return NextResponse.json({ error: "URL is required" }, { status: 400 })
    }

    const metadata = await fetchYouTubeMetadata(url)
    return NextResponse.json({ success: true, metadata })
  } catch (error) {
    console.error("Error fetching YouTube metadata:", error)
    const message =
      error instanceof Error ? error.message : "Failed to fetch metadata"
    return NextResponse.json(
      { success: false, error: message },
      { status: 400 }
    )
  }
}

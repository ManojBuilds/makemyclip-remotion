import { NextResponse } from "next/server"
import { getServerSession } from "@/lib/auth-server"
import { getOrCreateUser } from "@/lib/user"

export const dynamic = "force-dynamic"

export async function GET() {
  try {
    const session = await getServerSession()
    if (!session || !session.user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const dbUser = await getOrCreateUser({
      id: session.user.id,
      email: session.user.email,
      name: session.user.name,
    })

    return NextResponse.json(dbUser)
  } catch (error) {
    console.error("Error in /api/user/me:", error)
    return NextResponse.json(
      { error: "Internal Server Error" },
      { status: 500 }
    )
  }
}

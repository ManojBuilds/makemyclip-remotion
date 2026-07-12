import { NextResponse } from "next/server"
import { getServerSession } from "@/lib/auth-server"
import { db } from "@/lib/db"
import { user } from "@/lib/db/schema"
import { eq } from "drizzle-orm"

export async function GET() {
  try {
    const session = await getServerSession()
    if (!session) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const [dbUser] = await db
      .select()
      .from(user)
      .where(eq(user.id, session.user.id))

    if (!dbUser) {
      return NextResponse.json({ error: "User not found" }, { status: 404 })
    }

    return NextResponse.json({
      user: {
        id: dbUser.id,
        name: dbUser.name,
        email: dbUser.email,
        plan: dbUser.plan ?? "free",
        credits: dbUser.credits ?? 0,
        dodoCustomerId: dbUser.dodoCustomerId ?? null,
        subscriptionStatus: dbUser.subscriptionStatus ?? "inactive",
      },
    })
  } catch (error) {
    console.error("Failed to load current user:", error)
    return NextResponse.json(
      { error: "Failed to load current user" },
      { status: 500 }
    )
  }
}

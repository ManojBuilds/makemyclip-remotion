"use server"

import { getServerSession } from "@/lib/auth-server"
import { dodo } from "@/lib/dodo"
import { db } from "@/lib/db"
import { user } from "@/lib/db/schema"
import { eq } from "drizzle-orm"
import { redirect } from "next/navigation"

export async function createCustomerPortalSession() {
  const session = await getServerSession()

  if (!session || !session.user) {
    throw new Error("Unauthorized")
  }

  const [dbUser] = await db
    .select()
    .from(user)
    .where(eq(user.id, session.user.id))

  const dodoCustomerId = dbUser?.dodoCustomerId

  if (!dodoCustomerId) {
    // If no customer ID, they probably haven't subscribed yet.
    throw new Error("No customer ID found. Please subscribe to a plan first.")
  }

  try {
    const portalSession = await dodo.customers.customerPortal.create(
      dodoCustomerId,
      {
        return_url: `${process.env.NEXT_PUBLIC_APP_URL}/projects`,
      }
    )

    if (portalSession.link) {
      return { url: portalSession.link }
    } else {
      throw new Error("Failed to create customer portal session")
    }
  } catch (error: unknown) {
    console.error("Error creating customer portal session:", error)
    const message =
      error instanceof Error ? error.message : "Internal server error"
    throw new Error(message)
  }
}

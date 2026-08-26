import { db } from "@/lib/db"
import { user } from "@/lib/db/schema"
import { eq } from "drizzle-orm"
import { PLAN_LIMITS } from "@/lib/config"

export interface ClerkUserSession {
  id: string
  email: string
  name: string
  image?: string | null
}

/**
 * Retrieves a user from the PostgreSQL database using their Clerk User ID.
 * If the user does not exist in the database, automatically inserts a new record
 * with 45 initial credits and plan set to "free".
 */
export async function getOrCreateUser(clerkUser: ClerkUserSession) {
  if (!clerkUser?.id) {
    throw new Error("Invalid Clerk user session")
  }

  // 1. Try to find the user in the database
  const [existingUser] = await db
    .select()
    .from(user)
    .where(eq(user.id, clerkUser.id))

  if (existingUser) {
    return existingUser
  }

  // 2. If the user doesn't exist, insert them
  const newUserData = {
    id: clerkUser.id,
    name: clerkUser.name || "User",
    email: clerkUser.email,
    emailVerified: true,
    image: clerkUser.image || null,
    credits: PLAN_LIMITS.free.monthlyProcessingMinutes, // 45 initial credits on sign up
    plan: "free",
    subscriptionStatus: "inactive",
    createdAt: new Date(),
    updatedAt: new Date(),
  }

  try {
    const [insertedUser] = await db
      .insert(user)
      .values(newUserData)
      .returning()

    console.log(`Successfully synced and created user in database: ${clerkUser.email}`)
    return insertedUser
  } catch (error) {
    console.error("Error creating user in database:", error)
    // In case of a race condition where the Clerk webhook inserted the user concurrently:
    const [retryUser] = await db
      .select()
      .from(user)
      .where(eq(user.id, clerkUser.id))
    
    if (retryUser) {
      return retryUser
    }
    throw error
  }
}

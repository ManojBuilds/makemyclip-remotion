import { auth, currentUser } from "@clerk/nextjs/server"

/**
 * Get the current authenticated user from the request headers/cookies.
 * Returns null if not authenticated.
 */
export async function getServerSession() {
  const { userId } = await auth()
  if (!userId) return null

  const user = await currentUser()

  return {
    user: {
      id: userId,
      email: user?.emailAddresses[0]?.emailAddress || "",
      name: `${user?.firstName || ""} ${user?.lastName || ""}`.trim() || "User",
    },
  }
}

/**
 * Get the current authenticated user, throwing if not authenticated.
 */
export async function requireAuth() {
  const session = await getServerSession()
  if (!session) {
    throw new Error("Unauthorized")
  }
  return session
}

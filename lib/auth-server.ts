import { headers } from "next/headers"
import { auth } from "@/lib/auth"

/**
 * Get the current authenticated user from the request headers.
 * Returns null if not authenticated.
 */
export async function getServerSession() {
  const session = await auth.api.getSession({
    headers: await headers(),
  })
  return session
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

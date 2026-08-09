import { Webhook } from "svix"
import { headers } from "next/headers"
import { WebhookEvent } from "@clerk/nextjs/server"
import { db } from "@/lib/db"
import { user } from "@/lib/db/schema"
import { eq } from "drizzle-orm"

export async function POST(req: Request) {
  const SIGNING_SECRET = process.env.CLERK_WEBHOOK_SECRET

  if (!SIGNING_SECRET) {
    throw new Error('Error: Please add CLERK_WEBHOOK_SECRET from Clerk Dashboard to .env or .env.local')
  }

  // Create new Svix instance with secret
  const wh = new Webhook(SIGNING_SECRET)

  // Get headers
  const headerPayload = await headers()
  const svix_id = headerPayload.get('svix-id')
  const svix_timestamp = headerPayload.get('svix-timestamp')
  const svix_signature = headerPayload.get('svix-signature')

  // If there are no headers, error out
  if (!svix_id || !svix_timestamp || !svix_signature) {
    return new Response('Error: Missing Svix headers', {
      status: 400,
    })
  }

  // Get body
  const payload = await req.json()
  const body = JSON.stringify(payload)

  let evt: WebhookEvent

  // Verify payload with headers
  try {
    evt = wh.verify(body, {
      'svix-id': svix_id,
      'svix-timestamp': svix_timestamp,
      'svix-signature': svix_signature,
    }) as WebhookEvent
  } catch (err) {
    console.error('Error: Could not verify webhook:', err)
    return new Response('Error: Verification error', {
      status: 400,
    })
  }

  const eventType = evt.type

  if (eventType === 'user.created') {
    const { id, email_addresses, first_name, last_name, image_url } = evt.data
    const email = email_addresses?.[0]?.email_address

    if (!email) {
      return new Response('Error: No email address provided', { status: 400 })
    }

    const name = `${first_name || ''} ${last_name || ''}`.trim() || 'User'

    try {
      await db.insert(user).values({
        id: id,
        name: name,
        email: email,
        emailVerified: true,
        image: image_url || null,
        credits: 30, // Default signup credits
        plan: 'free',
        subscriptionStatus: 'inactive',
      })
      return new Response('User synced successfully', { status: 200 })
    } catch (err) {
      console.error('Error inserting user to database:', err)
      return new Response('Database insertion error', { status: 500 })
    }
  }

  if (eventType === 'user.updated') {
    const { id, first_name, last_name, image_url } = evt.data
    const name = `${first_name || ''} ${last_name || ''}`.trim() || 'User'

    try {
      await db.update(user)
        .set({
          name: name,
          image: image_url || null,
          updatedAt: new Date(),
        })
        .where(eq(user.id, id))
      return new Response('User updated successfully', { status: 200 })
    } catch (err) {
      console.error('Error updating user in database:', err)
      return new Response('Database update error', { status: 500 })
    }
  }

  if (eventType === 'user.deleted') {
    const { id } = evt.data
    if (id) {
      try {
        await db.delete(user).where(eq(user.id, id))
        return new Response('User deleted successfully', { status: 200 })
      } catch (err) {
        console.error('Error deleting user from database:', err)
        return new Response('Database deletion error', { status: 500 })
      }
    }
  }

  return new Response('Webhook received', { status: 200 })
}

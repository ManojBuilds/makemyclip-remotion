import { NextResponse } from "next/server"
import { dodo } from "@/lib/dodo"
import { db } from "@/lib/db"
import { user } from "@/lib/db/schema"
import { eq } from "drizzle-orm"
import { trackServerPaymentCompleted } from "@/lib/posthog-server"

interface DodoCustomer {
  customer_id: string
  email: string
}

interface DodoSubscriptionData {
  customer?: DodoCustomer
  status: string
  product_id: string
  price_cents?: number
}

interface DodoCreditData {
  customer_id: string
  balance_after?: string
  available_balance?: string
  customer?: DodoCustomer
}

export async function POST(req: Request) {
  try {
    const body = await req.text()
    const headers = {
      "webhook-id": req.headers.get("webhook-id") || "",
      "webhook-signature": req.headers.get("webhook-signature") || "",
      "webhook-timestamp": req.headers.get("webhook-timestamp") || "",
    }

    if (!process.env.DODO_PAYMENTS_WEBHOOK_KEY) {
      console.error("DODO_PAYMENTS_WEBHOOK_KEY is not set")
      return NextResponse.json(
        { error: "Configuration error" },
        { status: 500 }
      )
    }

    let event
    try {
      // Use the Dodo SDK to verify and unwrap the webhook
      event = dodo.webhooks.unwrap(body, {
        headers,
        // The SDK uses the webhookKey from initialization if available
      })
    } catch (err) {
      console.error("Webhook verification failed:", err)
      return NextResponse.json({ error: "Invalid signature" }, { status: 401 })
    }

    const { type, data } = event

    console.log(`Processing Dodo webhook: ${type}`)
    console.log(`Full event data:`, JSON.stringify(data, null, 2))

    switch (type) {
      case "subscription.active":
      case "subscription.renewed":
      case "subscription.updated":
      case "subscription.plan_changed": {
        const subData = data as unknown as DodoSubscriptionData
        const customerId = subData.customer?.customer_id
        const status = subData.status // active, cancelled, on_hold, etc.
        const userEmail = subData.customer?.email
        const productId = subData.product_id

        const creatorProductId =
          process.env.NEXT_PUBLIC_DODO_PRODUCT_CREATOR ||
          "pdt_0NeAL7ABiEx4ZLymAhpQq"
        const powerProductId =
          process.env.NEXT_PUBLIC_DODO_PRODUCT_POWER ||
          "pdt_0NeANzWl0m2Mn1lFOW5yD"
        const proProductId =
          process.env.NEXT_PUBLIC_DODO_PRODUCT_PRO || "pdt_pro"

        const planMapping: Record<string, string> = {
          [creatorProductId]: "creator",
          [powerProductId]: "power",
          [proProductId]: "power", // Fallback for safety
        }

        const plan = planMapping[productId] || "free"

        if (userEmail) {
          const [updatedUser] = await db
            .update(user)
            .set({
              dodoCustomerId: customerId,
              subscriptionStatus: status,
              plan: status === "active" ? plan : "free",
              updatedAt: new Date(),
            })
            .where(eq(user.email, userEmail))
            .returning()

          if (status === "active" && updatedUser?.id) {
            await trackServerPaymentCompleted({
              distinctId: updatedUser.id,
              planId: plan,
              amountCents: subData.price_cents || 0,
              customerId,
            })
          }
        }
        break
      }

      case "subscription.cancelled":
      case "subscription.expired": {
        const subData = data as unknown as DodoSubscriptionData
        const userEmail = subData.customer?.email

        if (userEmail) {
          await db
            .update(user)
            .set({
              subscriptionStatus: "inactive",
              plan: "free",
              updatedAt: new Date(),
            })
            .where(eq(user.email, userEmail))
        }
        break
      }

      case "credit.added":
      case "credit.deducted":
      case "credit.manual_adjustment":
      case "credit.rolled_over": {
        const creditData = data as unknown as DodoCreditData
        const customerId = creditData.customer_id
        const balance = parseInt(
          creditData.balance_after || creditData.available_balance || "0"
        )
        let userEmail = creditData.customer?.email

        // credit events don't always include the customer object.
        // If this arrives before subscription.active, we won't match by dodoCustomerId.
        // Fetch the email to guarantee the fallback works.
        if (!userEmail && customerId) {
          try {
            const customer = await dodo.customers.retrieve(customerId)
            userEmail = customer.email
          } catch (e) {
            console.error("Failed to fetch customer for credit event:", e)
          }
        }

        const updateData: {
          credits: number
          updatedAt: Date
          dodoCustomerId?: string
        } = {
          credits: balance,
          updatedAt: new Date(),
        }
        if (customerId) updateData.dodoCustomerId = customerId

        // Try update by customerId
        let result = await db
          .update(user)
          .set(updateData)
          .where(eq(user.dodoCustomerId, customerId))
          .returning()

        // Fallback to email for initial purchase (if events arrive out of order)
        if (result.length === 0 && userEmail) {
          result = await db
            .update(user)
            .set(updateData)
            .where(eq(user.email, userEmail))
            .returning()
        }
        break
      }

      default:
        console.log(`Unhandled webhook type: ${type}`)
    }

    return NextResponse.json({ received: true })
  } catch (error: unknown) {
    console.error("Dodo webhook error:", error)
    const message =
      error instanceof Error ? error.message : "Internal Server Error"
    return NextResponse.json({ error: message }, { status: 500 })
  }
}

import { NextResponse } from "next/server"
import { getServerSession } from "@/lib/auth-server"
import { dodo } from "@/lib/dodo"

export async function POST(req: Request) {
  try {
    const session = await getServerSession()
    if (!session || !session.user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const { productId } = await req.json()

    if (!productId) {
      return NextResponse.json(
        { error: "productId is required" },
        { status: 400 }
      )
    }

    // Create a checkout session
    const checkoutSession = await dodo.checkoutSessions.create({
      product_cart: [
        {
          product_id: productId,
          quantity: 1,
        },
      ],
      customer: {
        email: session.user.email,
        name: session.user.name || "",
      },
      return_url: `${process.env.NEXT_PUBLIC_APP_URL}/projects`,
      // You can also add metadata here
    })

    return NextResponse.json({ url: checkoutSession.checkout_url })
  } catch (err: unknown) {
    console.error("Checkout error:", err)
    const message = err instanceof Error ? err.message : "Internal server error"
    return NextResponse.json({ error: message }, { status: 500 })
  }
}

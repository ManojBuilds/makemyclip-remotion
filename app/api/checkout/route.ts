import { NextResponse } from "next/server"
import { auth, currentUser } from "@clerk/nextjs/server"
import { getServerSession } from "@/lib/auth-server"
import { dodo } from "@/lib/dodo"

export async function POST(req: Request) {
  console.log("========== [CHECKOUT API DEBUG] START ==========")
  try {
    const rawCookies = req.headers.get("cookie")
    const authHeader = req.headers.get("authorization")
    const origin = req.headers.get("origin")
    const referer = req.headers.get("referer")

    console.log("[CHECKOUT_DEBUG] Request Headers:", {
      origin,
      referer,
      hasAuthHeader: !!authHeader,
      hasCookies: !!rawCookies,
      cookieNames: rawCookies
        ? rawCookies
            .split(";")
            .map((c) => c.trim().split("=")[0])
        : [],
    })

    // Direct Clerk auth inspection
    const clerkAuth = await auth()
    console.log("[CHECKOUT_DEBUG] Clerk auth() result:", {
      userId: clerkAuth.userId,
      sessionId: clerkAuth.sessionId,
      orgId: clerkAuth.orgId,
      isAuthenticated: !!clerkAuth.userId,
    })

    // Clerk currentUser inspection
    let clerkUser = null
    try {
      clerkUser = await currentUser()
      console.log("[CHECKOUT_DEBUG] Clerk currentUser():", {
        id: clerkUser?.id,
        email: clerkUser?.emailAddresses?.[0]?.emailAddress,
        firstName: clerkUser?.firstName,
        lastName: clerkUser?.lastName,
      })
    } catch (userErr) {
      console.warn("[CHECKOUT_DEBUG] Error calling currentUser():", userErr)
    }

    // getServerSession inspection
    const session = await getServerSession()
    console.log("[CHECKOUT_DEBUG] getServerSession() result:", session)

    if (!session || !session.user || !session.user.id) {
      console.warn("[CHECKOUT_DEBUG] Auth check failed! Returning 401. Reason:", {
        hasSession: !!session,
        hasUser: !!session?.user,
        userId: session?.user?.id || null,
        clerkUserId: clerkAuth.userId || null,
      })
      console.log("========== [CHECKOUT API DEBUG] END (401) ==========")
      return NextResponse.json(
        {
          error: "Please sign in to complete your purchase.",
          debug: {
            authenticated: false,
            clerkUserId: clerkAuth.userId || null,
            reason: !clerkAuth.userId
              ? "No active Clerk session or auth token found in request cookies/headers"
              : "User profile could not be loaded",
          },
        },
        { status: 401 }
      )
    }

    const body = await req.json().catch((e) => {
      console.error("[CHECKOUT_DEBUG] Failed to parse JSON body:", e)
      return {}
    })
    const { productId } = body

    console.log("[CHECKOUT_DEBUG] Request Body:", { productId, userEmail: session.user.email })

    if (!productId) {
      console.warn("[CHECKOUT_DEBUG] Missing productId. Returning 400.")
      console.log("========== [CHECKOUT API DEBUG] END (400) ==========")
      return NextResponse.json(
        { error: "productId is required" },
        { status: 400 }
      )
    }

    const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000"
    const hasDodoKey = !!process.env.DODO_PAYMENTS_API_KEY
    const dodoEnv =
      process.env.DODO_PAYMENTS_ENVIRONMENT ||
      (process.env.NODE_ENV === "production" ? "live_mode" : "test_mode")

    console.log("[CHECKOUT_DEBUG] Dodo Client Configuration:", {
      hasDodoKey,
      dodoKeyPrefix: process.env.DODO_PAYMENTS_API_KEY
        ? `${process.env.DODO_PAYMENTS_API_KEY.slice(0, 7)}...`
        : "MISSING",
      dodoEnv,
      nodeEnv: process.env.NODE_ENV,
    })

    console.log("[CHECKOUT_DEBUG] Creating Dodo checkout session with:", {
      productId,
      customerEmail: session.user.email,
      customerName: session.user.name || "User",
      returnUrl: `${appUrl}/projects`,
    })

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
        name: session.user.name || "User",
      },
      return_url: `${appUrl}/projects`,
    })

    console.log("[CHECKOUT_DEBUG] Dodo checkout session created successfully:", {
      checkout_url: checkoutSession?.checkout_url,
      session_id: checkoutSession?.session_id,
    })
    console.log("========== [CHECKOUT API DEBUG] END (200) ==========")

    return NextResponse.json({ url: checkoutSession.checkout_url })
  } catch (err: unknown) {
    console.error("========== [CHECKOUT API DEBUG] ERROR ==========")
    console.error("Dodo Payments / Checkout error:", err)
    const message = err instanceof Error ? err.message : "Internal server error"
    return NextResponse.json(
      {
        error: `Checkout failed: ${message}`,
        details: err instanceof Error ? err.stack : undefined,
      },
      { status: 500 }
    )
  }
}

import { NextRequest, NextResponse } from "next/server"

export function proxy(request: NextRequest) {
  const path = request.nextUrl.pathname

  // Check for the presence of Better Auth session token cookies (standard and secure/production)
  const sessionToken =
    request.cookies.get("better-auth.session_token") ||
    request.cookies.get("__Secure-better-auth.session_token")

  const hasSession = !!sessionToken

  const isDashboardRoute =
    path.startsWith("/projects") || path.startsWith("/settings")
  const isAuthRoute = path.startsWith("/login") || path.startsWith("/signup")

  if (isDashboardRoute && !hasSession) {
    const loginUrl = new URL("/login", request.url)
    // Keep track of the original page to redirect back after successful login
    loginUrl.searchParams.set(
      "callbackUrl",
      request.nextUrl.pathname + request.nextUrl.search
    )
    return NextResponse.redirect(loginUrl)
  }

  if (isAuthRoute && hasSession) {
    // If user is already authenticated, redirect them to dashboard
    return NextResponse.redirect(new URL("/projects", request.url))
  }

  return NextResponse.next()
}

// Limit the middleware to run only on dashboard and authentication pages
export const config = {
  matcher: ["/projects/:path*", "/settings/:path*", "/login", "/signup"],
}

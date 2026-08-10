import { clerkMiddleware } from "@clerk/nextjs/server"

export default clerkMiddleware(async (auth, req) => {
  const { pathname } = req.nextUrl
  const isProtectedRoute =
    pathname.startsWith("/projects") || pathname.startsWith("/settings")

  if (isProtectedRoute) {
    await auth.protect()
  }
})

export const config = {
  matcher: [
    /*
     * Match all request paths except for:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - Media: mp4, webm, m4a, mp3, wav, ogg, mov, avi, flac, mkv
     * - Images: html, css, js, json, jpg, jpeg, webp, png, gif, svg, avif, ico, cur
     * - Fonts: ttf, woff, woff2, otf, eot
     * - Data/Docs/Meta: csv, doc, docx, xls, xlsx, zip, webmanifest, txt, xml, map
     */
    '/((?!_next|[^?]*\\.(?:html?|css|js|json|jpe?g|webp|png|gif|svg|avif|ico|cur|ttf|woff2?|otf|eot|csv|docx?|xlsx?|zip|webmanifest|txt|xml|map|mp4|webm|m4a|mp3|wav|ogg|mov|avi|flac|mkv)).*)',
    '/(api|trpc)(.*)',
    '/__clerk/(.*)',
  ],
}
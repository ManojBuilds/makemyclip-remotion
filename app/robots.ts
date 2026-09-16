import type { MetadataRoute } from "next"

export default function robots(): MetadataRoute.Robots {
  const baseUrl = process.env.NEXT_PUBLIC_APP_URL || "https://kivio.pro"

  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          "/api/",
          "/projects/",
          "/settings/",
          "/dashboard/",
          "/brand-kit/",
          "/sign-in/",
          "/sign-up/",
        ],
      },
      {
        userAgent: "Googlebot",
        allow: "/",
        disallow: [
          "/api/",
          "/projects/",
          "/settings/",
          "/dashboard/",
          "/brand-kit/",
          "/sign-in/",
          "/sign-up/",
        ],
      },
    ],
    sitemap: `${baseUrl}/sitemap.xml`,
    host: baseUrl,
  }
}

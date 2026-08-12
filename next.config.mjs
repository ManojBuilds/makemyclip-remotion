const nextConfig = {
  serverExternalPackages: [
    "@remotion/bundler",
    "@vercel/sandbox",
    "esbuild",
  ],
  transpilePackages: [
    "remotion",
    "@remotion/player",
    "@remotion/vercel",
    "@remotion/google-fonts",
    "@remotion/media-utils",
    "@remotion/captions",
  ],
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.unsplash.com",
      },
      {
        protocol: "https",
        hostname: "i.pravatar.cc",
      },
      {
        protocol: "https",
        hostname: "img.youtube.com",
      },
    ],
  },
  async rewrites() {
    return [
      {
        source: "/ingest/static/:path*",
        destination: "https://us-assets.i.posthog.com/static/:path*",
      },
      {
        source: "/ingest/:path*",
        destination: "https://us.i.posthog.com/:path*",
      },
      {
        source: "/ingest/decide",
        destination: "https://us.i.posthog.com/decide",
      },
    ];
  },
};

export default nextConfig;


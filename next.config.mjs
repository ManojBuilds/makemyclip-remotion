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
};

export default nextConfig;


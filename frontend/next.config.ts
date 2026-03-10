import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    // Allow Amazon product images (used in confirmation grid and product cards)
    remotePatterns: [
      { protocol: "https", hostname: "**.amazon.com" },
      { protocol: "https", hostname: "**.ssl-images-amazon.com" },
      { protocol: "https", hostname: "m.media-amazon.com" },
    ],
  },
};

export default nextConfig;

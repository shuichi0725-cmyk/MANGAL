import type { NextConfig } from "next";

const config: NextConfig = {
  output: "export",
  images: {
    unoptimized: true,
    remotePatterns: [
      { protocol: "https", hostname: "cover.openbd.jp" },
      { protocol: "https", hostname: "m.media-amazon.com" },
      { protocol: "https", hostname: "images-na.ssl-images-amazon.com" },
      { protocol: "https", hostname: "thumbnail.image.rakuten.co.jp" },
    ],
  },
};

export default config;

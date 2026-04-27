import type { NextConfig } from "next";

const config: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "cover.openbd.jp" },
      { protocol: "https", hostname: "m.media-amazon.com" },
      { protocol: "https", hostname: "images-na.ssl-images-amazon.com" },
    ],
  },
};

export default config;

import('@opennextjs/cloudflare').then(m => m.initOpenNextCloudflareForDev());

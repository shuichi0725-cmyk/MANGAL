import type { NextConfig } from "next";

const config: NextConfig = {
  output: "export",
  // ★buildId固定 = 再ビルドしても内容不変ページのハッシュが変わらない(R2差分同期の前提。2026-07-03)
  generateBuildId: async () => "mangal-static",
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

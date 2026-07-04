import type { NextConfig } from "next";

const config: NextConfig = {
  output: "export",
  // ★buildId固定 = 再ビルドしても内容不変ページのハッシュが変わらない(R2差分同期の前提。2026-07-03)
  generateBuildId: async () => "mangal-static",
  // ★静的生成タイムアウト延長(2026-07-05): 既定60sだと重頁(home-design=66k全読込/大巻数頁)が
  //   ワーカー競合時に超過し3回リトライ後にビルド全体をkillする。300sで全頁に余裕を持たせる。
  staticPageGenerationTimeout: 300,
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

import path from "node:path";
import type { NextConfig } from "next";

// ★プレビュー専用の頁(= ファイル名 page.preview.tsx。例: 実験頁 app/lab/magic-shelf)は、
//   プレビュー用データ(MANGAL_DATA_DIR=.preview-data)でビルドする時だけ頁として認める。
//   それ以外(本番)は Next 既定と同じ拡張子だけ = その頁もJSも一切作られない(2026-09-26)。
//   ★頁側で notFound() や generateStaticParams を空にする手は使えない: 前者は404のHTMLとJSが残り、
//     後者は output: export のビルドが落ちる(いずれも実測)。
const isPreviewData =
  !!process.env.MANGAL_DATA_DIR && path.resolve(process.env.MANGAL_DATA_DIR) === path.resolve(".preview-data");

const config: NextConfig = {
  output: "export",
  pageExtensions: isPreviewData ? ["preview.tsx", "tsx", "ts", "jsx", "js"] : ["tsx", "ts", "jsx", "js"],
  // ★共通の頁(作品頁など)に入るプレビュー専用部品の門(例: マイ本棚の「しまう」ボタン)。
  //   本番も "0" を**必ず定義**する = ビルド時の定数になり、`=== "1" ? require(...) : null` の require ごと
  //   webpack が刈り取る → 作品頁の出力(HTML/RSC/JS)は1バイトも変わらない(2026-09-28 実測)。
  //   未定義のままだと定数にならず、部品が本番の頁チャンクに混ざる。
  env: { NEXT_PUBLIC_PREVIEW_FEATURES: isPreviewData ? "1" : "0" },
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

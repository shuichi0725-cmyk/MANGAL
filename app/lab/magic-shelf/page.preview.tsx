import type { Metadata } from "next";
import { preload } from "react-dom";
import { loadMasters } from "@/lib/loadData";
import MagicCompass from "./MagicCompass";
import "./compass.css";

// ★プレビュー専用の実験頁。拡張子 .preview.tsx = next.config.ts の pageExtensions が
//   MANGAL_DATA_DIR=.preview-data の時だけ頁として認める(本番ビルドでは頁もJSも作られない)。
// 非索引(sitemap にも載らない: scripts/_gen-sitemap.py は lab/ を拾わない)。
export const metadata: Metadata = {
  title: "魔法の書架(実験)",
  description: "中央の1冊から、作者・雑誌・年・要素の糸を手繰って次の本へ旅する羅針盤の実験頁。",
  robots: { index: false, follow: false },
};

/** 魔法の書架(/lab/magic-shelf) = 旅路つき羅針盤。依頼書 docs/cloud-briefs/magic-shelf-compass.md。
 *  データは useMangaIndex()(本番の全件索引 /prod-idx/)を端末で逆引きするだけ。見本JSONは持たない。 */
export default function MagicShelfPage() {
  // ★本番の全件索引は大きいので HTML の段階で取り始める。 URL・取得モードは lib/useMangaIndex.ts の
  //   fetch と一致させる(fetch 既定 = mode cors / credentials same-origin ⇔ crossOrigin "anonymous")。
  preload("/prod-idx/manga-list-head.json", { as: "fetch", crossOrigin: "anonymous" });
  preload("/prod-idx/manga-list-cols.v1.json", { as: "fetch", crossOrigin: "anonymous", fetchPriority: "low" });
  preload("/prod-idx/manga-catch-index.json", { as: "fetch", crossOrigin: "anonymous", fetchPriority: "low" });
  // 雑誌名(ラベル「週刊少年ジャンプ」用)だけをこの頁に渡す
  const magazines = Object.fromEntries(loadMasters().magazines.map((m) => [m.key, m.name]));
  return <MagicCompass magazines={magazines} />;
}

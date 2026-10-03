import type { Metadata } from "next";
import { preload } from "react-dom";
import { loadMasters } from "@/lib/loadData";
import MagicCompass from "./MagicCompass";
import "./compass.css";

// ★羅針盤(/compass)。 2026-10-03 ユーザ裁定で本番へ(旧 = テスト環境専用の実験頁 /lab/magic-shelf)。
//   ★本番:   索引 = 本番の公開索引(/manga-*.json)をそのまま読む。 「しまう」(本棚)は出さない(本棚はまだテスト環境のみ)。
//   ★テスト: 索引 = preview CI が置く本番の全件(/prod-idx/)。 テスト環境の索引は抜粋で糸がほぼ張れないため。
// 非索引(robots noindex・sitemap にも載らない): 描画は端末側で、配信HTMLに本文が無い(番人 _check-ssr-content.py は compass を除外)。
export const metadata: Metadata = {
  title: "羅針盤",
  description: "中央の1冊から、作者・雑誌・年・要素の糸を手繰って次の本へ旅する羅針盤。",
  robots: { index: false, follow: false },
};

/** 羅針盤 = 旅路つきの魔法の書架。依頼書 docs/cloud-briefs/magic-shelf-compass.md。
 *  データは useMangaIndex()(全件索引)を端末で逆引きするだけ。見本JSONは持たない。 */
export default function CompassPage() {
  // ★全件索引は大きいので HTML の段階で取り始める。 URL・取得モードは lib/useMangaIndex.ts の
  //   fetch と一致させる(fetch 既定 = mode cors / credentials same-origin ⇔ crossOrigin "anonymous")。
  //   ★基点(テスト=/prod-idx・本番="")は MagicCompass の setIndexBase と必ず揃える。
  if (process.env.NEXT_PUBLIC_PREVIEW_FEATURES === "1") {
    preload("/prod-idx/manga-list-head.json", { as: "fetch", crossOrigin: "anonymous" });
    preload("/prod-idx/manga-list-cols.v1.json", { as: "fetch", crossOrigin: "anonymous", fetchPriority: "low" });
    preload("/prod-idx/manga-catch-index.json", { as: "fetch", crossOrigin: "anonymous", fetchPriority: "low" });
  } else {
    preload("/manga-list-head.json", { as: "fetch", crossOrigin: "anonymous" });
    preload("/manga-list-cols.v1.json", { as: "fetch", crossOrigin: "anonymous", fetchPriority: "low" });
    preload("/manga-catch-index.json", { as: "fetch", crossOrigin: "anonymous", fetchPriority: "low" });
  }
  // 雑誌名(ラベル「週刊少年ジャンプ」用)とジャンル名をこの頁に渡す
  const masters = loadMasters();
  const magazines = Object.fromEntries(masters.magazines.map((m) => [m.key, m.name]));
  // ジャンル名(周りの本のラベル「歴史・時代劇」用・2026-09-30)
  const genres = Object.fromEntries(masters.genres.map((g) => [g.key, g.name]));
  return <MagicCompass magazines={magazines} genres={genres} />;
}

import { preload } from "react-dom";

/**
 * 一覧索引(列形式)の先読み指定を HTML に出す(2026-09-23 検索の読み込み高速化)。
 *
 * ★索引そのものが本文の面(/browse・/list)だけで呼ぶ。読むだけの頁(漫画詳細等)では呼ばない
 *   = 検索する気のない訪問者に数MBを落とさない方針([[search_perf_hotspots_2026_08]] 2026-09-08)。
 *   ホーム(/)は到着ウォームが saveData/2G を見て控える設計なので、ここは使わない。
 * ★URL・取得モードは lib/useMangaIndex.ts の fetch と一致させる(一致しないと二重に落とす):
 *   fetch() の既定 = mode cors / credentials same-origin ⇔ preload の crossOrigin "anonymous"。
 * ★fetchPriority low = JS・書影の取得を先に通し、空いた帯域で索引を落とす。
 */
export function preloadListIndex(): void {
  preload("/manga-list-cols.v1.json", { as: "fetch", crossOrigin: "anonymous", fetchPriority: "low" });
}

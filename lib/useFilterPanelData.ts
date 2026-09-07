"use client";

import { useEffect, useMemo, useState } from "react";
import {
  isAltLoading,
  onAltLoaded,
  prewarmSearch,
  searchWithTiers,
} from "@/lib/clientSearch";
import { ensureFullIndex, isFullIndexLoaded, useMangaIndex } from "@/lib/useMangaIndex";
import { authorsWithKana } from "@/lib/filters";
import type { MangaListItem } from "@/lib/schema";

/**
 * ★FilterPanel を出す画面の共通配線 (2026-09-06)。
 *
 * 経緯: 同じ FilterPanel を /browse(app/HomeClient.tsx) と /list(components/ListClient.tsx) が
 * 別々に手配線していたため、片方だけ更新されて静かにズレる事故を3回起こした。
 *   - /list に matchedSlugs を渡しておらず、ファセット件数が検索を無視して全件基準だった
 *   - /list は最後に自前で sortRows し直すので、パネルの並び順セレクトが効かない死んだUIだった
 *   - /list は state.artBooks を読まないので、画集チップが押しても何も起きなかった
 * 索引ロード・検索の一致集合・確定前フラグ・著者50音は「どちらの画面でも同じ」なので、
 * ここに1本化して両画面が同じものを受け取るようにする。以後 prop を足すときもここに足せば
 * 両方へ同時に効く。
 *
 * ★画面ごとに違うのは3点だけで、それは引数で受ける:
 *   - withCatch  : カード表示にキャッチ文が要るか(/browse=要る, /list=要らない)
 *   - query      : 検索語の出どころ(/browse=FilterState.query, /list=独立state の q)
 *   - authorsReady: 著者50音を作ってよいか(/list は抽斗を一度開くまで作らない=実測166msの節約)
 *   - enabled     : 索引の取得を要求してよいか(既定 true)。PC左レールだけ false から始める
 *                   = 素通りの読者に 6.06MB + haystack前計算3.7秒を課さないため(2026-09-08)。
 */
export type FilterPanelData = {
  /** 索引そのもの(未到着=null)。 */
  mangaIndex: MangaListItem[] | null;
  /** 索引(未到着は空配列)。 */
  manga: MangaListItem[];
  /** 索引がまだ届いていない。 */
  indexLoading: boolean;
  /** 前後の空白を落とした検索語。 */
  needle: string;
  hasQuery: boolean;
  /** 検索の一致(slug→tier)。検索語が無ければ null。 */
  searchTiers: Map<string, number> | null;
  /** 一致slug集合 = FilterPanel の matchedSlugs。検索語が無ければ null。 */
  matchedSlugs: Set<string> | null;
  /** 検索語はあるが索引が未到着(= 一覧側の「検索しています…」)。 */
  searchLoading: boolean;
  /** フル索引/別名照合がまだ = 検索結果が確定していない(0件と断言しない窓)。 */
  searchPending: boolean;
  /** FilterPanel の loading prop(件数を出してよいか)。 */
  panelLoading: boolean;
  /** 著者50音索引の材料。authorsReady=false の間は空配列。 */
  authorEntries: { name: string; kana: string; count: number }[];
};

export function useFilterPanelData(opts: {
  query: string;
  withCatch?: boolean;
  authorsReady?: boolean;
  enabled?: boolean;
}): FilterPanelData {
  const { query, withCatch = false, authorsReady = true, enabled = true } = opts;

  // ★一覧 manga は軽量索引をクライアント遅延ロード (= SSR props で 65k を送らない)。
  const mangaIndex = useMangaIndex({ withCatch, enabled });
  const manga = useMemo(() => mangaIndex ?? [], [mangaIndex]);
  const indexLoading = mangaIndex === null;

  const needle = query.trim();
  const hasQuery = needle.length > 0;

  // ★検索v2(2026-07-14): 検索専用索引を廃止し一覧索引を共有(前計算haystack+逐次絞り込み+2段照合)。
  //   alt(別名)は題名ヒット0の時だけ遅延fetch → 到着したら altTick で再検索。
  const [altTick, setAltTick] = useState(0);
  useEffect(() => onAltLoaded(() => setAltTick((v) => v + 1)), []);
  useEffect(() => {
    // ★enabled=false の間は前計算もしない(haystack は実機3.7秒。休止中のレールに払わせない)
    if (enabled && mangaIndex) prewarmSearch(mangaIndex); // 手すきで前計算(検索開始時のワンショット遅延を消す)
  }, [enabled, mangaIndex]);
  useEffect(() => {
    // 検索語が在る=利用者は検索している → 休止中でもフル索引を要求してよい
    if (hasQuery) ensureFullIndex(); // 検索確定=フル索引を即時要求(head 200件だけの誤答窓を閉じる)
  }, [hasQuery]);

  const searchTiers = useMemo(
    () => (hasQuery ? searchWithTiers(needle, manga) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [hasQuery, needle, manga, altTick],
  );
  const matchedSlugs = useMemo(
    () => (searchTiers ? new Set(searchTiers.keys()) : null),
    [searchTiers],
  );

  const searchLoading = hasQuery && indexLoading;
  // ★偽0件対策=B案(2026-08-18 ユーザ裁定): フル索引が届く前(head100件だけ)や、題名ヒット0で
  //   別名(alt)照合がまだの間は「検索が確定していない」。この間は
  //   ①0件と断言しない(検索中表示に差し替え) ②部分結果には「検索中」バッジを重ねる。
  //   再計算タイミング: full到着=_indexListeners→再レンダー / alt到着=altTick で担保される。
  const searchPending = hasQuery && (!isFullIndexLoaded() || isAltLoading());
  // ★FilterPanel へ渡す「まだ確定していない」signal(2026-09-05)。
  //   索引未到着/検索確定前は全facetが0になり、絞り込んで0件になった廃墟と区別が付かなかった。
  const panelLoading = indexLoading || searchLoading || searchPending;

  const authorEntries = useMemo(
    () => (authorsReady ? authorsWithKana(manga, true) : []),
    [manga, authorsReady],
  );

  return {
    mangaIndex,
    manga,
    indexLoading,
    needle,
    hasQuery,
    searchTiers,
    matchedSlugs,
    searchLoading,
    searchPending,
    panelLoading,
    authorEntries,
  };
}

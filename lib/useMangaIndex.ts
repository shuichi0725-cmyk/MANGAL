"use client";

import { useEffect, useState } from "react";
import type { MangaListItem } from "./schema";

// ★一覧索引をクライアントで遅延ロード (= SSR props で 65k を送らない)。
//   /manga-list-index.json を一度だけ fetch → module キャッシュで全ページ共有。
//   静的ファイル(R2/public)なので CDN キャッシュも効く ([[hosting_worker_r2_architecture]])。
let _cache: MangaListItem[] | null = null;
let _inflight: Promise<MangaListItem[]> | null = null;

function fetchIndex(): Promise<MangaListItem[]> {
  if (_cache) return Promise.resolve(_cache);
  if (_inflight) return _inflight;
  _inflight = fetch("/manga-list-index.json")
    .then((r) => {
      if (!r.ok) throw new Error(`索引取得失敗 ${r.status}`);
      return r.json();
    })
    .then((d: MangaListItem[]) => {
      _cache = d;
      return d;
    })
    .finally(() => {
      _inflight = null;
    });
  return _inflight;
}

/** 一覧索引を返す。 未ロード時は null (= 呼び出し側で loading 表示)。 */
export function useMangaIndex(): MangaListItem[] | null {
  const [data, setData] = useState<MangaListItem[] | null>(_cache);
  useEffect(() => {
    let alive = true;
    fetchIndex().then((d) => {
      if (alive) setData(d);
    });
    return () => {
      alive = false;
    };
  }, []);
  return data;
}

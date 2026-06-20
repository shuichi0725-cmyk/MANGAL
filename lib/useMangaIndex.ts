"use client";

import { useEffect, useState } from "react";
import type { MangaListItem, MangaSearchItem } from "./schema";

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

// ★検索索引 = 別ファイル。 検索ボックスに入力があった時だけ遅延ロード (= 既定ブラウズでは読まない)。
let _scache: MangaSearchItem[] | null = null;
let _sinflight: Promise<MangaSearchItem[]> | null = null;
function fetchSearchIndex(): Promise<MangaSearchItem[]> {
  if (_scache) return Promise.resolve(_scache);
  if (_sinflight) return _sinflight;
  _sinflight = fetch("/manga-search-index.json")
    .then((r) => {
      if (!r.ok) throw new Error(`検索索引取得失敗 ${r.status}`);
      return r.json();
    })
    .then((d: MangaSearchItem[]) => {
      _scache = d;
      return d;
    })
    .finally(() => {
      _sinflight = null;
    });
  return _sinflight;
}

/**
 * 検索索引を返す。 `enabled` (= 検索クエリ有) が true の時だけ fetch する。
 * 未ロード/未要求時は null。
 */
export function useSearchIndex(enabled: boolean): MangaSearchItem[] | null {
  const [data, setData] = useState<MangaSearchItem[] | null>(_scache);
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    fetchSearchIndex().then((d) => {
      if (alive) setData(d);
    });
    return () => {
      alive = false;
    };
  }, [enabled]);
  return data;
}

"use client";

import { useEffect, useState } from "react";
import type { MangaListItem, MangaSearchItem } from "./schema";
import { decodeListIndex } from "./listIndexDecode";

// ★一覧索引をクライアントで遅延ロード (= SSR props で 65k を送らない)。
//   /manga-list-index.json を一度だけ fetch → module キャッシュで全ページ共有。
//   静的ファイル(R2/public)なので CDN キャッシュも効く ([[hosting_worker_r2_architecture]])。
// ★軽量化: 索引は {f:フィールド順, d:値配列[]} の配列形式(キー名の65,980回重複を排除)。
//   ここでオブジェクトに復元(デコード層)するので、コンポーネントは無改修で m.title 等が使える。
//   catch は別ファイル(manga-catch-index.json)を遅延ロードして後から merge = カード維持・主索引軽量。
type RawIndex = { f: string[]; d: unknown[][] };
let _cache: MangaListItem[] | null = null;       // head(部分) → full に置換される
let _cacheIsFull = false;
let _inflight: Promise<MangaListItem[]> | null = null;
let _catchLoaded = false;
const _catchListeners = new Set<() => void>();
// ★head→full 置換をフックへ通知(2026-07-14 コールドスタート対策: 先頭200件で即描画→全件差替)
const _indexListeners = new Set<() => void>();

const decode = decodeListIndex; // 共有デコーダ(fl展開・authorsパック復元・cover復元)

function loadCatch(): void {
  if (_catchLoaded || !_cache) return;
  _catchLoaded = true;
  fetch("/manga-catch-index.json")
    .then((r) => (r.ok ? r.json() : {}))
    .then((cm: Record<string, string>) => {
      if (_cache)
        for (const m of _cache) {
          const c = cm[m.slug];
          if (c) (m as { catch?: string }).catch = c;
        }
      _catchListeners.forEach((fn) => fn());
    })
    .catch(() => {});
}

// ★初期サクサク化(2026-07-19 ユーザ体感報告): フル索引(22MB+67kデコード)を初描画と奪い合わない。
//   head(200件)で即描画 → フルは requestIdleCallback(初描画後の手すき・上限2秒)で開始。
//   デコードも8,000行ずつのチャンク処理=メインスレッドの長タスク(旧~数百ms一撃)を解消。
//   検索確定・フィルタ時は ensureFullIndex() で即時開始(headだけで検索する誤答窓を最小化)。
async function decodeChunked(raw: RawIndex): Promise<MangaListItem[]> {
  const CH = 8000;
  const out: MangaListItem[] = [];
  for (let i = 0; i < raw.d.length; i += CH) {
    out.push(...decode({ f: raw.f, d: raw.d.slice(i, i + CH) }));
    if (i + CH < raw.d.length) await new Promise((r) => setTimeout(r, 0));
  }
  return out;
}

let _fullState: "idle" | "loading" | "done" = "idle";

/** フル索引の取得を(まだなら)開始する。検索/フィルタ開始時に呼んで正確性を担保。冪等。 */
export function ensureFullIndex(): void {
  if (_fullState !== "idle") return;
  _fullState = "loading";
  fetch("/manga-list-index.json")
    .then((r) => {
      if (!r.ok) throw new Error(`索引取得失敗 ${r.status}`);
      return r.json();
    })
    .then((raw: RawIndex) => decodeChunked(raw))
    .then((items) => {
      _cache = items;
      _cacheIsFull = true;
      _fullState = "done";
      _indexListeners.forEach((fn) => fn());
      loadCatch(); // catch は非同期で後から merge
    })
    .catch(() => {
      _fullState = "idle"; // 失敗時は再試行可能に
    });
}

function scheduleIdle(fn: () => void, timeout = 2000): void {
  if (typeof requestIdleCallback === "function") requestIdleCallback(fn, { timeout });
  else setTimeout(fn, 800);
}

function fetchIndex(): Promise<MangaListItem[]> {
  if (_cacheIsFull && _cache) return Promise.resolve(_cache);
  if (_inflight) return _inflight;
  const headP: Promise<void> = _cache
    ? Promise.resolve()
    : fetch("/manga-list-head.json")
        .then((r) => (r.ok ? r.json() : null))
        .then((raw: RawIndex | null) => {
          if (raw && !_cache) {
            _cache = decode(raw);
            _indexListeners.forEach((fn) => fn());
          }
        })
        .catch(() => {});
  _inflight = headP
    .then(() => {
      scheduleIdle(() => ensureFullIndex()); // フルは初描画後の手すきで
      return _cache ?? [];
    })
    .finally(() => {
      _inflight = null;
    });
  return _inflight;
}

/** 一覧索引を返す。 未ロード時は null。 head→full差替/catchロード完了時は再レンダーで反映。 */
export function useMangaIndex(): MangaListItem[] | null {
  const [data, setData] = useState<MangaListItem[] | null>(_cache);
  const [, force] = useState(0);
  useEffect(() => {
    let alive = true;
    const onIndex = () => {
      if (alive) setData(_cache);
    };
    _indexListeners.add(onIndex);
    fetchIndex().then((d) => {
      if (alive) setData(d);
    });
    const onCatch = () => {
      if (alive) force((v) => v + 1);
    };
    if (_catchLoaded) onCatch();
    else _catchListeners.add(onCatch);
    return () => {
      alive = false;
      _indexListeners.delete(onIndex);
      _catchListeners.delete(onCatch);
    };
  }, []);
  return data;
}

// ★検索索引 = 別ファイル。 検索ボックスに入力があった時だけ遅延ロード (= 既定ブラウズでは読まない)。
let _scache: MangaSearchItem[] | null = null;
let _sinflight: Promise<MangaSearchItem[]> | null = null;
// 検索索引も {f,d} 配列形式 → デコード(cover無いので単純)。 client専用(server側ローダ無し)。
function decodeSearch(raw: RawIndex): MangaSearchItem[] {
  const { f, d } = raw;
  return d.map((arr) => {
    const o: Record<string, unknown> = {};
    for (let i = 0; i < f.length; i++) {
      const v = arr[i];
      if (v !== null && v !== undefined) o[f[i]] = v;
    }
    return o as unknown as MangaSearchItem;
  });
}
function fetchSearchIndex(): Promise<MangaSearchItem[]> {
  if (_scache) return Promise.resolve(_scache);
  if (_sinflight) return _sinflight;
  _sinflight = fetch("/manga-search-index.json")
    .then((r) => {
      if (!r.ok) throw new Error(`検索索引取得失敗 ${r.status}`);
      return r.json();
    })
    .then((raw: RawIndex) => {
      _scache = decodeSearch(raw);
      return _scache;
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

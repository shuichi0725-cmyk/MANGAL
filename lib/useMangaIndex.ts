"use client";

import { useEffect, useState } from "react";
import type { MangaListItem } from "./schema";
import { decodeListIndex } from "./listIndexDecode";
import { nowMs, perfDiag, since } from "./perfDiag";

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
// ★キャッチ文(manga-catch-index.json 6.9MB)は【カード表示の画面だけ】読む(2026-08-01)。
//   旧: フル索引が揃ったら無条件に fetch して63,749件へ merge していたが、
//   実際に catch を描画するのは MangaCard(=ホームのカード一覧)だけ。
//   一覧表(/list は表形式)とカレンダーは一切使わないのに6.9MBを落としていた。
let _catchWanted = false;
const _catchListeners = new Set<() => void>();
// ★head→full 置換をフックへ通知(2026-07-14 コールドスタート対策: 先頭100件で即描画→全件差替)
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
//   head(100件。manga-list-head.json の実体も100件)で即描画 → フルは
//   requestIdleCallback(初描画後の手すき・上限2秒)で開始。
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
  const _t0 = nowMs();
  let _tDecode = 0;
  fetch("/manga-list-index.json")
    .then((r) => {
      if (!r.ok) throw new Error(`索引取得失敗 ${r.status}`);
      return r.json();
    })
    .then((raw: RawIndex) => {
      perfDiag.fullFetchMs = since(_t0); // 取得+解凍+JSON.parse
      _tDecode = nowMs();
      return decodeChunked(raw);
    })
    .then((items) => {
      perfDiag.fullDecodeMs = since(_tDecode);
      _cache = items;
      _cacheIsFull = true;
      _fullState = "done";
      _indexListeners.forEach((fn) => fn());
      if (_catchWanted) loadCatch(); // ★キャッチを使う画面だけ(下の useMangaIndex 参照)
    })
    .catch(() => {
      _fullState = "idle"; // 失敗時は再試行可能に
    });
}

/** フル索引が手元に揃っているか(検索UIの「読み込み中」表示用)。full到着時は
 *  _indexListeners 経由で使用側が再レンダーされるため、レンダー中に読めば十分新しい。 */
export function isFullIndexLoaded(): boolean {
  return _cacheIsFull;
}

/** フル索引が揃った時に items を一度だけ渡す(既に揃っていれば即時)。
 *  ホームの検索ウォーム(到着時にhaystack前計算まで済ませる 2026-08-31)用。 */
export function onFullIndex(fn: (items: MangaListItem[]) => void): void {
  if (_cacheIsFull && _cache) {
    fn(_cache);
    return;
  }
  const h = () => {
    if (_cacheIsFull && _cache) {
      _indexListeners.delete(h);
      fn(_cache);
    }
  };
  _indexListeners.add(h);
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

/** 一覧索引を返す。 未ロード時は null。 head→full差替/catchロード完了時は再レンダーで反映。
 *  @param opts.withCatch キャッチ文も必要な画面(=カード表示)だけ true。
 *         渡さなければ manga-catch-index.json(6.9MB) を落とさない。 */
export function useMangaIndex(opts?: { withCatch?: boolean }): MangaListItem[] | null {
  const withCatch = !!opts?.withCatch;
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
    if (withCatch) {
      _catchWanted = true;
      if (_cacheIsFull) loadCatch(); // 先に別画面で索引だけ揃っていた場合の取り返し
      if (_catchLoaded) onCatch();
      else _catchListeners.add(onCatch);
    }
    return () => {
      alive = false;
      _indexListeners.delete(onIndex);
      _catchListeners.delete(onCatch);
    };
  }, [withCatch]);
  return data;
}

// (旧: 検索索引 manga-search-index.json の遅延ロード層は 2026-08-03 廃止。
//  検索は clientSearch.ts が一覧索引+alt索引を共有する方式に統一済みで呼び出し元ゼロだった。)

"use client";

/**
 * ★実機の実数字を採るための診断カウンタ(2026-08-01)。
 *
 * なぜ要るか: 性能の議論を PC の Node 実測だけでやると当たらない。
 * ユーザ報告「検索押す→画面でる→なぜか動かない」に対し、
 * こちらの計測(検索40ms程度)とは桁が合わないため、★端末側の実数字★が要る。
 *
 * 特に知りたいのは **haySyncMs** = 検索ボタンを押した瞬間に haystack の残りを
 * 同期で埋めてしまった時間。前計算が追いついていないと searchWithTiers が
 * その場で全行ぶん作るため、ここが体感の固まりの正体である可能性が高い
 * (PC実測でフル構築 2,714ms → モバイルは数倍)。
 *
 * 表示は一覧/検索面の★テスト専用パネルだけ★(preview / localhost / mangal-diag=1)。
 * 本番の通常利用者には出ない。計測自体は performance.now() の加算のみで無視できる。
 */
export type PerfDiag = {
  /** フル索引の fetch(ネットワーク+解凍) */
  fullFetchMs: number | null;
  /** フル索引のデコード(68,724件をオブジェクトへ) */
  fullDecodeMs: number | null;
  /** ★検索時に同期で埋めた haystack の合計時間と行数(= 押した瞬間の固まり) */
  haySyncMs: number;
  haySyncRows: number;
  /** 空き時間に埋めた haystack の合計時間と行数 */
  hayIdleMs: number;
  hayIdleRows: number;
  /** 直近の検索実行 */
  searchMs: number | null;
  searchHits: number | null;
  /** 別名索引(初回検索時に遅延取得) */
  altFetchMs: number | null;
};

export const perfDiag: PerfDiag = {
  fullFetchMs: null,
  fullDecodeMs: null,
  haySyncMs: 0,
  haySyncRows: 0,
  hayIdleMs: 0,
  hayIdleRows: 0,
  searchMs: null,
  searchHits: null,
  altFetchMs: null,
};

/** 経過ミリ秒(整数)。 performance が無い環境でも落ちない。 */
export function since(t0: number): number {
  const now = typeof performance !== "undefined" ? performance.now() : Date.now();
  return Math.round(now - t0);
}

export function nowMs(): number {
  return typeof performance !== "undefined" ? performance.now() : Date.now();
}

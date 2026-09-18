import fs from "node:fs";
import path from "node:path";
import type { AizItem, TksItem } from "@/components/EditionCorners";

/** 版ものコーナー(/color-manga・/aizouban・/tokusouban)のデータ層。server専用(fs)。
 *
 *  ★2026-09-18 新設の理由(番人 _check-ssr-content.py が検出した実害):
 *  この3頁は `*ListClient` が `fetch("/data/*.json")` でクライアント描画しており、
 *  **配信HTMLが「読み込み中…」だけ**だった(頁固有の本文 56〜95字・作品リンク0本)。
 *  ブラウザでは正常に見えるので目視では気づけない。[[ssr_content_gate]] の型。
 *
 *  直し方 = `/shinkan` が 2026-09-01 に採った手と同じ:
 *  **同じJSONを build 時に fs で読み、props で渡して初期HTMLに焼く**。
 *  チップ絞り込み・並び替え・KanaShelf の対話は client のままなので体験は変わらない。
 *
 *  ★props はRSCペイロードに直列化され、Next は同じ物を HTML内インライン と `.txt` の
 *  2箇所に書く = 実データの約2倍が頁に乗る([[shell_props_serialized_to_all_routes]])。
 *  ここで許容できるのは **対象が3頁だけ**だから(あの事故は共通layout×92,000ルートだった)。
 *  共通シェル側へ同じことをしてはいけない。
 */
const DIR = path.join(process.cwd(), "public", "data");

function readJson<T>(name: string, fallback: T): T {
  const p = path.join(DIR, name);
  try {
    if (!fs.existsSync(p)) return fallback;
    return JSON.parse(fs.readFileSync(p, "utf8")) as T;
  } catch {
    return fallback;
  }
}

/** 電子カラー版(/color-manga)。key = slug。 */
export type ColorEntry = { v: number; u: string; c?: string | null; b?: string; t?: string };

export function loadColorEditions(): Record<string, ColorEntry> {
  return readJson<Record<string, ColorEntry>>("color-editions.json", {});
}

/** 愛蔵版・合本(/aizouban)。 */
export function loadAizoubanStock(): AizItem[] {
  return readJson<AizItem[]>("aizouban-stock.json", []);
}

/** 特装版・限定版(/tokusouban)。 */
export function loadTokusoubanStock(): TksItem[] {
  return readJson<TksItem[]>("tokusouban-stock.json", []);
}

/** 「三世代、今日の一冊」の在庫と凍結ログ(/sansedai-archive)。 [[sansedai_archive_frozen_log]] */
export function loadSansedaiStock(): import("./sansedai").SansedaiEntry[] {
  return readJson<import("./sansedai").SansedaiEntry[]>("sansedai-stock.json", []);
}

export function loadSansedaiLog(): Record<string, import("./sansedai").SansedaiEntry[]> {
  return readJson<Record<string, import("./sansedai").SansedaiEntry[]>>("sansedai-log.json", {});
}

/** 日替わり特集(/tokushu)。 [[daily_feature_corner]]
 *  ★build時の「今日」を server で読んで Suspense の fallback に焼くために使う
 *  (useSearchParams を使う client は静的出力では必ず fallback がHTMLになるため、
 *   そこが「読み込み中…」だと配信HTMLが空になる = 2026-09-18 是正)。 */
export type TokushuItem = [string, string, string, string | null, number | null, number | null, string | null];
export type TokushuDay = {
  t: string; lead: string; n: number; q: string;
  sty: { l: "A" | "B"; p: 1 | 2 };
  c: { a: string; d: string };
  items: TokushuItem[];
};
export type TokushuIndexDays = Record<string, { t: string; n: number; sty: { l: string; p: number }; c: { a: string; d: string } }>;

/** JSTの「今日」(build時刻基準)。 */
export function jstTodayStr(): string {
  return new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
}

export function loadTokushuDay(date: string): TokushuDay | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;
  const p = path.join(DIR, "tokushu", `${date}.json`);
  try {
    if (!fs.existsSync(p)) return null;
    return JSON.parse(fs.readFileSync(p, "utf8")) as TokushuDay;
  } catch {
    return null;
  }
}

export function loadTokushuIndexDays(): TokushuIndexDays {
  const p = path.join(DIR, "tokushu", "index.json");
  try {
    if (!fs.existsSync(p)) return {};
    return (JSON.parse(fs.readFileSync(p, "utf8")) as { days?: TokushuIndexDays }).days ?? {};
  } catch {
    return {};
  }
}

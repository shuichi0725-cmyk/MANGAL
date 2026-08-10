import { loadAllManga } from "./loadData";
import type { Manga } from "./schema";

/** 著者静的ページ用マップ(2026-08-10 preview試作)。
 *  loadAllManga から著者→作品を組み立てる(ビルド時のみ・moduleキャッシュ)。
 *  key = 著者romaji(kana由来ヘボン連結形)をslug化。衝突は五十音順で -2 連番。
 *  romaji無し著者(ヨミ未解決372人層)は試作では対象外(チップ未差替なのでリンク切れは生じない)。 */

export type AuthorWork = {
  slug: string;
  title: string;
  year: number | null;
  cover: string | null;
  role: "author" | "original";
};

export type AuthorPage = {
  key: string;
  name: string;
  kana: string | null;
  works: AuthorWork[];      // 作画(authors)
  originals: AuthorWork[];  // 原作(original_authors)
};

let _map: Map<string, AuthorPage> | null = null;

function slugify(romaji: string): string {
  return romaji
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function coverOf(m: Manga): string | null {
  for (const e of m.editions) for (const v of e.volumes) if (v.cover_url) return v.cover_url;
  return null;
}

export function authorMap(): Map<string, AuthorPage> {
  if (_map) return _map;
  const { manga } = loadAllManga();
  // 名前→集計(同名は現状1人扱い=データ構造の忠実な反映。NDL典拠分離は将来課題)
  type Acc = { name: string; kana: string | null; romaji: string | null; works: AuthorWork[]; originals: AuthorWork[] };
  const byName = new Map<string, Acc>();
  const push = (m: Manga, a: { name: string; kana?: string | null; romaji?: string | null }, role: "author" | "original") => {
    if (!a.name) return;
    let acc = byName.get(a.name);
    if (!acc) {
      acc = { name: a.name, kana: a.kana ?? null, romaji: a.romaji ?? null, works: [], originals: [] };
      byName.set(a.name, acc);
    }
    if (!acc.kana && a.kana) acc.kana = a.kana;
    if (!acc.romaji && a.romaji) acc.romaji = a.romaji;
    const w: AuthorWork = { slug: m.slug, title: m.title, year: m.year_started ?? null, cover: coverOf(m), role };
    (role === "author" ? acc.works : acc.originals).push(w);
  };
  for (const m of manga) {
    for (const a of m.authors ?? []) push(m, a as never, "author");
    for (const a of m.original_authors ?? []) push(m, a as never, "original");
  }
  // key割当(romaji slug・衝突は五十音順-2)
  const list = [...byName.values()]
    .filter((a) => a.romaji && slugify(a.romaji))
    .sort((x, y) => (x.kana ?? x.name).localeCompare(y.kana ?? y.name, "ja"));
  const used = new Map<string, number>();
  _map = new Map();
  for (const a of list) {
    const base = slugify(a.romaji!);
    const n = (used.get(base) ?? 0) + 1;
    used.set(base, n);
    const key = n === 1 ? base : `${base}-${n}`;
    const sortWorks = (ws: AuthorWork[]) =>
      ws.sort((p, q) => (p.year ?? 9999) - (q.year ?? 9999) || p.title.localeCompare(q.title, "ja"));
    _map.set(key, { key, name: a.name, kana: a.kana, works: sortWorks(a.works), originals: sortWorks(a.originals) });
  }
  return _map;
}

export function getAuthor(key: string): AuthorPage | null {
  return authorMap().get(key) ?? null;
}

export function allAuthorKeys(): string[] {
  return [...authorMap().keys()];
}

let _byName: Map<string, string> | null = null;

/** 著者名→著者頁key(詳細頁チップの行き先解決用)。romaji無し著者はnull=従来の?author=にフォールバック。 */
export function authorKeyFor(name: string): string | null {
  if (!_byName) {
    _byName = new Map();
    for (const [k, a] of authorMap()) _byName.set(a.name, k);
  }
  return _byName.get(name) ?? null;
}

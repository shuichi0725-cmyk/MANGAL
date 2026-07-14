import { fullCover } from "./coverSlim";
import type { MangaListItem } from "./schema";

/**
 * ★一覧索引の共有デコーダ(2026-07-14): client(useMangaIndex)とserver(loadData)の二重実装を一本化。
 *  - {f,d}配列形式 → MangaListItem[](列名ベース=列の増減に耐性)
 *  - cover: slim → full URL 復元(coverSlim)
 *  - fl: 診断フラグのビットフィールド → 個別boolean展開(コンポーネント無改修)
 *  - authors/original_authors: "name\tkana" パック文字列 → {name,kana} 復元(旧オブジェクト形式も互換)
 */

const FL_SOLO_NONFIRST = 1;
const FL_VOL_GAP = 2;
const FL_COVER_GAP = 4;
const FL_ANTHOLOGY = 8;
const FL_SLUGFIX = 16;

type AuthorLike = { name: string; kana?: string; role?: string };

function unpackAuthors(v: unknown): AuthorLike[] {
  if (!Array.isArray(v)) return [];
  return (v as unknown[]).map((s) => {
    if (typeof s === "string") {
      const i = s.indexOf("\t");
      return i >= 0 ? { name: s.slice(0, i), kana: s.slice(i + 1) || undefined } : { name: s };
    }
    return s as AuthorLike; // 旧形式(オブジェクト)互換
  });
}

export function decodeListIndex(raw: unknown): MangaListItem[] {
  if (Array.isArray(raw)) return raw as MangaListItem[]; // 旧オブジェクト配列互換
  const { f, d } = raw as { f: string[]; d: unknown[][] };
  return d.map((arr) => {
    const o: Record<string, unknown> = {};
    for (let i = 0; i < f.length; i++) {
      const v = arr[i];
      if (v !== null && v !== undefined) o[f[i]] = v; // null は欠落扱い
    }
    if (o.cover) o.cover = fullCover(o.cover as string) as string;
    if (typeof o.fl === "number") {
      const fl = o.fl as number;
      if (fl & FL_SOLO_NONFIRST) o.solo_nonfirst = true;
      if (fl & FL_VOL_GAP) o.vol_gap = true;
      if (fl & FL_COVER_GAP) o.cover_gap = true;
      if (fl & FL_ANTHOLOGY) o._anthology = true;
      if (fl & FL_SLUGFIX) o._slugfix = true;
      delete o.fl;
    }
    if (o.authors) o.authors = unpackAuthors(o.authors);
    if (o.original_authors) o.original_authors = unpackAuthors(o.original_authors);
    if (!o.authors) o.authors = [];
    if (!o.original_authors) o.original_authors = [];
    return o as unknown as MangaListItem;
  });
}

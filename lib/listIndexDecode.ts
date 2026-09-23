import { fullCover } from "./coverSlim";
import type { MangaListItem } from "./schema";

/**
 * ★一覧索引の共有デコーダ(2026-07-14): client(useMangaIndex)とserver(loadData)の二重実装を一本化。
 *  - {f,d}配列形式 → MangaListItem[](列名ベース=列の増減に耐性)
 *  - ★{f,c}列形式(2026-09-23 ブラウザ専用 manga-list-cols.v1.json)も同じ出口で復元する。
 *    列ごとに値を並べ直した物(圧縮が効く=転送約3割減)。著者列は番号化(A=番号→"name\tkana")。
 *    生成= scripts/_index_files.py。先頭の src = 元の行配列の内容ハッシュ(=索引の版)。
 *  - cover: slim → full URL 復元(coverSlim)
 *  - fl: 診断フラグのビットフィールド → 個別boolean展開(コンポーネント無改修)
 *  - authors/original_authors: "name\tkana" パック文字列 → {name,kana} 復元(旧オブジェクト形式も互換)
 */

const FL_SOLO_NONFIRST = 1;
const FL_VOL_GAP = 2;
const FL_COVER_GAP = 4;
const FL_ANTHOLOGY = 8;
const FL_SLUGFIX = 16;
// ★1巻が無い(= 先頭がごっそり欠け。 2026-09-06『皆様の玩具です』4..9 で発覚)。
//   vol_gap にも立つが、内側の穴と区別できるよう別ビットで持つ。
const FL_NO_VOL1 = 32;

type AuthorLike = { name: string; kana?: string; role?: string };

export type RowListIndex = { f: string[]; d: unknown[][] };
export type ColumnarListIndex = {
  src: string;
  n: number;
  f: string[];
  c: unknown[][];
  A: string[];
  dc?: string[];
};
export type RawListIndex = RowListIndex | ColumnarListIndex | MangaListItem[];

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

export function isColumnarIndex(raw: unknown): raw is ColumnarListIndex {
  return (
    !!raw &&
    !Array.isArray(raw) &&
    typeof (raw as ColumnarListIndex).n === "number" &&
    Array.isArray((raw as ColumnarListIndex).c)
  );
}

/** 行数(形式によらず)。 */
export function indexRowCount(raw: RawListIndex): number {
  if (Array.isArray(raw)) return raw.length;
  if (isColumnarIndex(raw)) return raw.n;
  return (raw as RowListIndex).d.length;
}

/** 索引の版(= 列形式の src。行配列/旧形式は版を持たないので null)。 */
export function indexVersionOf(raw: RawListIndex): string | null {
  return isColumnarIndex(raw) && typeof raw.src === "string" ? raw.src : null;
}

/** 1行ぶんの後処理(形式共通)。 o は列名→値(null/undefined は入れない)。 */
function finishRow(o: Record<string, unknown>): MangaListItem {
  if (o.cover) o.cover = fullCover(o.cover as string) as string;
  if (typeof o.fl === "number") {
    const fl = o.fl as number;
    if (fl & FL_SOLO_NONFIRST) o.solo_nonfirst = true;
    if (fl & FL_VOL_GAP) o.vol_gap = true;
    if (fl & FL_COVER_GAP) o.cover_gap = true;
    if (fl & FL_ANTHOLOGY) o._anthology = true;
    if (fl & FL_SLUGFIX) o._slugfix = true;
    if (fl & FL_NO_VOL1) o.no_vol1 = true;
    delete o.fl;
  }
  if (o.authors) o.authors = unpackAuthors(o.authors);
  if (o.original_authors) o.original_authors = unpackAuthors(o.original_authors);
  if (!o.authors) o.authors = [];
  if (!o.original_authors) o.original_authors = [];
  return o as unknown as MangaListItem;
}

/** [from, to) 行ぶんを復元(細切れデコード用)。 */
export function decodeListIndexRange(raw: RawListIndex, from: number, to: number): MangaListItem[] {
  if (Array.isArray(raw)) return raw.slice(from, to) as MangaListItem[]; // 旧オブジェクト配列互換
  const out: MangaListItem[] = [];
  if (isColumnarIndex(raw)) {
    const { f, c, A } = raw;
    const dc = new Set(raw.dc ?? []);
    const coded = f.map((name) => dc.has(name)); // 番号化された列か(列ごとに1回だけ判定)
    const end = Math.min(to, raw.n);
    for (let i = from; i < end; i++) {
      const o: Record<string, unknown> = {};
      for (let j = 0; j < f.length; j++) {
        const v = c[j][i];
        if (v === null || v === undefined) continue; // null は欠落扱い
        o[f[j]] = coded[j] && Array.isArray(v) ? (v as number[]).map((k) => A[k]) : v;
      }
      out.push(finishRow(o));
    }
    return out;
  }
  const { f, d } = raw as RowListIndex;
  const end = Math.min(to, d.length);
  for (let r = from; r < end; r++) {
    const arr = d[r];
    const o: Record<string, unknown> = {};
    for (let i = 0; i < f.length; i++) {
      const v = arr[i];
      if (v !== null && v !== undefined) o[f[i]] = v; // null は欠落扱い
    }
    out.push(finishRow(o));
  }
  return out;
}

export function decodeListIndex(raw: unknown): MangaListItem[] {
  const r = raw as RawListIndex;
  return decodeListIndexRange(r, 0, indexRowCount(r));
}

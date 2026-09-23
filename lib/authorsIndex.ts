/** 著者50音索引の頁割り(2026-09-23)。
 *  旧 /authors は著者20,220人を1枚に並べて HTML 8.6MB・リンク20,255本になり、
 *  GSC の「インデックス登録をリクエスト」が3回とも失敗した(同日 /titles 0.2MB・/shinkan 3.5MB は成功)。
 *  → /titles と同じ「行ごとの目次 + /authors/<行>-<n> の分割頁」にする。
 *  頁割りはこのファイルが単一ソース(app/authors と app/authors/[part] が共有。
 *  sitemap は build 成果物 out/authors/*.html の実在から拾う=Python に再実装しない)。 */

/** 1頁あたりの人数(ハブ面の頁割り300件と揃える)。 */
export const AUTHORS_PER_PAGE = 300;

/** 行の定義。key は /titles と同じ(a, ka, … , other)。 */
export const AUTHOR_GYO: { key: string; label: string; re: RegExp | null }[] = [
  { key: "a", label: "あ行", re: /^[あ-おア-オヴ]/ },
  { key: "ka", label: "か行", re: /^[か-ごカ-ゴ]/ },
  { key: "sa", label: "さ行", re: /^[さ-ぞサ-ゾ]/ },
  { key: "ta", label: "た行", re: /^[た-どタ-ド]/ },
  { key: "na", label: "な行", re: /^[な-のナ-ノ]/ },
  { key: "ha", label: "は行", re: /^[は-ぽハ-ポ]/ },
  { key: "ma", label: "ま行", re: /^[ま-もマ-モ]/ },
  { key: "ya", label: "や行", re: /^[やゆよヤユヨ]/ },
  { key: "ra", label: "ら行", re: /^[ら-ろラ-ロ]/ },
  { key: "wa", label: "わ行", re: /^[わ-んワ-ン]/ },
  { key: "other", label: "英数他", re: null },
];

export type AuthorIndexEntry = { key: string; name: string; kana: string | null; n: number };
export type AuthorGyo = { key: string; label: string; count: number; pages: number };
export type AuthorsPages = { gyo: AuthorGyo[]; parts: Record<string, AuthorIndexEntry[]> };

/** 並び順どおりの著者一覧を行→頁に割る(純関数)。part key = "<行key>-<1始まりの頁番号>"。 */
export function splitAuthors(list: AuthorIndexEntry[], perPage = AUTHORS_PER_PAGE): AuthorsPages {
  const byGyo = new Map<string, AuthorIndexEntry[]>(AUTHOR_GYO.map((g) => [g.key, []]));
  for (const a of list) {
    const head = (a.kana || a.name).charAt(0);
    const g = AUTHOR_GYO.find((x) => x.re && x.re.test(head));
    byGyo.get(g ? g.key : "other")!.push(a);
  }
  const gyo: AuthorGyo[] = [];
  const parts: Record<string, AuthorIndexEntry[]> = {};
  for (const g of AUTHOR_GYO) {
    const rows = byGyo.get(g.key)!;
    const pages = Math.ceil(rows.length / perPage);
    gyo.push({ key: g.key, label: g.label, count: rows.length, pages });
    for (let i = 0; i < pages; i++) parts[`${g.key}-${i + 1}`] = rows.slice(i * perPage, (i + 1) * perPage);
  }
  return { gyo, parts };
}

/** part key → 行と頁番号。不正なら null。 */
export function parsePart(part: string): { gyoKey: string; page: number } | null {
  const i = part.lastIndexOf("-");
  if (i <= 0) return null;
  const page = Number(part.slice(i + 1));
  if (!Number.isInteger(page) || page < 1) return null;
  return { gyoKey: part.slice(0, i), page };
}

import fs from "node:fs";
import path from "node:path";
import { loadMangaListIndex } from "./loadData";
import { KNOWN_ALL, monthsCovering, rowsInRange, type KnownSet, type ShinkanItem, type ShinkanMonth } from "./shinkanDates";

export * from "./shinkanDates";

/** /shinkan 系の静的ページ(月別・今週・来月)のデータ層(2026-09-01 SEO)。server専用(fs)。
 *  ★源は public/shinkan/{ym}.json(= _gen-shinkan-data.py が週次step1で生成・git追跡)。
 *  ShinkanClient(対話面)と同じJSONを build 時に fs で読み、HTMLに焼く=Googleに中身が見える。 */
const DIR = path.join(process.cwd(), "public", "shinkan");

export function listShinkanMonths(): string[] {
  if (!fs.existsSync(DIR)) return [];
  return fs
    .readdirSync(DIR)
    .filter((f) => /^\d{4}-\d{2}\.json$/.test(f))
    .map((f) => f.slice(0, 7))
    .sort();
}

export function loadShinkanMonth(ym: string): ShinkanMonth | null {
  const p = path.join(DIR, `${ym}.json`);
  if (!/^\d{4}-\d{2}$/.test(ym) || !fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, "utf8")) as ShinkanMonth;
}

/** @deprecated monthCount(shinkanDates) を使う */
export { monthCount as monthTotal } from "./shinkanDates";

/** 範囲内の発売日→冊リスト(発売日順)。跨る月のJSONを全部見る。 */
export function itemsInRange(start: string, end: string): Array<{ date: string; items: ShinkanItem[] }> {
  const months: Record<string, ShinkanMonth | null> = {};
  for (const ym of monthsCovering(start, end)) months[ym] = loadShinkanMonth(ym);
  return rowsInRange(months, start, end);
}

let _known: Set<string> | null = null;
/** 「詳細」リンクを出してよい slug(=一覧索引に居る作品)。preview(subset)でも死リンクを撒かない。 */
export function knownSlugs(): Set<string> {
  if (!_known) _known = new Set(loadMangaListIndex().map((m) => m.slug));
  return _known;
}

/** 構造化データ: ItemList(Book+datePublished)。上限で頭を切る(頁重量)。
 *  ★author は出さない(2026-09-01 レビュー指摘: JSONの著者欄は「・」連結の表示用文字列で、
 *    名前自体に「・」を含む著者(ジョージ・ルーカス等)が別人に割れる+60字切詰めで欠ける。作品頁のJSON-LDが正)。
 *  ★url は一覧索引に居る slug だけ(索引外=本番404 になる頁をGoogleに配らない)。 */
export function shinkanJsonLd(
  name: string,
  url: string,
  rows: Array<{ date: string | null; items: ShinkanItem[] }>,
  known: KnownSet = KNOWN_ALL,
  limit = 300,
): Record<string, unknown> {
  const els: Record<string, unknown>[] = [];
  for (const r of rows) {
    for (const [slug, vol, title, cover, isbn, , publisher] of r.items) {
      if (els.length >= limit) break;
      els.push({
        "@type": "ListItem",
        position: els.length + 1,
        item: {
          "@type": "Book",
          name: vol ? `${title} ${vol}巻` : title,
          ...(isbn ? { isbn } : {}),
          ...(r.date ? { datePublished: r.date } : {}),
          ...(publisher ? { publisher: { "@type": "Organization", name: publisher } } : {}),
          ...(cover ? { image: cover } : {}),
          ...(known.has(slug) ? { url: `https://mangal-db.com/manga/${slug}` } : {}),
        },
      });
    }
  }
  return { "@context": "https://schema.org", "@type": "ItemList", name, url, numberOfItems: els.length, itemListElement: els };
}

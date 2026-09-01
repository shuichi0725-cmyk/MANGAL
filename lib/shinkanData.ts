import fs from "node:fs";
import path from "node:path";
import { loadMangaListIndex } from "./loadData";
import { monthsCovering, rowsInRange, type ShinkanItem, type ShinkanMonth } from "./shinkanDates";

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

export function monthTotal(d: ShinkanMonth): number {
  return Object.values(d.days).reduce((s, v) => s + v.length, 0) + (d.unknown?.length ?? 0);
}

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

/** 構造化データ: ItemList(Book+datePublished)。上限で頭を切る(頁重量) */
export function shinkanJsonLd(
  name: string,
  url: string,
  rows: Array<{ date: string | null; items: ShinkanItem[] }>,
  limit = 300,
): Record<string, unknown> {
  const els: Record<string, unknown>[] = [];
  for (const r of rows) {
    for (const [slug, vol, title, cover, isbn, authors, publisher] of r.items) {
      if (els.length >= limit) break;
      els.push({
        "@type": "ListItem",
        position: els.length + 1,
        item: {
          "@type": "Book",
          name: vol ? `${title} ${vol}巻` : title,
          ...(isbn ? { isbn } : {}),
          ...(r.date ? { datePublished: r.date } : {}),
          ...(authors ? { author: authors.split("・").map((n) => ({ "@type": "Person", name: n })) } : {}),
          ...(publisher ? { publisher: { "@type": "Organization", name: publisher } } : {}),
          ...(cover ? { image: cover } : {}),
          url: `https://mangal-db.com/manga/${slug}`,
        },
      });
    }
  }
  return { "@context": "https://schema.org", "@type": "ItemList", name, url, numberOfItems: els.length, itemListElement: els };
}

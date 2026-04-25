import type { Manga } from "./schema";

const DEFAULT_LOCALE = "jp";

const LOCALE_DOMAIN: Record<string, string> = {
  jp: "amazon.co.jp",
  com: "amazon.com",
  uk: "amazon.co.uk",
};

function domain(locale: string = DEFAULT_LOCALE): string {
  return LOCALE_DOMAIN[locale] ?? LOCALE_DOMAIN[DEFAULT_LOCALE];
}

export type AmazonLinkOptions = {
  associateTag?: string;
  locale?: string;
};

/** ASIN/ISBN13 が揃っていれば商品ページ、なければタイトル検索URLを返す。 */
export function buildAmazonUrl(manga: Manga, opts: AmazonLinkOptions = {}): string {
  const tag = opts.associateTag ?? "";
  const host = domain(opts.locale);
  const asin = manga.volume_1?.asin?.toString().trim();
  const isbn = manga.volume_1?.isbn13?.toString().trim();

  if (asin) {
    const url = new URL(`https://www.${host}/dp/${encodeURIComponent(asin)}`);
    if (tag) url.searchParams.set("tag", tag);
    return url.toString();
  }

  const url = new URL(`https://www.${host}/s`);
  url.searchParams.set("k", isbn || `${manga.title} ${manga.authors[0]?.name ?? ""}`);
  url.searchParams.set("i", "stripbooks");
  if (tag) url.searchParams.set("tag", tag);
  return url.toString();
}

/**
 * フェーズA: openBD のカバー画像 URL を ISBN13 から組み立てる。
 * 再配布可で、PA-API 承認前でも合法に表示できる。
 */
export function openBdCoverUrl(isbn13?: string | number | null): string | null {
  if (!isbn13) return null;
  const id = String(isbn13).replace(/[^0-9X]/gi, "");
  if (id.length !== 13) return null;
  return `https://cover.openbd.jp/${id}.jpg`;
}

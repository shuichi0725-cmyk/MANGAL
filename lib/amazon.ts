import { primaryVolume, type Manga, type Volume } from "./schema";

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

/**
 * 任意の巻について Amazon の商品ページ／検索URLを返す。
 * ASIN > ISBN13 > タイトル検索の優先順位。
 */
export function buildAmazonUrlForVolume(
  volume: Volume | undefined,
  manga: Manga,
  opts: AmazonLinkOptions = {},
): string {
  const tag = opts.associateTag ?? "";
  const host = domain(opts.locale);
  const asin = volume?.asin?.toString().trim();
  const isbn = volume?.isbn13?.toString().trim();

  if (asin) {
    const url = new URL(`https://www.${host}/dp/${encodeURIComponent(asin)}`);
    if (tag) url.searchParams.set("tag", tag);
    return url.toString();
  }

  const url = new URL(`https://www.${host}/s`);
  const titleQuery = volume?.number && volume.number > 1
    ? `${manga.title} ${volume.number}`
    : manga.title;
  url.searchParams.set("k", isbn || `${titleQuery} ${manga.authors[0]?.name ?? ""}`);
  url.searchParams.set("i", "stripbooks");
  if (tag) url.searchParams.set("tag", tag);
  return url.toString();
}

/** 主エディション 1 巻への Amazon URL。 */
export function buildAmazonUrl(manga: Manga, opts: AmazonLinkOptions = {}): string {
  return buildAmazonUrlForVolume(primaryVolume(manga), manga, opts);
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

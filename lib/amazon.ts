import { primaryVolume, type ArtBook, type Manga, type Volume } from "./schema";

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
 * 任意の巻について **電子書籍 (Kindle)** の URL を返す。
 * kindle_asin > Kindleストア検索 (i=digital-text) の優先順位。
 * ★紙の asin/isbn13 は Kindle 商品に紐付かないので、 kindle_asin が無ければ
 *   タイトル+著者で Kindle ストア検索にフォールバックする。
 */
export function buildKindleUrlForVolume(
  volume: Volume | undefined,
  manga: Manga,
  opts: AmazonLinkOptions = {},
): string {
  const tag = opts.associateTag ?? "";
  const host = domain(opts.locale);
  const kindle = volume?.kindle_asin?.toString().trim();

  if (kindle) {
    const url = new URL(`https://www.${host}/dp/${encodeURIComponent(kindle)}`);
    if (tag) url.searchParams.set("tag", tag);
    return url.toString();
  }

  const url = new URL(`https://www.${host}/s`);
  const titleQuery = volume?.number && volume.number > 1
    ? `${manga.title} ${volume.number}`
    : manga.title;
  url.searchParams.set("k", `${titleQuery} ${manga.authors[0]?.name ?? ""}`);
  url.searchParams.set("i", "digital-text");
  if (tag) url.searchParams.set("tag", tag);
  return url.toString();
}

/**
 * 画集の Amazon URL。 ASIN > ISBN13 > タイトル+作画家 検索の優先順位。
 * ArtBook は editions を持たず volumes 直下なので Manga 用とは別関数。
 */
export function buildAmazonUrlForArtBook(
  artBook: ArtBook,
  opts: AmazonLinkOptions = {},
  volume?: Volume,
): string {
  const tag = opts.associateTag ?? "";
  const host = domain(opts.locale);
  const v = volume ?? artBook.volumes[0];
  const asin = v?.asin?.toString().trim();
  const isbn = v?.isbn13?.toString().trim();

  if (asin) {
    const url = new URL(`https://www.${host}/dp/${encodeURIComponent(asin)}`);
    if (tag) url.searchParams.set("tag", tag);
    return url.toString();
  }
  const url = new URL(`https://www.${host}/s`);
  url.searchParams.set("k", isbn || `${artBook.title} ${artBook.artist}`);
  url.searchParams.set("i", "stripbooks");
  if (tag) url.searchParams.set("tag", tag);
  return url.toString();
}

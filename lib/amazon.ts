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

/** ISBN-13 → ISBN-10(チェックデジット再計算)。紙の書籍はAmazonのASIN=ISBN-10なので
 *  これで /dp/ 直リンクが組める(検索リンクより確実+コンバージョン高)。978以外(979等)は変換不能でnull。 */
export function isbn13ToIsbn10(isbn13: string | number | null | undefined): string | null {
  const s = String(isbn13 ?? "").replace(/[^0-9]/g, "");
  if (s.length !== 13 || !s.startsWith("978")) return null;
  const body = s.slice(3, 12);
  let sum = 0;
  for (let i = 0; i < 9; i++) sum += (10 - i) * Number(body[i]);
  const check = (11 - (sum % 11)) % 11;
  return body + (check === 10 ? "X" : String(check));
}

/** 素の検索クエリ用のAmazonリンク(tag付き)。component側の軽量利用向け。 */
export function amazonSearchUrl(query: string, tag: string, locale?: string): string {
  const url = new URL(`https://www.${domain(locale)}/s`);
  url.searchParams.set("k", query);
  url.searchParams.set("i", "stripbooks");
  if (tag) url.searchParams.set("tag", tag);
  return url.toString();
}

/** ISBN-13から /dp/ 直リンク(tag付き)。変換不能ならnull(呼び側で検索fallback)。 */
export function amazonDpUrlFromIsbn13(isbn13: string | number | null | undefined, tag: string, locale?: string): string | null {
  const i10 = isbn13ToIsbn10(isbn13);
  if (!i10) return null;
  const url = new URL(`https://www.${domain(locale)}/dp/${i10}`);
  if (tag) url.searchParams.set("tag", tag);
  return url.toString();
}

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
  // ★紙のASIN=ISBN-10なので、ISBNがあれば /dp/ 直リンク(2026-07-29 アソシエイト開設で有効化)
  const dp = amazonDpUrlFromIsbn13(isbn, tag, opts.locale);
  if (dp) return dp;

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
  const dp = amazonDpUrlFromIsbn13(isbn, tag, opts.locale);
  if (dp) return dp;
  const url = new URL(`https://www.${host}/s`);
  url.searchParams.set("k", isbn || `${artBook.title} ${artBook.artist}`);
  url.searchParams.set("i", "stripbooks");
  if (tag) url.searchParams.set("tag", tag);
  return url.toString();
}

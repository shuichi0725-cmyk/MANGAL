/** カラー版→Kindle直行リンクの共有ヘルパー(2026-08-12)。
 *  使用箇所=ColorCorner(ホームのカラー版コーナー)+ColorListClient(/color-manga一覧)。
 *  カラー版はASINを持たないため題名でKindleストア検索(i=digital-text)に飛ばす。 */

export function kindleSearchUrl(title: string): string {
  const tag = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG ?? "";
  const url = new URL("https://www.amazon.co.jp/s");
  url.searchParams.set("k", title);
  url.searchParams.set("i", "digital-text");
  if (tag) url.searchParams.set("tag", tag);
  return url.toString();
}

/** Kindleは必ずブラウザで開く(AffiliateLinkと同じ: Amazonアプリ内ではKindle本が買えない
 *  IAP規約対策)。本番(Worker配下)は /go 中継、preview/開発は window.open 簡易版。 */
export function openKindleInBrowser(e: { preventDefault(): void }, href: string) {
  e.preventDefault();
  const viaWorker =
    window.location.hostname === "mangal-db.com" || window.location.hostname.endsWith("workers.dev");
  window.open(viaWorker ? `/go?u=${encodeURIComponent(href)}` : href, "_blank", "noopener");
}

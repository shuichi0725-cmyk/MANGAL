/** カラー版→Kindle直行リンクの共有ヘルパー(2026-08-12)。
 *  使用箇所=ColorCorner(ホームのカラー版コーナー)+ColorListClient(/color-manga一覧)。
 *  カラー版はASINを持たないため題名でKindleストア検索(i=digital-text)に飛ばす。
 *  ★ブラウザ強制は不可能(2026-07-29 実機検証[[kindle-link-browser-not-app]]):
 *    Amazon検索URLは302/JS遷移に関係なく全形式アプリに奪われ、ブラウザで開くのは/dp/のみ。
 *    旧/go中継はWorkerから撤去済み(404)のため使わない。恒久解=PA-API解錠後に
 *    カラー版のKindle ASIN(B0…)を収穫し /dp/B0… 直リンク化。それまでは検索リンク=アプリ着地。 */

export function kindleSearchUrl(title: string): string {
  const tag = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG ?? "";
  const url = new URL("https://www.amazon.co.jp/s");
  url.searchParams.set("k", title);
  url.searchParams.set("i", "digital-text");
  if (tag) url.searchParams.set("tag", tag);
  return url.toString();
}

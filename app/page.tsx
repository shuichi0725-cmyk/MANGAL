import Design12 from "./home-design-12/page";

// ★canonicalはページ自身のURLを各routeで宣言(2026-07-19: layout継承の全頁"/"化でGoogleが/browse等を代替ページ扱い=deindexした事故の恒久修正)
export const metadata = { alternates: { canonical: "/" } };

/** ホーム = 案12「D3ダークブルータル」(★2026-08-13 ユーザGO=本番採用。previewトライアル卒業)。
 *  旧=案11(2026-06-13採用、/home-design-11 に温存)。旧フィルター付きグリッドは /browse へ。 */
export default function HomePage() {
  return <Design12 />;
}

import Design11 from "./home-design-11/page";

// ★canonicalはページ自身のURLを各routeで宣言(2026-07-19: layout継承の全頁"/"化でGoogleが/browse等を代替ページ扱い=deindexした事故の恒久修正)
export const metadata = { alternates: { canonical: "/" } };

/** ホーム = 案11(2026-06-13 ユーザ採用)。 旧フィルター付きグリッドは /browse へ。 */
export default function HomePage() {
  return <Design11 />;
}

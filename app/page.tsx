import Design12 from "./home-design-12/page";

// ★canonicalはページ自身のURLを各routeで宣言(2026-07-19: layout継承の全頁"/"化でGoogleが/browse等を代替ページ扱い=deindexした事故の恒久修正)
// ★「漫画 探す/検索」系クエリ対応(2026-08-17 ユーザ要望): title/descに検索意図語を明示。
//   absolute指定=layoutの"%s | MANGAL"テンプレートを回避(ブランド名二重を防ぐ)
export const metadata = {
  title: { absolute: "MANGAL — 日本の漫画データベース | 漫画を探す・全巻一覧" },
  description:
    "漫画を探す・検索するならMANGAL。68,000作品以上の日本の漫画を著者・出版年・出版社・ジャンル・完結/連載から絞り込めます。全巻の発売日・ISBN・書影と購入リンクつきの漫画データベース。",
  alternates: { canonical: "/" },
};

/** ホーム = 案12「D3ダークブルータル」(★2026-08-13 ユーザGO=本番採用。previewトライアル卒業)。
 *  旧=案11(2026-06-13採用、/home-design-11 に温存)。旧フィルター付きグリッドは /browse へ。 */

// ★WebSite構造化データ(2026-08-17): Googleの「サイト名」表示(検索結果でドメインでなくMANGALと出す)用。
//   Googleの要件=ホームページにのみ設置。作品頁のComicSeries/BreadcrumbListは実装済(2026-08-06)。
//   SearchAction(サイトリンク検索ボックス)は2024年にGoogleが廃止済みのため付けない。
const WEBSITE_LD = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: "MANGAL",
  alternateName: "MANGAL 日本の漫画データベース",
  url: "https://mangal-db.com/",
};

export default function HomePage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(WEBSITE_LD) }}
      />
      <Design12 />
    </>
  );
}

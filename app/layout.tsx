import SiteFooter from "@/components/SiteFooter";
import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import ScrollTopButton from "@/components/ScrollTopButton";
import GlobalDragScroll from "@/components/GlobalDragScroll";
import SiteHeader from "@/components/SiteHeader";
import GlobalNav from "@/components/GlobalNav";
import PageShell from "@/components/PageShell";
import FilterRail from "@/components/FilterRail";
import animeView from "@/data/anime-seasons-view.json";
import { animeNavSeasons, type AnimeSeasonsView } from "@/lib/animeSeason";
import { loadMasters } from "@/lib/loadData";
import { dotGothic } from "@/lib/fonts";

export const metadata: Metadata = {
  metadataBase: new URL("https://mangal-db.com"),
  title: {
    default: "MANGAL — 日本の漫画データベース",
    template: "%s | 漫画・コミックのMANGAL",
  },
  description:
    "出版年・著者・出版社・分野・ジャンルから日本の漫画を絞り込めるデータベース。全巻の発売日・ISBN・書影と、楽天ブックス等の購入リンクつき。",
};

// ★D3テーマ(黒×アシッドライム)= 2026-08-13 ユーザGOで本採用。全ビルドで常時付与。
//   (経緯: 2026-08-11にpreview限定トライアル→全ページ検証→本採用。ライト時代の配色は
//    globals.css の :root トークンとして残存=theme-d3クラスを外せば即戻せる)

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // ★PC左レール = 検索窓 + 絞り込みパネル。マスタ(出版社/雑誌/ジャンル/分野)を渡す。
  //   loadMasters はモジュールキャッシュ済み。作品索引はレール側がクライアントで遅延ロードする。
  const masters = loadMasters();
  // ★ナビ「アニメ化」の行き先(= ホームの今季コーナーと同じ /anime/<季>)。
  //   order(222件)ではなく**文字列2つだけ**を渡す = 全69,241頁のRSCペイロードに乗るため。
  const animeNav = animeNavSeasons((animeView as unknown as AnimeSeasonsView).order);
  return (
    <html lang="ja">
      <body className={`min-h-screen flex flex-col theme-d3 ${dotGothic.variable}`}>
        {/* PCマウスの横ドラッグを全横帯のスワイプ相当に変換(タッチは不介入) */}
        <GlobalDragScroll />
        {/* 共通ヘッダー(SiteHeader=client): ★ホームでは非表示 = Design12のE型ステータスバーが代替
            (2026-08-15 E融合型)。購入モードトグルは廃止済(2026-07-12)。 */}
        <SiteHeader />
        {/* ★2026-09-07: アイコンナビと PC左レールを layout へ一本化(旧= 47箇所が各自 DesignNav
            を呼び、レールはホームと漫画頁だけ)。ホームは PageShell 側で対象外にしている。 */}
        <main className="flex-1">
          <GlobalNav animeNow={animeNav.now} animeNext={animeNav.next} />
          <PageShell rail={<FilterRail masters={masters} />}>{children}</PageShell>
          <SiteFooter />
        </main>
        <footer className="border-t border-[var(--color-line)] mt-12 py-8 text-center text-xs text-ink/50 space-y-3">
          <nav className="flex justify-center gap-4">
            <Link href="/about" className="hover:text-ink">
              About
            </Link>
            <span aria-hidden="true">·</span>
            <Link href="/privacy" className="hover:text-ink">
              プライバシー
            </Link>
            <span aria-hidden="true">·</span>
            <Link href="/terms" className="hover:text-ink">
              利用規約
            </Link>
          </nav>
          <p>
            当サイトの商品リンクは Amazon.co.jp 等の外部サイトへ遷移します。
          </p>
        </footer>
        <ScrollTopButton />
        {/* ValueCommerce LinkSwitch (2026-08-05): BookLive等の提携広告主への素リンクを
            クリック時に自動でアフィリエイトリンクへ変換する。個別リンク加工不要
            (試し読みボタン結線時に25,149アンカーがそのまま収益化対象になる)。
            タグはVC管理画面「LinkSwitch設定」発行の正規スニペット(vc_pid=サイトID紐付き)。 */}
        <script
          dangerouslySetInnerHTML={{ __html: 'var vc_pid = "892673489";' }}
        />
        <script src="https://aml.valuecommerce.com/vcdal.js" async />
      </body>
    </html>
  );
}

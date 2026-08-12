import SiteFooter from "@/components/SiteFooter";
import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import ScrollTopButton from "@/components/ScrollTopButton";
import GlobalDragScroll from "@/components/GlobalDragScroll";
import SiteMenu from "@/components/SiteMenu";

export const metadata: Metadata = {
  metadataBase: new URL("https://mangal-db.com"),
  title: {
    default: "MANGAL — 日本の漫画データベース",
    template: "%s | MANGAL",
  },
  description:
    "出版年・著者・出版社・分野・ジャンルから日本の漫画を絞り込めるデータベース。全巻の発売日・ISBN・書影と、楽天ブックス等の購入リンクつき。",
};

// ★D3テーマ全ページトライアル(2026-08-11 ユーザ指示「全ページ変えたのを見たい」):
//   previewビルド(MANGAL_DATA_DIR=.preview-data)だけ body にテーマを付与。
//   本番ビルドは env 未設定=従来のライトテーマのまま(本採用はユーザGO後)。
const PREVIEW_D3 = (process.env.MANGAL_DATA_DIR ?? "").includes("preview");

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body className={`min-h-screen flex flex-col${PREVIEW_D3 ? " theme-d3" : ""}`}>
        {/* PCマウスの横ドラッグを全横帯のスワイプ相当に変換(タッチは不介入) */}
        <GlobalDragScroll />
        <header className="border-b border-[var(--color-line)] bg-[var(--color-surface)]/80 backdrop-blur sticky top-0 z-20">
          <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between gap-3">
            {/* 左 = ロゴ + 「日本の漫画データベース」。 ロゴ寄りに少し左へ。 */}
            <div className="flex items-baseline gap-2 min-w-0">
              <Link href="/" className="font-bold text-lg tracking-tight shrink-0">
                MANGAL<span className="text-[var(--color-accent)]">.</span>
              </Link>
              <span className="text-xs sm:text-sm text-ink/55 truncate">日本の漫画データベース</span>
            </div>
            {/* 右端 = ≡メニュー(2026-08-12 ユーザ裁定: ナビ行右端から共通ヘッダー右端へ移設。
                ホーム(D3Nav=メニュー無し)と他ページ(DesignNav)で位置が食い違っていたのを、
                全ページ「使い方の上=ヘッダー右端」に統一。ナビ行は使い方が右端になる) */}
            <SiteMenu />
            {/* 購入モードトグルは廃止(2026-07-12 ユーザ裁定)。電子は将来「電子書籍で買う」ボタン
                =ストアリスト方式で提供する([[store_affiliate_architecture]])。usePurchaseModeは
                Provider外の安全既定=print で動作継続。 */}
          </div>
        </header>
        <main className="flex-1">{children}
        <SiteFooter /></main>
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

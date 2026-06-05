import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import ScrollTopButton from "@/components/ScrollTopButton";
import { PurchaseModeProvider, PurchaseModeToggle, ScreenFlip } from "@/components/PurchaseMode";

export const metadata: Metadata = {
  title: "MANGAL — 日本の漫画データベース",
  description:
    "出版年・著者・出版社・分野・ジャンルから日本の漫画を絞り込めるデータベース。各作品の購入はAmazonへ。",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body className="min-h-screen flex flex-col">
        <PurchaseModeProvider>
        <header className="border-b border-[var(--color-line)] bg-[var(--color-surface)]/80 backdrop-blur sticky top-0 z-20">
          <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between gap-3">
            {/* 左 = ロゴ + 「日本の漫画データベース」。 ロゴ寄りに少し左へ。 */}
            <div className="flex items-baseline gap-2 min-w-0">
              <Link href="/" className="font-bold text-lg tracking-tight shrink-0">
                MANGAL<span className="text-[var(--color-accent)]">.</span>
              </Link>
              <span className="text-xs sm:text-sm text-ink/55 truncate">日本の漫画データベース</span>
            </div>
            {/* 右上 = 購入モードのトグル 1 個 (タップで 紙 ⇄ 電子 を 180度フリップ)。 */}
            <PurchaseModeToggle />
          </div>
        </header>
        <ScreenFlip>
          <main className="flex-1">{children}</main>
        </ScreenFlip>
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
        </PurchaseModeProvider>
      </body>
    </html>
  );
}

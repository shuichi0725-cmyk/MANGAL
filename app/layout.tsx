import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "MANGAL — 日本の漫画データベース",
  description:
    "出版年・著者・出版社・分野・ジャンルから日本の漫画を絞り込めるデータベース。各作品の購入はAmazonへ。",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body className="min-h-screen flex flex-col">
        <header className="border-b border-black/10 bg-white/70 backdrop-blur sticky top-0 z-20">
          <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between">
            <Link href="/" className="font-bold text-lg tracking-tight">
              MANGAL<span className="text-[var(--color-accent)]">.</span>
            </Link>
            <nav className="text-sm text-black/60">
              <span>日本の漫画データベース</span>
            </nav>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-black/10 mt-12 py-8 text-center text-xs text-black/50">
          <p>
            購入リンクは Amazon アソシエイトを利用しています。
          </p>
        </footer>
      </body>
    </html>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import SiteMenu from "@/components/SiteMenu";

/** 共通ヘッダー(2026-08-15 E融合型導入で client 化):
 *  ★ホーム("/")では描かない = ホームは Design12 側の「MANGAL_OS ステータスバー」が
 *  ヘッダーの役を担う(E融合型・ユーザ指示「ヘッダーから検索窓までEを取り入れる」)。
 *  他ページは従来のロゴ+≡メニューのまま。二重ヘッダー問題(2026-08-11)を再発させないための分岐。 */
export default function SiteHeader() {
  const pathname = usePathname();
  if (pathname === "/") return null;
  return (
    <header className="border-b border-[var(--color-line)] bg-[var(--color-surface)]/80 backdrop-blur sticky top-0 z-20">
      <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between gap-3">
        {/* 左 = ロゴ + 「日本の漫画データベース」。 ロゴ寄りに少し左へ。 */}
        <div className="flex items-baseline gap-2 min-w-0">
          <Link href="/" className="font-bold text-lg tracking-tight shrink-0">
            MANGAL<span className="text-[var(--color-accent)]">.</span>
          </Link>
          <span className="text-xs sm:text-sm text-ink/55 truncate">日本の漫画データベース</span>
        </div>
        {/* 右端 = ≡メニュー(2026-08-12 ユーザ裁定: 全ページ「ヘッダー右端」に統一) */}
        <SiteMenu />
      </div>
    </header>
  );
}

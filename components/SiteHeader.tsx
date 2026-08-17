import Link from "next/link";
import SiteMenu from "@/components/SiteMenu";

/** 共通ヘッダー(2026-08-17 案D採用でホームも復帰):
 *  一時期ホームだけE型ステータスバー(MANGAL_OS)に差し替えたが、ユーザ裁定=案Dで
 *  全ページ旧ヘッダーに統一。日付はホームのマーキー帯先頭が担う(MarqueeDate)。 */
export default function SiteHeader() {
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

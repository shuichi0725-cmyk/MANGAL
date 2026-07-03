"use client";

import { useState } from "react";
import Link from "next/link";

/** ≡メニュー(本実装 2026-07-03): 全コーナーへのドロワー。 DesignNav右端から開く。 */
const ITEMS: Array<[string, string, string]> = [
  ["🏠", "ホーム", "/"],
  ["📋", "一覧(全作品)", "/list"],
  ["🔍", "検索・絞り込み", "/browse"],
  ["📖", "今日の一冊(毎日書評)", "/"],
  ["👥", "三世代、今日の一冊 過去ログ", "/sansedai-archive"],
  ["📝", "AI書評家リーグ(週刊)", "/column-ai-league"],
  ["🎨", "画集", "/art-books"],
  ["🔰", "使い方", "/about"],
  ["✉️", "お問い合わせ", "/contact"],
  ["📜", "利用規約", "/terms"],
  ["🔒", "プライバシー", "/privacy"],
];

export default function SiteMenu() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        aria-label="メニュー"
        onClick={() => setOpen(true)}
        className="spring-press flex flex-col items-center gap-0.5 active:scale-90"
      >
        <span className="text-[18px] leading-none">≡</span>
        <span className="text-[9px] text-ink/55">メニュー</span>
      </button>
      {open && (
        <div className="fixed inset-0 z-50" role="dialog" aria-label="サイトメニュー">
          <button
            aria-label="閉じる"
            className="absolute inset-0 bg-black/40"
            onClick={() => setOpen(false)}
          />
          <div className="absolute right-0 top-0 h-full w-[78%] max-w-[320px] overflow-y-auto bg-[var(--color-surface)] p-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <p className="text-[15px] font-extrabold">
                MANGAL<span className="text-[var(--color-accent)]">.</span> メニュー
              </p>
              <button
                onClick={() => setOpen(false)}
                aria-label="閉じる"
                className="flex h-8 w-8 items-center justify-center rounded-full text-ink/50 hover:bg-[var(--color-surface-2)]"
              >
                ×
              </button>
            </div>
            <nav className="mt-3 space-y-1">
              {ITEMS.map(([icon, label, href]) => (
                <Link
                  key={label}
                  href={href}
                  onClick={() => setOpen(false)}
                  className="spring-press flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13.5px] font-semibold hover:bg-[var(--color-surface-2)]"
                >
                  <span className="text-[17px]">{icon}</span>
                  {label}
                </Link>
              ))}
            </nav>
            <p className="mt-4 border-t border-[var(--color-line)] pt-3 text-[10px] leading-relaxed text-ink/45">
              [PR] 本サイトの店舗リンクにはアフィリエイト広告を含みます。
            </p>
          </div>
        </div>
      )}
    </>
  );
}

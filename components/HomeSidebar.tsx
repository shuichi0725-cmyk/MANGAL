"use client";

import Link from "next/link";
import { useState } from "react";

/** PC専用の左サイドバー(2026-07-06 ユーザ要望「PCは左に検索常駐」)。
 *  lg未満では非表示(モバイルは従来の1カラム)。sticky常駐。
 *  検索は /list?q= へ(ListClient が初期クエリを読む)。 */
export default function HomeSidebar({ genres }: { genres: Array<{ key: string; name: string }> }) {
  const [q, setQ] = useState("");
  return (
    <aside className="hidden lg:block w-[260px] shrink-0">
      <div className="sticky top-4 space-y-4">
        {/* 検索 */}
        <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm">
          <p className="text-[12px] font-extrabold text-ink/70">🔍 さがす</p>
          <form action="/list" method="GET" className="mt-2">
            <input
              name="q"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="題名・よみ・著者…"
              className="w-full rounded-full border border-[var(--color-line)] bg-white px-3.5 py-1.5 text-[13px] outline-none focus:border-[var(--color-accent)]"
            />
            <button
              type="submit"
              className="spring-press mt-2 w-full rounded-full bg-[var(--color-accent)] py-1.5 text-[12px] font-bold text-white"
            >
              検索
            </button>
          </form>
          <div className="mt-2 grid grid-cols-2 gap-1.5 text-[11px]">
            <Link href="/list" className="spring-press rounded-lg border border-[var(--color-line)] px-2 py-1.5 text-center">📋 一覧表</Link>
            <Link href="/browse" className="spring-press rounded-lg border border-[var(--color-line)] px-2 py-1.5 text-center">🎚️ 絞り込み</Link>
          </div>
        </div>
        {/* ジャンル */}
        <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm">
          <p className="text-[12px] font-extrabold text-ink/70">🏷️ ジャンルから</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {genres.map((g) => (
              <Link
                key={g.key}
                href={`/genre/${g.key}`}
                className="spring-press rounded-full border border-[var(--color-line)] bg-[var(--color-surface-2)]/60 px-2.5 py-1 text-[11px] text-ink/80 hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
              >
                {g.name}
              </Link>
            ))}
          </div>
        </div>
        {/* 入口 */}
        <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm">
          <p className="text-[12px] font-extrabold text-ink/70">📚 コーナー</p>
          <nav className="mt-1.5 space-y-1 text-[12px]">
            <Link href="/sansedai-archive" className="spring-press block rounded px-1.5 py-1 hover:bg-[var(--color-surface-2)]">🕘 今日の一冊 過去ログ</Link>
            <Link href="/column-ai-league" className="spring-press block rounded px-1.5 py-1 hover:bg-[var(--color-surface-2)]">📝 AI書評家リーグ</Link>
            <Link href="/art-books" className="spring-press block rounded px-1.5 py-1 hover:bg-[var(--color-surface-2)]">🎨 画集</Link>
            <Link href="/about" className="spring-press block rounded px-1.5 py-1 hover:bg-[var(--color-surface-2)]">🔰 使い方</Link>
          </nav>
        </div>
      </div>
    </aside>
  );
}

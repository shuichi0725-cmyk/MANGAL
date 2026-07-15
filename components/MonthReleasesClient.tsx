"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import CoverImage from "./CoverImage";
import MarqueeTitle from "./MarqueeTitle";

const SHOW = 12;

export type MonthPick = {
  slug: string;
  title: string;
  authors: string;
  number: number | null; // 当月に出る巻番号(リンクの #v フォーカス用)
  sub: string; // 「3巻・7/18発売」等の表示文字列(server側で組立済)
  cover: string | null;
};

/** 📦 今月の新刊の表示部(client)。★再読込ごとにランダム入替(2026-07-15 ユーザ要望=アニメコーナーと同方式)。
 *  SSR初期値=発売日順先頭12(hydration一致)→マウント後にFisher-Yatesシャッフルへ差し替え。
 *  リンクは #v<巻番号> 付き=作品ページで当月巻(最新刊)にフォーカス(旧=常に1巻表示で誤読された)。 */
export default function MonthReleasesClient({ pool }: { pool: MonthPick[] }) {
  const [picks, setPicks] = useState<MonthPick[]>(pool.slice(0, SHOW));

  useEffect(() => {
    const a = pool.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    setPicks(a.slice(0, SHOW));
  }, [pool]);

  if (picks.length === 0) return null;

  return (
    <ul className="-mx-3.5 mt-2.5 flex gap-3 overflow-x-auto px-3.5 pb-1 snap-x">
      {picks.map((r) => (
        <li key={r.slug} className="w-[96px] shrink-0 snap-start">
          <Link
            href={`/manga/${r.slug}${r.number ? `#v${r.number}` : ""}`}
            className="block group spring-press"
          >
            <div className="relative aspect-[2/3] w-full overflow-hidden rounded border border-[var(--color-line)] bg-[var(--color-surface-2)]">
              {r.cover ? (
                <CoverImage src={r.cover} alt={r.title} sizes="96px" size="card" />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center p-2 text-center text-[11px] leading-tight text-ink/45">
                  {r.title.slice(0, 28)}
                </div>
              )}
            </div>
            <MarqueeTitle text={r.title} className="mt-1 text-[12px] leading-snug text-ink/85 group-hover:text-[var(--color-accent)]" />
            <p className="truncate text-[10px] font-semibold text-[var(--color-accent)]">{r.sub}</p>
            <p className="truncate text-[10px] text-ink/50">{r.authors}</p>
          </Link>
        </li>
      ))}
    </ul>
  );
}

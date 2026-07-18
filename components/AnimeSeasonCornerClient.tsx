"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import CoverImage from "./CoverImage";
import MarqueeTitle from "./MarqueeTitle";
import { sourceLabel, type AnimeSeasonEntry } from "@/lib/animeSeason";

const SHOW = 12;

/** 今季アニメコーナーの表示部(client)。★再読込ごとにランダム入替(2026-07-12 ユーザ要望)。
 *  シャッフル=Fisher-Yates非復元抽出なので同じ作品が2つ出ることはない。
 *  SSR初期値=人気順先頭12(hydration一致)→マウント後にシャッフルへ差し替え。 */
export default function AnimeSeasonCornerClient({
  seasonKey,
  label,
  total,
  entries,
}: {
  seasonKey: string;
  label: string;
  total: number;
  entries: AnimeSeasonEntry[];
}) {
  const [picks, setPicks] = useState<AnimeSeasonEntry[]>(entries.slice(0, SHOW));

  useEffect(() => {
    const a = entries.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    setPicks(a.slice(0, SHOW));
  }, [entries]);

  if (picks.length === 0) return null;

  return (
    <section className="mt-4 px-4">
      <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm">
        <div className="flex items-baseline justify-between">
          <h2 className="text-[14px] font-extrabold">📺 {label}アニメの原作</h2>
          <Link href={`/anime/${seasonKey}`} className="text-[11px] font-semibold text-[var(--color-accent)]">
            全{total}作品 →
          </Link>
        </div>
        {/* ★scroll-pl: snapは左paddingを無視して端に吸着する→スナップ位置にも14px余白(2026-07-16 ユーザ指摘) */}
        <ul className="-mx-3.5 mt-2.5 flex gap-3 overflow-x-auto no-scrollbar px-3.5 pb-1 snap-x scroll-pl-3.5">
          {picks.map((e) => (
            <li key={e.slug} className="w-[96px] shrink-0 snap-start">
              <Link href={`/manga/${e.slug}`} className="block group spring-press">
                <div
                  className="relative overflow-hidden rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)]"
                  style={{ aspectRatio: "2 / 3" }}
                >
                  {e.cover ? (
                    <CoverImage src={e.cover} alt={e.title} sizes="96px" />
                  ) : (
                    <span className="flex h-full w-full items-center justify-center text-[10px] text-ink/40">
                      no image
                    </span>
                  )}
                  <span className="absolute left-1 top-1 rounded bg-black/60 px-1 py-0.5 text-[9px] font-semibold text-white">
                    {sourceLabel(e.source)}
                  </span>
                </div>
                <MarqueeTitle
                  text={e.title}
                  className="mt-1 text-[12px] leading-snug text-ink/85 group-hover:text-[var(--color-accent)]"
                />
              </Link>
            </li>
          ))}
        </ul>
        <p className="mt-1.5 text-right text-[10px] text-ink/40">
          <Link href="/anime" className="hover:text-[var(--color-accent)]">
            過去の季節も見る(1960年代〜) →
          </Link>
        </p>
      </div>
    </section>
  );
}

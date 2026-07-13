"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import CoverImage from "./CoverImage";
import MarqueeTitle from "./MarqueeTitle";
import { jstDayIndex } from "./SansedaiDaily";

/** 特集「週末で読み切る、全5巻以内の完結作」(2026-07-13 全面改修):
 *  旧実装は読み込み順先頭6作の固定表示で ①永遠に変わらない ②書影なし作品が出る の2重不具合。
 *  → サーバ側で書影あり候補poolを埋込み、client側で週替わりrotation(DeluxeWeeklyと同方式)。 */
export type WeekendPick = { slug: string; title: string; authors: string; cover: string };

export default function WeekendFeature({ pool }: { pool: WeekendPick[] }) {
  // SSR時は描画せずclientで週を確定(build時の週が焼き付くhydrationズレ回避)
  const [week, setWeek] = useState<number | null>(null);
  useEffect(() => setWeek(Math.floor(jstDayIndex() / 7)), []);
  if (week === null || pool.length === 0) return null;
  const N = 6;
  const start = (((week * N) % pool.length) + pool.length) % pool.length;
  const picks = Array.from({ length: Math.min(N, pool.length) }, (_, i) => pool[(start + i) % pool.length]);
  return (
    <ul className="mt-3 grid grid-cols-3 gap-3">
      {picks.map((p) => (
        <li key={p.slug}>
          <Link href={`/manga/${p.slug}`} className="spring-press group block">
            <div className="relative aspect-[2/3] w-full overflow-hidden rounded border border-[var(--color-line)] bg-[var(--color-surface-2)]">
              <CoverImage src={p.cover} alt={p.title} sizes="104px" size="card" />
            </div>
            <MarqueeTitle text={p.title} className="mt-1 text-[12px] leading-snug text-ink/85 group-hover:text-[var(--color-accent)]" />
            <p className="truncate text-[10px] text-ink/50">{p.authors}</p>
          </Link>
        </li>
      ))}
    </ul>
  );
}

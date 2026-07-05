"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import CoverImage from "./CoverImage";
import LikeButton from "./LikeButton";

/** 三世代、今日の一冊(クライアント日替わり版)。
 *  静的サイトでも毎日変わるよう、public/data/sansedai-stock.json(741件)から
 *  JST日付で各世代1件を決定的に選ぶ(= 再ビルド不要・過去ログとも同じ式で整合)。 */
export type SansedaiEntry = {
  persona: string;
  gen: number;
  slug: string;
  title: string;
  comment: string;
  cover?: string | null;
};

export function jstDayIndex(offset = 0): number {
  return Math.floor((Date.now() + 9 * 3600 * 1000) / 86400000) - offset;
}
export function jstDateStr(offset = 0): string {
  const d = new Date(Date.now() + 9 * 3600 * 1000 - offset * 86400000);
  return d.toISOString().slice(0, 10);
}
export function picksForDay(entries: SansedaiEntry[], dayIndex: number): SansedaiEntry[] {
  return [0, 1, 2]
    .map((g) => {
      const pool = entries.filter((e) => Number(e.gen) === g); // ★JSONのgenは文字列のことがある(2026-07-06型バグ修正)
      if (pool.length === 0) return null;
      return pool[((dayIndex % pool.length) + pool.length) % pool.length];
    })
    .filter(Boolean) as SansedaiEntry[];
}

let _stock: SansedaiEntry[] | null = null;
export function useSansedaiStock(): SansedaiEntry[] | null {
  const [data, setData] = useState<SansedaiEntry[] | null>(_stock);
  useEffect(() => {
    if (_stock) return;
    fetch("/data/sansedai-stock.json")
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => {
        _stock = d;
        setData(d);
      })
      .catch(() => setData([]));
  }, []);
  return data;
}

export default function SansedaiDaily() {
  const stock = useSansedaiStock();
  if (!stock || stock.length === 0) return null;
  const day = jstDayIndex();
  const picks = picksForDay(stock, day);
  const date = jstDateStr();
  return (
    <section className="mt-4 px-4">
      <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm">
        <div className="flex items-baseline justify-between">
          <h2 className="text-[14px] font-extrabold">
            👥 三世代、今日の一冊
            <span className="ml-1.5 text-[10px] font-semibold text-ink/45">{date}・毎日更新</span>
          </h2>
          <Link href="/sansedai-archive" className="text-[11px] font-semibold text-[var(--color-accent)]">
            過去ログ →
          </Link>
        </div>
        <div className="mt-2.5 space-y-2.5">
          {picks.map((p) => (
            <div key={p.gen} className="rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-2)]/40 p-2.5">
              <Link href={`/manga/${p.slug}`} className="spring-press flex gap-3">
                <div
                  className="relative shrink-0 self-start overflow-hidden rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)]"
                  style={{ width: 52, aspectRatio: "2 / 3" }}
                >
                  {p.cover ? (
                    <CoverImage src={p.cover} alt={p.title} sizes="52px" />
                  ) : (
                    <span className="flex h-full w-full items-center justify-center text-[9px] text-ink/40">no image</span>
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] font-bold text-[var(--color-accent)]">{p.persona}</p>
                  <p className="truncate text-[13px] font-bold">{p.title}</p>
                  <p className="mt-0.5 line-clamp-3 text-[11px] leading-relaxed text-ink/70">{p.comment}</p>
                </div>
              </Link>
              {/* いいね=カード欄外(フッター行・右寄せ)。flex内に置くと書影が伸縮するため */}
              <div className="mt-1.5 flex justify-end">
                <LikeButton id={`sansedai:${date}:${p.gen}`} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import CoverImage from "./CoverImage";

export type DestinyItem = { slug: string; title: string; authors: string; vols: number; cover?: string | null };

/** 運命の一冊: ★再読込ごとにランダム(2026-07-15 ユーザ要望=アニメコーナーと同方式)、↻ボタンで再抽選
 *  (候補プール埋込=通信ゼロ)。 SSR初期値=日替わり(hydration一致)→マウント後にランダムへ差し替え。
 *  出会いの確率(1/総数)を演出として表示。 */
export default function DestinyPickMock({
  items,
  initialIndex,
  total,
}: {
  items: DestinyItem[];
  initialIndex: number;
  total: number;
}) {
  const [idx, setIdx] = useState(initialIndex % items.length);
  useEffect(() => {
    setIdx(Math.floor(Math.random() * items.length));
  }, [items.length]);
  const [spins, setSpins] = useState(0);
  const m = items[idx];
  if (!m) return null;
  const pct = (100 / total).toFixed(total > 10000 ? 5 : 2);
  return (
    <div className="flex gap-3 p-3.5">
      <Link href={`/manga/${m.slug}`} className="spring-press block w-16 shrink-0">
        <div className="relative flex aspect-[2/3] items-center justify-center overflow-hidden rounded border border-[var(--color-line)] bg-[var(--color-surface-2)] p-1 text-center text-[9px] leading-tight text-ink/45">
          <span className="line-clamp-4">{m.title.slice(0, 22)}</span>
          {m.cover ? <CoverImage src={m.cover} alt={m.title} sizes="64px" /> : null}
        </div>
      </Link>
      <div className="min-w-0 flex-1 self-center">
        <p className="text-[10px] font-bold tracking-widest text-[var(--color-accent)]">🎲 運命の一冊</p>
        <Link href={`/manga/${m.slug}`} className="spring-press block">
          <p className="text-[13px] font-bold leading-snug line-clamp-2">{m.title}</p>
          <p className="text-[11px] text-ink/55">{m.authors} ・ 全{m.vols}巻</p>
        </Link>
        <p className="mt-0.5 text-[9.5px] text-ink/45">
          この出会い、{total.toLocaleString()}分の1(= {pct}%!)
          {spins > 2 ? ` ・ ${spins}回目の運命` : ""}
        </p>
      </div>
      <button
        onClick={() => {
          setIdx((p) => {
            let n = Math.floor(Math.random() * items.length);
            if (n === p) n = (n + 1) % items.length;
            return n;
          });
          setSpins((s) => s + 1);
        }}
        aria-label="もう一度引く"
        className="spring-press self-center rounded-full border border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-2 text-[15px] shadow-sm"
      >
        ↻
      </button>
    </div>
  );
}

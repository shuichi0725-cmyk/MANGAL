"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import CoverImage from "./CoverImage";
import { jstDayIndex } from "./SansedaiDaily";

/** 豪華版コーナー: 特装版・限定版(variant書影あり)を週替わりで4点showcase。
 *  ★価格は絶対に表示しない(静的価格=規約違反+誤データ [[feedback-no-static-prices]])。 */
type Dlx = { s: string; t: string; v: number | null; l: string; c: string };

export default function DeluxeWeekly() {
  const [stock, setStock] = useState<Dlx[] | null>(null);
  useEffect(() => {
    fetch("/data/deluxe-stock.json")
      .then((r) => (r.ok ? r.json() : []))
      .then(setStock)
      .catch(() => setStock([]));
  }, []);
  if (!stock || stock.length === 0) return null;
  const week = Math.floor(jstDayIndex() / 7);
  const N = 4;
  const start = ((week * N) % stock.length + stock.length) % stock.length;
  const picks = Array.from({ length: Math.min(N, stock.length) }, (_, i) => stock[(start + i) % stock.length]);
  return (
    <section className="mt-4 px-4">
      <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm">
        <h2 className="text-[14px] font-extrabold">
          🎁 今週の特装版・限定版
          <span className="ml-1.5 text-[10px] font-semibold text-ink/45">週替わり</span>
        </h2>
        <div className="mt-2.5 grid grid-cols-4 gap-2.5">
          {picks.map((p) => (
            <Link key={`${p.s}-${p.v}-${p.l}`} href={`/manga/${p.s}`} className="spring-press block">
              <div className="relative overflow-hidden rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)]" style={{ aspectRatio: "2 / 3" }}>
                <CoverImage src={p.c} alt={`${p.t} ${p.l}`} sizes="120px" />
              </div>
              <p className="mt-1 truncate text-[10.5px] font-semibold">{p.t}{p.v ? ` ${p.v}巻` : ""}</p>
              <p className="truncate text-[9.5px] text-ink/50">{p.l}</p>
            </Link>
          ))}
        </div>
        <p className="mt-2 text-[10px] text-ink/45">フィギュア・DVD・小冊子つきなどの豪華版。各作品ページの巻詳細から購入先へ。</p>
      </div>
    </section>
  );
}

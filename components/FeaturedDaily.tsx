"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import CoverImage from "./CoverImage";
import LikeButton from "./LikeButton";
import { jstDayIndex, jstDateStr } from "./SansedaiDaily";

/** 今日の一冊(毎日書評)。 featured-stock.json(厳選+書評blurb)から JST日付で1冊。 再ビルド不要。 */
type Featured = { slug: string; title: string; author?: string; blurb: string; cover?: string | null };

export default function FeaturedDaily() {
  const [stock, setStock] = useState<Featured[] | null>(null);
  useEffect(() => {
    fetch("/data/featured-stock.json")
      .then((r) => (r.ok ? r.json() : []))
      .then(setStock)
      .catch(() => setStock([]));
  }, []);
  if (!stock || stock.length === 0) return null;
  const day = jstDayIndex();
  const pick = stock[((day % stock.length) + stock.length) % stock.length];
  const date = jstDateStr();
  return (
    <section className="mt-4 px-4">
      <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm">
        <div className="flex items-baseline justify-between">
          <h2 className="text-[14px] font-extrabold">
            📖 今日の一冊
            <span className="ml-1.5 text-[10px] font-semibold text-ink/45">{date}・毎日書評</span>
          </h2>
        </div>
        <Link href={`/manga/${pick.slug}`} className="spring-press mt-2.5 flex gap-3">
          <div
            className="relative shrink-0 self-start overflow-hidden rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)]"
            style={{ width: 72, aspectRatio: "2 / 3" }}
          >
            {pick.cover ? (
              <CoverImage src={pick.cover} alt={pick.title} sizes="72px" />
            ) : (
              <span className="flex h-full w-full items-center justify-center text-[9px] text-ink/40">no image</span>
            )}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[14px] font-bold leading-snug">{pick.title}</p>
            {pick.author && <p className="text-[11px] text-ink/55">{pick.author}</p>}
            <p className="mt-1 line-clamp-4 text-[11.5px] leading-relaxed text-ink/75">{pick.blurb}</p>
          </div>
        </Link>
        {/* いいね=カード欄外(フッター行・右寄せ) */}
        <div className="mt-1.5 flex justify-end">
          <LikeButton id={`featured:${date}`} />
        </div>
      </div>
    </section>
  );
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import CoverImage from "@/components/CoverImage";
import LikeButton from "@/components/LikeButton";
import { jstDayIndex } from "@/components/SansedaiDaily";

/** 今日の一冊 過去ログ: FeaturedDaily と同じ選定式(day % stock.length)で過去14日分を再現。 */
type Featured = { slug: string; title: string; author?: string; blurb: string; cover?: string | null };

function dateStrFor(offset: number): string {
  const jst = new Date(Date.now() + 9 * 3600_000 - offset * 86400_000);
  return jst.toISOString().slice(0, 10);
}

export default function ArchiveClient() {
  const [stock, setStock] = useState<Featured[] | null>(null);
  useEffect(() => {
    fetch("/data/featured-stock.json")
      .then((r) => (r.ok ? r.json() : []))
      .then(setStock)
      .catch(() => setStock([]));
  }, []);
  if (!stock || stock.length === 0) return <p className="text-[13px] text-ink/60">読み込み中…</p>;
  const today = jstDayIndex();
  const days = Array.from({ length: 14 }, (_, off) => off);
  return (
    <div className="space-y-3">
      {days.map((off) => {
        const day = today - off;
        const p = stock[(((day % stock.length) + stock.length) % stock.length)];
        const date = dateStrFor(off);
        return (
          <div key={off} className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3 shadow-sm">
            <p className="text-[11px] font-bold text-ink/50">
              {date}
              {off === 0 && <span className="ml-1.5 text-[10px] font-semibold text-[var(--color-accent)]">today</span>}
            </p>
            <Link href={`/manga/${p.slug}`} className="spring-press mt-2 flex gap-3">
              <div
                className="relative shrink-0 self-start overflow-hidden rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)]"
                style={{ width: 56, aspectRatio: "2 / 3" }}
              >
                {p.cover ? (
                  <CoverImage src={p.cover} alt={p.title} sizes="56px" />
                ) : (
                  <span className="flex h-full w-full items-center justify-center text-[9px] text-ink/40">no image</span>
                )}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13.5px] font-bold">{p.title}</p>
                {p.author && <p className="text-[11px] text-ink/55">{p.author}</p>}
                <p className="mt-0.5 line-clamp-3 text-[11px] leading-relaxed text-ink/70">{p.blurb}</p>
              </div>
            </Link>
            <div className="mt-1.5 flex justify-end">
              <LikeButton id={`featured:${date}`} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

"use client";

import Link from "next/link";
import CoverImage from "./CoverImage";
import LikeButton from "./LikeButton";
import { jstDayIndex, jstDateStr, picksForDay, useSansedaiStock } from "./SansedaiDaily";

/** 今日の一冊(毎日更新)。 ★三世代の案内人3人分=別作品3冊/日(2026-07-06 ユーザ指摘で1冊→3冊に復元)。
 *  sansedai-stock.json(737件・persona付き)から JST日付×世代ごとに決定的に選ぶ。 再ビルド不要。 */
export default function FeaturedDaily() {
  const stock = useSansedaiStock();
  if (!stock || stock.length === 0) return null;
  const day = jstDayIndex();
  const picks = picksForDay(stock, day);
  if (picks.length === 0) return null;
  const date = jstDateStr();
  return (
    <section className="mt-4 px-4">
      <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm">
        <div className="flex items-baseline justify-between">
          <h2 className="text-[14px] font-extrabold">
            📖 今日の一冊
            <span className="ml-1.5 text-[10px] font-semibold text-ink/45">{date}・毎日更新</span>
          </h2>
          <Link href="/sansedai-archive" className="text-[11px] font-semibold text-[var(--color-accent)]">
            過去ログ →
          </Link>
        </div>
        <ul className="mt-2.5 space-y-3">
          {picks.map((p) => (
            <li key={`${p.gen}-${p.slug}`} className="border-t border-[var(--color-line)]/60 pt-2.5 first:border-t-0 first:pt-0">
              <p className="text-[11px] font-bold text-[var(--color-accent)]">{p.persona}</p>
              <Link href={`/manga/${p.slug}`} className="spring-press mt-1 flex gap-3">
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
                  <p className="text-[13px] font-bold leading-snug">{p.title}</p>
                  <p className="mt-0.5 line-clamp-3 text-[11.5px] leading-relaxed text-ink/75">{p.comment}</p>
                </div>
              </Link>
              <div className="mt-1 flex justify-end">
                <LikeButton id={`sansedai:${date}:${p.gen}`} />
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

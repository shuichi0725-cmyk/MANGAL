"use client";

import Link from "next/link";
import CoverImage from "./CoverImage";
import LikeButton from "./LikeButton";
import { jstDayIndex, jstDateStr, picksForDay, useSansedaiStock, personaName } from "./SansedaiDaily";

/** 今日の一冊(毎日更新・3人分/日)。
 *  ★日替わり分散配置(2026-07-06 ユーザ要望): 3冊の「まとまり方と場所」が日ごとに変わる。
 *  Design11 に slot=0..2 の3箇所を用意し、日替わりパターンで配る:
 *    [3] / [1,1,1] / [1,2] / [2,1] (= 3人一緒・バラバラ・1+2・2+1)。間には他コーナーが挟まる。 */
const PATTERNS: number[][] = [[3], [1, 1, 1], [1, 2], [2, 1]];

export default function FeaturedDaily({ slot = 0 }: { slot?: number }) {
  const stock = useSansedaiStock();
  if (!stock || stock.length === 0) return null;
  const day = jstDayIndex();
  const picks = picksForDay(stock, day);
  if (picks.length === 0) return null;
  const pattern = PATTERNS[((day % PATTERNS.length) + PATTERNS.length) % PATTERNS.length];
  const count = pattern[slot] ?? 0;
  if (count === 0) return null;
  const offset = pattern.slice(0, slot).reduce((a, b) => a + b, 0);
  const mine = picks.slice(offset, offset + count);
  if (mine.length === 0) return null;
  const date = jstDateStr();
  const isFirst = offset === 0;
  return (
    <section className="mt-4 px-4">
      <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm">
        <div className="flex items-baseline justify-between">
          <h2 className="text-[14px] font-extrabold">
            📖 今日の一冊
            {isFirst && <span className="ml-1.5 text-[10px] font-semibold text-ink/45">{date}・毎日更新</span>}
          </h2>
          <Link href="/sansedai-archive" className="text-[11px] font-semibold text-[var(--color-accent)]">
            過去ログ →
          </Link>
        </div>
        <ul className="mt-2.5 space-y-3">
          {mine.map((p) => (
            <li key={`${p.gen}-${p.slug}`} className="border-t border-[var(--color-line)]/60 pt-2.5 first:border-t-0 first:pt-0">
              <p className="text-[11px] font-bold text-[var(--color-accent)]">{personaName(p.persona)}</p>
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
                  {/* ★文字切れ禁止(line-clamp除去 2026-07-06): コメントは全文表示 */}
                  <p className="mt-0.5 text-[11.5px] leading-relaxed text-ink/75">{p.comment}</p>
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

"use client";

import Link from "next/link";
import CoverImage from "@/components/CoverImage";
import LikeButton from "@/components/LikeButton";
import { useSansedaiStock, picksForDay, jstDayIndex, jstDateStr } from "@/components/SansedaiDaily";

/** 三世代、今日の一冊 − 過去ログ(直近14日・クライアント日付基準=本番と同じ選定式)。 */
export default function ArchiveClient() {
  const stock = useSansedaiStock();
  if (!stock || stock.length === 0) return <p className="px-4 py-8 text-sm text-ink/50">読み込み中…</p>;
  const today = jstDayIndex();
  const days = Array.from({ length: 14 }, (_, i) => i); // 0=今日
  return (
    <div className="space-y-6 px-4 pb-12">
      {days.map((off) => {
        const picks = picksForDay(stock, today - off);
        const date = jstDateStr(off);
        return (
          <section key={off}>
            <h2 className="text-[13px] font-extrabold text-ink/70">
              {date}
              {off === 0 && <span className="ml-1.5 text-[10px] font-semibold text-[var(--color-accent)]">today</span>}
            </h2>
            <div className="mt-2 space-y-2.5">
              {picks.map((p) => (
                <div key={`${off}-${p.gen}`} className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3 shadow-sm">
                  <Link href={`/manga/${p.slug}`} className="spring-press flex gap-3">
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
                      <p className="text-[10px] font-bold text-[var(--color-accent)]">{p.persona}</p>
                      <p className="truncate text-[13.5px] font-bold">{p.title}</p>
                      <p className="mt-0.5 line-clamp-3 text-[11px] leading-relaxed text-ink/70">{p.comment}</p>
                    </div>
                  </Link>
                  {/* いいね=カード欄外(フッター行・右寄せ) */}
                  <div className="mt-1.5 flex justify-end">
                    <LikeButton id={`sansedai:${date}:${p.gen}`} />
                  </div>
                </div>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

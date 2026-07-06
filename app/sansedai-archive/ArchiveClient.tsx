"use client";

import Link from "next/link";
import CoverImage from "@/components/CoverImage";
import LikeButton from "@/components/LikeButton";
import { jstDayIndex, picksForDay, useSansedaiStock, personaName, PERSONA_BIOS } from "@/components/SansedaiDaily";

/** 今日の一冊 過去ログ: ★三世代3人分/日をホームと同じ式(picksForDay)で過去14日分再現
 *  (2026-07-06 ユーザ指摘で1人分→3人分に復元)。 */

function dateStrFor(offset: number): string {
  const jst = new Date(Date.now() + 9 * 3600_000 - offset * 86400_000);
  return jst.toISOString().slice(0, 10);
}

export default function ArchiveClient() {
  const stock = useSansedaiStock();
  if (!stock || stock.length === 0) return <p className="px-4 text-[13px] text-ink/60">読み込み中…</p>;
  const today = jstDayIndex();
  const days = Array.from({ length: 14 }, (_, off) => off);
  const personas = Array.from(new Set(stock.map((e) => personaName(e.persona))));
  return (
    <div className="space-y-3 px-4 pb-8">
      {/* 案内人プロフィール(2026-07-06 ユーザ要望: 冒頭に全員分) */}
      <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm">
        <h2 className="text-[13px] font-extrabold">案内人</h2>
        <ul className="mt-2 space-y-1.5">
          {personas.map((n) => (
            <li key={n} className="flex gap-2 text-[12px] leading-relaxed">
              <span className="shrink-0 font-bold text-[var(--color-accent)]">{n}</span>
              <span className="text-ink/70">{PERSONA_BIOS[n] ?? ""}</span>
            </li>
          ))}
        </ul>
      </div>
      {days.map((off) => {
        const day = today - off;
        const picks = picksForDay(stock, day);
        const date = dateStrFor(off);
        return (
          <div key={off} className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3 shadow-sm">
            <p className="text-[11px] font-bold text-ink/50">
              {date}
              {off === 0 && <span className="ml-1.5 text-[10px] font-semibold text-[var(--color-accent)]">today</span>}
            </p>
            <ul className="mt-1 space-y-2.5">
              {picks.map((p) => (
                <li key={`${p.gen}-${p.slug}`} className="border-t border-[var(--color-line)]/60 pt-2 first:border-t-0 first:pt-1">
                  <p className="text-[10.5px] font-bold text-[var(--color-accent)]">{personaName(p.persona)}</p>
                  <Link href={`/manga/${p.slug}`} className="spring-press mt-1 flex gap-3">
                    <div
                      className="relative shrink-0 self-start overflow-hidden rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)]"
                      style={{ width: 48, aspectRatio: "2 / 3" }}
                    >
                      {p.cover ? (
                        <CoverImage src={p.cover} alt={p.title} sizes="48px" />
                      ) : (
                        <span className="flex h-full w-full items-center justify-center text-[9px] text-ink/40">no image</span>
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-bold leading-snug">{p.title}</p>
                      <p className="mt-0.5 text-[11px] leading-relaxed text-ink/70">{p.comment}</p>
                    </div>
                  </Link>
                  <div className="mt-1 flex justify-end">
                    <LikeButton id={`sansedai:${date}:${p.gen}`} />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

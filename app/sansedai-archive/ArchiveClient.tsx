"use client";

import Link from "next/link";
import CoverImage from "@/components/CoverImage";
import LikeButton from "@/components/LikeButton";
import { jstDayIndex, picksForDay, useSansedaiStock, personaName, PERSONA_BIOS } from "@/components/SansedaiDaily";

/** 今日の一冊 過去ログ: ★三世代3人分/日をホームと同じ式(picksForDay)で再現。
 *  (2026-07-06 ユーザ指摘で1人分→3人分に復元)
 *  ★2026-07-30 改訂: コーナー開始日=2026-06-01 に固定し、月単位セクションで表示
 *  (当月のみ展開・過去月は折りたたみ)。14日打ち切りの平置きは廃止(長くなりすぎるため)。
 *  注: picksはstock(sansedai-stock.json)と式から決定的に再現するため、stock改版時は
 *  過去日の表示も現stockで引き直される(=ログの凍結保存ではない)。 */

const EPOCH_DAY = Date.UTC(2026, 5, 1) / 86400000; // 2026-06-01(JST) のdayIndex

function dateStrOf(dayIndex: number): string {
  return new Date(dayIndex * 86400000).toISOString().slice(0, 10);
}

export default function ArchiveClient() {
  const stock = useSansedaiStock();
  if (!stock || stock.length === 0) return <p className="px-4 text-[13px] text-ink/60">読み込み中…</p>;
  const today = jstDayIndex();
  // 今日→2026-06-01 の全日を月ごとに束ねる(新しい月が先)
  const months: { key: string; label: string; days: number[] }[] = [];
  for (let day = today; day >= EPOCH_DAY; day--) {
    const date = dateStrOf(day);
    const key = date.slice(0, 7);
    let m = months[months.length - 1];
    if (!m || m.key !== key) {
      m = { key, label: `${key.slice(0, 4)}年${Number(key.slice(5, 7))}月`, days: [] };
      months.push(m);
    }
    m.days.push(day);
  }
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
      {months.map((m, mi) => (
        <details
          key={m.key}
          open={mi === 0}
          className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] shadow-sm"
        >
          <summary className="cursor-pointer select-none px-3.5 py-2.5 text-[13px] font-extrabold">
            {m.label}
            <span className="ml-1.5 text-[11px] font-semibold text-ink/45">{m.days.length}日分</span>
          </summary>
          <div className="space-y-3 px-3 pb-3">
            {m.days.map((day) => {
              const picks = picksForDay(stock, day);
              const date = dateStrOf(day);
              return (
                <div key={day} className="rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-2)]/40 p-3">
                  <p className="text-[11px] font-bold text-ink/50">
                    {date}
                    {day === today && <span className="ml-1.5 text-[10px] font-semibold text-[var(--color-accent)]">today</span>}
                  </p>
                  <ul className="mt-1 space-y-2.5">
                    {picks.map((p) => (
                      <li key={`${p.gen}-${p.slug}`} className="border-t border-[var(--color-line)]/60 pt-2 first:border-t-0 first:pt-1">
                        <div className="flex items-center justify-between">
                          <p className="text-[10.5px] font-bold text-[var(--color-accent)]">{personaName(p.persona)}</p>
                          <LikeButton id={`sansedai:${date}:${p.gen}`} />
                        </div>
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
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        </details>
      ))}
    </div>
  );
}

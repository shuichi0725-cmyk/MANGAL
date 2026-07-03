"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

/** タイムマシン: 「◯年前の今日」発売の本。全期間化した発売カレンダーJSONを流用(再ビルド不要)。
 *  calendar/release item = [slug, vol, title](title埋め込み済) */
type Item = [string, number | null, string?];
type MonthData = { days: Record<string, Item[]>; unknown: Item[] };

const OFFSETS = [10, 20, 30];

export default function TimeMachine() {
  const [rows, setRows] = useState<{ n: number; year: number; items: Item[] }[] | null>(null);
  useEffect(() => {
    const jst = new Date(Date.now() + 9 * 3600_000);
    const mm = String(jst.getUTCMonth() + 1).padStart(2, "0");
    const dd = String(jst.getUTCDate()).padStart(2, "0");
    const y0 = jst.getUTCFullYear();
    Promise.all(
      OFFSETS.map(async (n) => {
        const y = y0 - n;
        try {
          const r = await fetch(`/calendar/release/${y}-${mm}.json`);
          if (!r.ok) return { n, year: y, items: [] as Item[] };
          const d: MonthData = await r.json();
          return { n, year: y, items: (d.days?.[dd] || []).slice(0, 3) };
        } catch {
          return { n, year: y, items: [] as Item[] };
        }
      })
    ).then(setRows);
  }, []);
  if (!rows || rows.every((r) => r.items.length === 0)) return null;
  return (
    <section className="mt-4 px-4">
      <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm">
        <h2 className="text-[14px] font-extrabold">
          🕰️ タイムマシン
          <span className="ml-1.5 text-[10px] font-semibold text-ink/45">◯年前の今日、発売</span>
        </h2>
        <div className="mt-2 space-y-2">
          {rows.filter((r) => r.items.length > 0).map((r) => (
            <div key={r.n}>
              <p className="text-[11px] font-bold text-[var(--color-accent)]">{r.n}年前の今日({r.year}年)</p>
              <ul className="mt-0.5 space-y-0.5">
                {r.items.map(([slug, vol, title]) => (
                  <li key={`${slug}-${vol}`}>
                    <Link href={`/manga/${slug}`} className="spring-press flex items-baseline gap-1.5 text-[12.5px]">
                      <span className="h-1 w-1 shrink-0 translate-y-[-2px] rounded-full bg-[var(--color-accent)]" />
                      <span className="min-w-0 flex-1 truncate text-ink/85">
                        {title ?? slug}
                        {vol ? <span className="text-ink/45"> {vol}巻</span> : null}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

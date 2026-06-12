"use client";

import Link from "next/link";
import { useState } from "react";

export type CalDay = { d: number; items: Array<{ slug: string; title: string; authors: string }> };

/** 発売カレンダー(クライアント島): 日付タップで直下にその日の一覧を展開。
 *  月データはビルド時にprops埋込=リクエストゼロの完全静的。 */
export default function ReleaseCalendarMock({ ym, days }: { ym: string; days: CalDay[] }) {
  const [sel, setSel] = useState<number | null>(null);
  const map = new Map(days.map((x) => [x.d, x.items]));
  const maxN = Math.max(1, ...days.map((x) => x.items.length));
  const first = new Date(`${ym}-01T00:00:00`);
  const pad = first.getDay();
  const last = new Date(Number(ym.slice(0, 4)), Number(ym.slice(5, 7)), 0).getDate();
  const selItems = sel != null ? map.get(sel) ?? [] : [];

  const cells = [];
  for (let i = 0; i < pad; i++) cells.push(<span key={`p${i}`} />);
  for (let d = 1; d <= last; d++) {
    const n = map.get(d)?.length ?? 0;
    const op = n === 0 ? 0 : 0.25 + 0.75 * (n / maxN);
    cells.push(
      <button
        key={d}
        onClick={() => setSel(sel === d ? null : d)}
        disabled={n === 0}
        className={`spring-press relative flex h-8 flex-col items-center justify-center rounded text-[10px] ${
          sel === d ? "ring-2 ring-[var(--color-accent)]" : ""
        } ${n === 0 ? "text-ink/30" : "text-ink/70"}`}
        style={n ? { backgroundColor: `color-mix(in srgb, var(--color-accent) ${Math.round(op * 28)}%, transparent)` } : undefined}
      >
        {d}
        {n > 0 && <span className="text-[8px] font-bold text-[var(--color-accent)]">{n}</span>}
      </button>,
    );
  }

  return (
    <div>
      <div className="mt-2.5 grid grid-cols-7 gap-1 text-center">
        {["日", "月", "火", "水", "木", "金", "土"].map((w) => (
          <span key={w} className="text-[9px] font-semibold text-ink/40">{w}</span>
        ))}
        {cells}
      </div>
      {sel != null && (
        <div className="mt-2.5 rounded-lg border border-[var(--color-line)] bg-[var(--color-bg)]/60 p-2.5">
          <p className="text-[11px] font-bold text-ink/70">
            {Number(ym.slice(5, 7))}月{sel}日の発売 — {selItems.length}冊
          </p>
          <ul className="mt-1.5 space-y-1">
            {selItems.map((it) => (
              <li key={it.slug}>
                <Link href={`/manga/${it.slug}`} className="spring-press flex items-baseline gap-2">
                  <span className="h-1.5 w-1.5 shrink-0 translate-y-[-1px] rounded-full bg-[var(--color-accent)]" />
                  <span className="min-w-0 flex-1 truncate text-[12.5px] text-ink/85">{it.title}</span>
                  <span className="shrink-0 text-[10px] text-ink/45">{it.authors}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="mt-2 text-[10px] text-ink/45">
        日付タップでその日の一覧 ・ 月名タップで月別ページへ(本番=過去全月分を静的生成)
      </p>
    </div>
  );
}

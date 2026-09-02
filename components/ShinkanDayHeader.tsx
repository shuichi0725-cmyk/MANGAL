"use client";

import { dotGothic } from "@/lib/fonts";

/** 高速スムーススクロール(既定のsmoothは長距離で遅い→~8px/msの短時間アニメ。
 *  ユーザ要望「高速スクロールする感じ」= 旧ShinkanClient から移植 2026-09-01) */
export function fastScrollTo(el: HTMLElement) {
  const target = el.getBoundingClientRect().top + window.scrollY;
  const start = window.scrollY;
  const dist = target - start;
  const dur = Math.min(900, Math.max(300, Math.abs(dist) / 8));
  const t0 = performance.now();
  const ease = (t: number) => 1 - Math.pow(1 - t, 3);
  const step = (now: number) => {
    const p = Math.min(1, (now - t0) / dur);
    window.scrollTo(0, start + dist * ease(p));
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/** 日付見出し(sticky)+日送りボタン(2026-08-27 ユーザ要望「日付と冊数の間に前の日/次の日」)。
 *  見た目は旧ShinkanClient のまま。h2 を持つのでSEO上も見出しになる。 */
export default function ShinkanDayHeader({
  label,
  sub,
  count,
  prevId,
  nextId,
}: {
  label: string;
  sub?: string;
  count: number;
  prevId?: string;
  nextId?: string;
}) {
  const go = (id?: string) => {
    if (!id) return;
    const el = document.getElementById(id);
    if (el) fastScrollTo(el);
  };
  return (
    <div className="sticky top-0 z-10 flex items-center gap-2 border-b-2 border-[var(--color-accent)] bg-[color-mix(in_srgb,var(--color-bg)_92%,transparent)] px-3.5 pb-1.5 pt-2 backdrop-blur-[2px]">
      <h2 className={`${dotGothic.className} text-[19px] font-black leading-none text-[var(--color-accent)]`}>{label}</h2>
      {sub ? <span className="text-[11px] text-ink/55">({sub})</span> : null}
      <span className="mx-auto flex items-center gap-1.5">
        {prevId && (
          <button type="button" onClick={() => go(prevId)} className="spring-press border border-[var(--color-line)] px-2 py-0.5 text-[10.5px] font-bold text-ink/65">
            ↑前の日
          </button>
        )}
        {nextId && (
          <button type="button" onClick={() => go(nextId)} className="spring-press border border-[var(--color-line)] px-2 py-0.5 text-[10.5px] font-bold text-ink/65">
            ↓次の日
          </button>
        )}
      </span>
      <span className="text-[11px] text-ink/45">{count}冊</span>
    </div>
  );
}

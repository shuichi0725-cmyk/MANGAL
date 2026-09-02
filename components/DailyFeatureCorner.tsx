"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

/** 日替わり特集コーナーのホーム導線(2026-08-03 ユーザ採用)。
 *  見た目は日替わりで 案A(帯バナー=書影ファン) / 案B(チケット=半券)。色は題材色(stock側で決定)。
 *  データ= /data/tokushu/<date>.json(自己完結: 題・著者・書影同梱 = 索引に依存しない。
 *  _gen-daily-feature.py が45日先まで凍結stock)。 */

/** items の1件 = [slug, 題, 著者, 書影URL, 開始年, 終了年|null, status] */
export type TokushuItem = [string, string, string, string | null, number | null, number | null, string | null];
export type TokushuDay = {
  t: string; lead: string; n: number; q: string;
  sty: { l: "A" | "B"; p: 1 | 2 };
  c: { a: string; d: string };
  items: TokushuItem[];
};
export type TokushuIndex = { days: Record<string, { t: string; n: number; sty: { l: string; p: number }; c: { a: string; d: string } }> };

const _dayCache = new Map<string, TokushuDay | null>();
export async function fetchTokushuDay(date: string): Promise<TokushuDay | null> {
  if (_dayCache.has(date)) return _dayCache.get(date) ?? null;
  const d = await fetch(`/data/tokushu/${date}.json`)
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null);
  _dayCache.set(date, d);
  return d;
}

let _idx: TokushuIndex | null = null;
export async function fetchTokushuIndex(): Promise<TokushuIndex | null> {
  if (_idx) return _idx;
  _idx = await fetch("/data/tokushu/index.json")
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null);
  return _idx;
}

/** JSTの今日(発売日と同じ基準=端末TZ非依存)。 */
export function jstToday(): string {
  return new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
}

export default function DailyFeatureCorner() {
  const [day, setDay] = useState<TokushuDay | null>(null);
  useEffect(() => {
    fetchTokushuDay(jstToday()).then(setDay);
  }, []);
  if (!day) return null;

  const covers = day.items.slice(0, 5).map((it) => it[3]).filter(Boolean) as string[];
  const d = new Date(Date.now() + 9 * 3600 * 1000);
  const md = `${d.getUTCMonth() + 1}/${d.getUTCDate()}`;
  const wk = "日月火水木金土"[d.getUTCDay()];

  if (day.sty.l === "A") {
    // 案A: 帯バナー(書影ファン+特集帯)
    return (
      <section className="mt-4 px-4">
        <Link
          href="/tokushu"
          className="spring-press relative flex items-center gap-3 overflow-hidden rounded-lg border border-[var(--color-line)] p-3 shadow-[var(--shadow-lift)]"
          style={{ borderLeft: `5px solid ${day.c.a}`, background: `linear-gradient(105deg,var(--color-surface) 55%, ${day.c.a}14)` }}
        >
          <div className="relative h-24 w-[104px] shrink-0">
            {covers.slice(0, 3).map((c, i) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                key={i}
                src={c}
                alt=""
                loading="lazy"
                className="absolute h-[86px] w-[60px] rounded-[3px] border-2 border-white bg-white object-cover shadow-[0_3px_8px_rgba(15,17,21,.28)]"
                style={{ left: i * 24, top: [6, 2, 7][i], transform: `rotate(${[-8, 1, 9][i]}deg)`, zIndex: i + 1 }}
              />
            ))}
          </div>
          <div className="min-w-0">
            <span className="inline-block rounded-full px-2.5 py-0.5 text-[10px] font-extrabold tracking-wider text-white" style={{ background: day.c.a }}>
              📅 本日の特集
            </span>
            <h3 className="mt-1 text-[18px] font-black leading-snug">{day.t}</h3>
            <p className="mt-0.5 text-[11px] text-ink/55">人気の{day.n}作品 ｜ 毎日日替わり</p>
          </div>
          <span className="ml-auto shrink-0 text-xl" style={{ color: day.c.a }}>›</span>
        </Link>
      </section>
    );
  }

  // 案B: チケット(半券つき)
  return (
    <section className="mt-4 px-4">
      <Link href="/tokushu" className="spring-press relative flex overflow-hidden rounded-[10px] border border-[var(--color-line)] bg-[var(--color-surface)] shadow-[var(--shadow-lift)]">
        <div className="relative flex-1 border-r-2 border-dashed border-ink/20 p-3">
          <span className="absolute -top-2 right-[-8px] h-4 w-4 rounded-full border border-[var(--color-line)] bg-[var(--color-paper)]" />
          <span className="absolute -bottom-2 right-[-8px] h-4 w-4 rounded-full border border-[var(--color-line)] bg-[var(--color-paper)]" />
          <p className="text-[10px] font-bold tracking-[.2em] text-ink/50">DAILY FEATURE ─ {md} ({wk})</p>
          <h3 className="mb-2 mt-0.5 text-[17px] font-black">{day.t}</h3>
          <div className="flex gap-1">
            {covers.slice(0, 4).map((c, i) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img key={i} src={c} alt="" loading="lazy" className="h-12 w-[34px] rounded-[2px] border border-[var(--color-line)] bg-white object-cover" />
            ))}
            <span className="flex h-12 w-[34px] items-center justify-center rounded-[2px] bg-[var(--color-surface-2)] text-[10px] font-extrabold text-ink/50">
              +{Math.max(0, day.n - 4)}
            </span>
          </div>
        </div>
        <div
          className="flex w-[72px] shrink-0 flex-col items-center justify-center gap-1 text-white"
          style={{ background: `repeating-linear-gradient(-45deg, ${day.c.a}, ${day.c.a} 6px, ${day.c.d} 6px, ${day.c.d} 12px)` }}
        >
          <span className="text-[9px] tracking-[.15em] opacity-85">No.{md.replace("/", "")}</span>
          <span className="text-[14px] font-black tracking-[.2em] [writing-mode:vertical-rl]">読む</span>
        </div>
      </Link>
    </section>
  );
}

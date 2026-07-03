"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import CoverImage from "./CoverImage";

/** 周年コーナー: 「今日で連載開始◯◯年」— 1巻発売日(完全日付)が今日と同じ月日の作品から、
 *  切りの良い周年(10の倍数>5の倍数>その他、N>=5)を優先して1作。データ=anniversaries.json(週次再生成)。 */
type Ann = { s: string; t: string; y: number; c: string };

function jstToday(): { mmdd: string; year: number } {
  const jst = new Date(Date.now() + 9 * 3600_000);
  return { mmdd: jst.toISOString().slice(5, 10), year: jst.getUTCFullYear() };
}

export default function AnniversaryDaily() {
  const [data, setData] = useState<Record<string, Ann[]> | null>(null);
  useEffect(() => {
    fetch("/data/anniversaries.json")
      .then((r) => (r.ok ? r.json() : {}))
      .then(setData)
      .catch(() => setData({}));
  }, []);
  if (!data) return null;
  const { mmdd, year } = jstToday();
  const todays = (data[mmdd] || [])
    .map((a) => ({ ...a, n: year - a.y }))
    .filter((a) => a.n >= 5);
  if (todays.length === 0) return null;
  const rank = (n: number) => (n % 10 === 0 ? 0 : n % 5 === 0 ? 1 : 2);
  todays.sort((a, b) => rank(a.n) - rank(b.n) || b.n - a.n);
  const pick = todays[0];
  return (
    <section className="mt-4 px-4">
      <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm">
        <h2 className="text-[14px] font-extrabold">
          🎂 今日で{pick.n}周年
          <span className="ml-1.5 text-[10px] font-semibold text-ink/45">1巻発売 {pick.y}年{mmdd.replace("-", "月")}日</span>
        </h2>
        <Link href={`/manga/${pick.s}`} className="spring-press mt-2.5 flex gap-3">
          <div
            className="relative shrink-0 self-start overflow-hidden rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)]"
            style={{ width: 64, aspectRatio: "2 / 3" }}
          >
            <CoverImage src={pick.c} alt={pick.t} sizes="64px" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[14px] font-bold leading-snug">{pick.t}</p>
            <p className="mt-1 text-[11.5px] leading-relaxed text-ink/70">
              第1巻の発売から今日でちょうど{pick.n}年。ページで全巻をたどれます。
            </p>
          </div>
        </Link>
        {todays.length > 1 && (
          <p className="mt-2 text-[10.5px] text-ink/45">
            きょうが記念日の作品 ほか{todays.length - 1}作
          </p>
        )}
      </div>
    </section>
  );
}

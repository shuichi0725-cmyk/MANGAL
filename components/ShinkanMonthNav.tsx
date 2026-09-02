import Link from "next/link";
import { ymLabel } from "@/lib/shinkanDates";

/** 年×月のチップ(静的リンク=クロール導線。旧ShinkanClient の年月ボタンと同じ見た目・2026-08-31 ユーザ要望の2段ナビ)。
 *  current の年を先頭に開き、他の年は折りたたまず並べる(月が増えても指定しやすい)。 */
export default function ShinkanMonthNav({ months, current }: { months: string[]; current?: string }) {
  const byYear = new Map<string, string[]>();
  for (const ym of months) byYear.set(ym.slice(0, 4), [...(byYear.get(ym.slice(0, 4)) ?? []), ym]);
  const chip = (active: boolean) =>
    `shrink-0 px-2.5 py-1 text-[11.5px] font-black ${active ? "bg-[var(--color-accent)] text-[#0d0d0d]" : "border border-[var(--color-line)] text-ink/70"}`;
  return (
    <nav aria-label="月別の新刊一覧" className="mt-2 text-[12px]">
      <div className="flex flex-wrap gap-x-3 gap-y-1 font-bold">
        <Link href="/shinkan/this-week" className="underline">今週の新刊</Link>
        <Link href="/shinkan/next-month" className="underline">来月の新刊</Link>
        <Link href="/shinkan" className="underline">今月の新刊</Link>
      </div>
      {[...byYear.entries()].map(([y, yms]) => (
        <div key={y} className="mt-1.5 flex items-center gap-1.5 overflow-x-auto pb-0.5">
          <span className="shrink-0 px-1 text-[11.5px] font-black text-ink/60">{y}年</span>
          {yms.map((ym) => (
            <Link key={ym} href={`/shinkan/${ym}`} aria-current={ym === current ? "page" : undefined} className={chip(ym === current)}>
              {Number(ym.slice(5))}月
            </Link>
          ))}
        </div>
      ))}
      <p className="mt-1 text-[11px] text-ink/45">
        {months.length ? `${ymLabel(months[0])}〜${ymLabel(months[months.length - 1])}の漫画新刊発売日を月ごとに掲載` : ""}
      </p>
    </nav>
  );
}

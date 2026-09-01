import Link from "next/link";
import { ymLabel } from "@/lib/shinkanData";

/** 月別ページへの静的リンク群(クロール導線。ShinkanClient のタブは client 描画で Google に見えない) */
export default function ShinkanMonthNav({ months, current }: { months: string[]; current?: string }) {
  const byYear = new Map<string, string[]>();
  for (const ym of months) byYear.set(ym.slice(0, 4), [...(byYear.get(ym.slice(0, 4)) ?? []), ym]);
  return (
    <nav aria-label="月別の新刊一覧" className="mx-auto w-full max-w-[720px] px-4 py-3 text-[12px]">
      <div className="mb-1 flex flex-wrap gap-x-3 gap-y-1 font-bold">
        <Link href="/shinkan/this-week" className="underline">今週の新刊</Link>
        <Link href="/shinkan/next-month" className="underline">来月の新刊</Link>
        <Link href="/shinkan" className="underline">今月の新刊(月切替)</Link>
      </div>
      {[...byYear.entries()].map(([y, yms]) => (
        <div key={y} className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <span className="font-black text-ink/60">{y}年</span>
          {yms.map((ym) => (
            <Link key={ym} href={`/shinkan/${ym}`} aria-current={ym === current ? "page" : undefined}
              className={`underline ${ym === current ? "font-black text-[var(--color-accent)]" : "text-ink/75"}`}>
              {Number(ym.slice(5))}月
            </Link>
          ))}
        </div>
      ))}
      <p className="mt-1 text-[11px] text-ink/45">{months.length ? `${ymLabel(months[0])}〜${ymLabel(months[months.length - 1])}の漫画新刊発売日を月ごとに掲載` : ""}</p>
    </nav>
  );
}

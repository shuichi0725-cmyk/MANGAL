import Link from "next/link";
import { ymLabel } from "@/lib/shinkanDates";

/** 年行+月行の固定2行ナビ(静的リンク=クロール導線。2026-09-02 ユーザ裁定: 年が増えても高さが増えない形)。
 *  - 年行: JSONに在る年をチップで1行。表示中の年が active。他年の飛び先=同じ月(無ければ最寄り月)
 *  - 月行: 表示中の年の月だけ。折り返さず横スクロール(ユーザ裁定)。★初期表示で当月チップが見える位置へ
 *    inline script が scrollLeft を合わせる(hydration前に走る=ちらつき無し。JS無効なら先頭から見えるだけ)
 *  current=自頁の月(aria-current)。月頁でない頁(今週)は focus で「今月」を渡す(activeにはしない・年選択と初期位置だけ) */
export default function ShinkanMonthNav({ months, current, focus }: { months: string[]; current?: string; focus?: string }) {
  const byYear = new Map<string, string[]>();
  for (const ym of months) byYear.set(ym.slice(0, 4), [...(byYear.get(ym.slice(0, 4)) ?? []), ym]);
  const years = [...byYear.keys()];
  const pivot = current ?? focus ?? months[months.length - 1] ?? "";
  const year = byYear.has(pivot.slice(0, 4)) ? pivot.slice(0, 4) : years[years.length - 1];
  const yms = byYear.get(year) ?? [];
  const mm = pivot.slice(5);
  // 年チップの飛び先: 同じ月 → 無ければ最寄り(過去年=その年の最終月 / 未来年=最初の月)
  const yearHref = (y: string) => {
    const list = byYear.get(y) ?? [];
    const same = list.find((ym) => ym.slice(5) === mm);
    return `/shinkan/${same ?? (y < year ? list[list.length - 1] : list[0])}`;
  };
  // 初期スクロールの目標: 自頁の月 > focus(今月)。月行に無ければ何もしない
  const target = current ?? (focus && yms.includes(focus) ? focus : undefined);
  const chip = (active: boolean) =>
    `shrink-0 px-2.5 py-1 text-[11.5px] font-black ${active ? "bg-[var(--color-accent)] text-[#0d0d0d]" : "border border-[var(--color-line)] text-ink/70"}`;
  const ROW_ID = "shinkan-months";
  return (
    <nav aria-label="月別の新刊一覧" className="mt-2 text-[12px]">
      <div className="flex flex-wrap gap-x-3 gap-y-1 font-bold">
        <Link href="/shinkan/this-week" className="underline">今週の新刊</Link>
        <Link href="/shinkan/next-month" className="underline">来月の新刊</Link>
        <Link href="/shinkan" className="underline">今月の新刊</Link>
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5" aria-label="年">
        {years.map((y) => (
          <Link key={y} href={yearHref(y)} className={chip(y === year)}>
            {y}年
          </Link>
        ))}
      </div>
      <div id={ROW_ID} className="relative mt-1.5 flex items-center gap-1.5 overflow-x-auto pb-0.5" aria-label={`${year}年の月`}>
        {yms.map((ym) => (
          <Link
            key={ym}
            href={`/shinkan/${ym}`}
            aria-current={ym === current ? "page" : undefined}
            data-focus={ym === target ? "" : undefined}
            className={chip(ym === current)}
          >
            {Number(ym.slice(5))}月
          </Link>
        ))}
      </div>
      {target && (
        // 当月チップを月行の中央に寄せる(offsetLeft は relative な行基準)。要素直後に置く=描画前に位置が決まる
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){var r=document.getElementById("${ROW_ID}"),c=r&&r.querySelector("[data-focus]");if(c)r.scrollLeft=c.offsetLeft-(r.clientWidth-c.offsetWidth)/2;})();`,
          }}
        />
      )}
      <p className="mt-1 text-[11px] text-ink/45">
        {months.length ? `${ymLabel(months[0])}〜${ymLabel(months[months.length - 1])}の漫画新刊発売日を月ごとに掲載` : ""}
      </p>
    </nav>
  );
}

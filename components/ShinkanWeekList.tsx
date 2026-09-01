"use client";

import { useEffect, useState } from "react";
import { ShinkanDayBlock } from "@/components/ShinkanRow";
import { dateLabel, monthsCovering, rowsInRange, weekRange, type ShinkanItem, type ShinkanMonth } from "@/lib/shinkanDates";

type Rows = Array<{ date: string; items: ShinkanItem[] }>;

/** 今週の新刊リスト(client): build 時の今週分を初期描画(=静的HTMLに焼かれる)し、
 *  閲覧時の「今週」が build 時と違えば /shinkan/{ym}.json から取り直して差し替える
 *  (データ週=面HTMLを焼き直さない週があるため。鮮度の保険)。 */
export default function ShinkanWeekList({
  initialStart,
  initialEnd,
  initialRows,
  knownSlugs,
}: {
  initialStart: string;
  initialEnd: string;
  initialRows: Rows;
  knownSlugs: string[];
}) {
  const [range, setRange] = useState({ start: initialStart, end: initialEnd });
  const [rows, setRows] = useState<Rows>(initialRows);
  const [known, setKnown] = useState<Set<string> | null>(() => new Set(knownSlugs));
  const [refreshed, setRefreshed] = useState(false);
  useEffect(() => {
    const now = weekRange();
    if (now.start === initialStart) return;
    let alive = true;
    (async () => {
      try {
        const months: Record<string, ShinkanMonth | null> = {};
        for (const ym of monthsCovering(now.start, now.end)) {
          const r = await fetch(`/shinkan/${ym}.json`);
          months[ym] = r.ok ? ((await r.json()) as ShinkanMonth) : null;
        }
        if (!alive) return;
        setRows(rowsInRange(months, now.start, now.end));
        setRange(now);
        setKnown(null); // 取り直し分は全作品に「詳細」を出す(本番は全slugが索引に居る)
        setRefreshed(true);
      } catch {
        /* 失敗時は build 時の内容のまま */
      }
    })();
    return () => {
      alive = false;
    };
  }, [initialStart]);
  const total = rows.reduce((s, r) => s + r.items.length, 0);
  const isKnown = (slug: string) => (known ? known.has(slug) : true);
  const knownSet = { has: isKnown } as Set<string>;
  return (
    <>
      <p className="px-4 pb-2 text-[12px] text-ink/65">
        {dateLabel(range.start, true)}〜{dateLabel(range.end)} の発売分 全{total.toLocaleString()}冊
        {refreshed ? <span className="ml-2 text-[10.5px] text-ink/45">(最新の週に更新)</span> : null}
      </p>
      {rows.map((r) => (
        <ShinkanDayBlock key={r.date} id={`d${r.date.slice(8)}`} heading={dateLabel(r.date, true)} items={r.items} known={knownSet} />
      ))}
      {total === 0 && <p className="px-4 py-8 text-[13px] text-ink/60">この週の新刊はまだ登録されていません。</p>}
    </>
  );
}

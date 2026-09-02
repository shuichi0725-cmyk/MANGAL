"use client";

import { useEffect, useState } from "react";
import { ShinkanDayBlock } from "@/components/ShinkanRow";
import {
  KNOWN_ALL,
  dateLabel,
  monthsCovering,
  rowsInRange,
  weekRange,
  weekdayOf,
  type KnownSet,
  type ShinkanItem,
  type ShinkanMonth,
} from "@/lib/shinkanDates";

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
  const [known, setKnown] = useState<KnownSet>(() => new Set(knownSlugs));
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
        setKnown(KNOWN_ALL); // 取り直し分は全作品に「詳細」を出す(本番は全slugが索引に居る)
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
  const ids = rows.map((r) => `day-${Number(r.date.slice(8))}`);
  return (
    <>
      <p className="px-4 pb-2 text-[12px] text-ink/65">
        {dateLabel(range.start, true)}〜{dateLabel(range.end)} の発売分 全{total.toLocaleString()}冊
        {refreshed ? <span className="ml-2 text-[10.5px] text-ink/45">(最新の週に更新)</span> : null}
      </p>
      {rows.map((r, i) => (
        <ShinkanDayBlock
          key={r.date}
          id={ids[i]}
          label={`${Number(r.date.slice(5, 7))}/${r.date.slice(8)}`}
          sub={weekdayOf(r.date)}
          items={r.items}
          known={known}
          prevId={i > 0 ? ids[i - 1] : undefined}
          nextId={i < rows.length - 1 ? ids[i + 1] : undefined}
        />
      ))}
      {total === 0 && <p className="px-4 py-8 text-[13px] text-ink/60">この週の新刊はまだ登録されていません。</p>}
      <p className="px-4 pt-3 text-[10px] text-ink/40">[PR] Amazonリンクにはアフィリエイト広告を含みます</p>
    </>
  );
}

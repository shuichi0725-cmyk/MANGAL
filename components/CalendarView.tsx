"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useMangaIndex } from "@/lib/useMangaIndex";
import type { MangaListItem } from "@/lib/schema";

type MonthData = { days: Record<string, [string, number | null][]>; unknown: [string, number | null][] };
type Manifest = {
  current: string;
  launch_months: string[];
  release_months: string[];
  launch_counts: Record<string, number>;
  release_counts: Record<string, number>;
};
type CalType = "release" | "launch";

const WEEK = ["日", "月", "火", "水", "木", "金", "土"];

/**
 * 2ビュー発売カレンダー(データ駆動)。
 *  ・発売(release) = 当月+未来の全巻発売 / 創刊(launch) = その月に始まった新連載(全期間)。
 *  ・月データは public/calendar/{type}/{YYYY-MM}.json を遅延fetch(slug参照)。
 *  ・日の中身(題/著者)は軽量索引から join(= 重複保存なし)。 日未定はバケットで別掲。
 */
export default function CalendarView() {
  const [type, setType] = useState<CalType>("release");
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [ym, setYm] = useState("");
  const [data, setData] = useState<MonthData | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [showUnknown, setShowUnknown] = useState(false);

  const index = useMangaIndex();
  const bySlug = useMemo(() => {
    const m = new Map<string, MangaListItem>();
    for (const it of index ?? []) m.set(it.slug, it);
    return m;
  }, [index]);

  // ★データのある月の一覧(type別) → 年セレクタ + 前後ナビ(空月をスキップ)
  const months = useMemo<string[]>(
    () => (manifest ? (type === "release" ? manifest.release_months : manifest.launch_months) : []),
    [manifest, type],
  );
  const years = useMemo(() => [...new Set(months.map((m) => m.slice(0, 4)))].sort().reverse(), [months]);
  // type切替/初期で現ymがその種別に無ければ最新の在る月へ
  useEffect(() => {
    if (months.length && ym && !months.includes(ym)) setYm(months[months.length - 1]);
  }, [months, ym]);

  useEffect(() => {
    fetch("/calendar/manifest.json")
      .then((r) => r.json())
      .then((m: Manifest) => {
        setManifest(m);
        setYm(m.current);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!ym) return;
    setData(null);
    setSel(null);
    setShowUnknown(false);
    fetch(`/calendar/${type}/${ym}.json`)
      .then((r) => (r.ok ? r.json() : { days: {}, unknown: [] }))
      .then(setData)
      .catch(() => setData({ days: {}, unknown: [] }));
  }, [ym, type]);

  const dayMap = useMemo(() => {
    const m = new Map<number, [string, number | null][]>();
    if (data) for (const [d, items] of Object.entries(data.days)) m.set(Number(d), items);
    return m;
  }, [data]);
  const maxN = useMemo(() => Math.max(1, ...[...dayMap.values()].map((x) => x.length)), [dayMap]);

  if (!ym) return <div className="py-6 text-center text-[11px] text-ink/45">カレンダー読込中…</div>;

  const [yy, mm] = ym.split("-");
  const idx = months.indexOf(ym);
  const jumpYear = (y: string) => {
    const m = months.find((mm2) => mm2.startsWith(y));
    if (m) setYm(m);
  };
  const first = new Date(`${ym}-01T00:00:00`);
  const pad = first.getDay();
  const last = new Date(Number(yy), Number(mm), 0).getDate();
  const renderItem = (it: [string, number | null]) => {
    const [slug, vol] = it;
    const m = bySlug.get(slug);
    return (
      <li key={slug + "-" + vol}>
        <Link href={`/manga/${slug}`} className="spring-press flex items-baseline gap-2">
          <span className="h-1.5 w-1.5 shrink-0 translate-y-[-1px] rounded-full bg-[var(--color-accent)]" />
          <span className="min-w-0 flex-1 truncate text-[12.5px] text-ink/85">
            {m?.title ?? slug}
            {type === "release" && vol ? <span className="text-ink/45"> {vol}巻</span> : null}
          </span>
          <span className="shrink-0 text-[10px] text-ink/45">{m?.authors?.map((a) => a.name).join("・") ?? ""}</span>
        </Link>
      </li>
    );
  };

  const selItems = sel != null ? dayMap.get(Number(sel)) ?? [] : [];
  const cells = [];
  for (let i = 0; i < pad; i++) cells.push(<span key={`p${i}`} />);
  for (let d = 1; d <= last; d++) {
    const n = dayMap.get(d)?.length ?? 0;
    const op = n === 0 ? 0 : 0.25 + 0.75 * (n / maxN);
    cells.push(
      <button
        key={d}
        onClick={() => setSel(sel === String(d) ? null : String(d))}
        disabled={n === 0}
        className={`spring-press relative flex h-8 flex-col items-center justify-center rounded text-[10px] ${
          sel === String(d) ? "ring-2 ring-[var(--color-accent)]" : ""
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
      {/* ビュー切替 + 月ナビ */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex gap-1">
          {(["release", "launch"] as CalType[]).map((t) => (
            <button
              key={t}
              onClick={() => setType(t)}
              className={`spring-press rounded-full px-2.5 py-1 text-[11px] font-bold ${
                type === t ? "bg-[var(--color-accent)] text-white" : "border border-[var(--color-line)] bg-[var(--color-surface)] text-ink/65"
              }`}
            >
              {t === "release" ? "発売日" : "創刊"}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => idx > 0 && setYm(months[idx - 1])} disabled={idx <= 0} className="spring-press rounded px-1 text-ink/60 disabled:opacity-25" aria-label="前の月">‹</button>
          <select
            value={yy}
            onChange={(e) => jumpYear(e.target.value)}
            className="rounded border border-[var(--color-line)] bg-[var(--color-surface)] px-1 py-0.5 text-[12px] font-bold tabular-nums"
            aria-label="年"
          >
            {years.map((y) => (
              <option key={y} value={y}>{y}年</option>
            ))}
          </select>
          <span className="min-w-[26px] text-center text-[12px] font-bold tabular-nums">{Number(mm)}月</span>
          <button onClick={() => idx >= 0 && idx < months.length - 1 && setYm(months[idx + 1])} disabled={idx < 0 || idx >= months.length - 1} className="spring-press rounded px-1 text-ink/60 disabled:opacity-25" aria-label="次の月">›</button>
        </div>
      </div>

      <div className="mt-2.5 grid grid-cols-7 gap-1 text-center">
        {WEEK.map((w) => (
          <span key={w} className="text-[9px] font-semibold text-ink/40">{w}</span>
        ))}
        {cells}
      </div>

      {sel != null && (
        <div className="mt-2.5 rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)]/60 p-2.5">
          <p className="text-[11px] font-bold text-ink/70">
            {Number(mm)}月{sel}日{type === "release" ? "の発売" : "に創刊"} — {selItems.length}件
          </p>
          <ul className="mt-1.5 space-y-1">{selItems.map(renderItem)}</ul>
        </div>
      )}

      {/* 日未定バケット(年月のみ = 予約で日未確定 or 古い月精度) */}
      {data && data.unknown.length > 0 && (
        <div className="mt-2">
          <button
            onClick={() => setShowUnknown((v) => !v)}
            className="spring-press w-full rounded-lg border border-dashed border-[var(--color-line)] px-2.5 py-1.5 text-left text-[11px] text-ink/60"
          >
            📅 {Number(mm)}月発売・<span className="font-bold">日未定</span> {data.unknown.length}件{showUnknown ? " ▲" : " ▼"}
          </button>
          {showUnknown && <ul className="mt-1.5 space-y-1 px-1">{data.unknown.map(renderItem)}</ul>}
        </div>
      )}

      <p className="mt-2 text-[10px] text-ink/45">
        {type === "release" ? "発売日 = 当月+未来の新刊(続刊含む)" : "創刊 = その月に始まった新連載(全期間)"} ・ 日付タップでその日の一覧
      </p>
    </div>
  );
}

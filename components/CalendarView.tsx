"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMangaIndex } from "@/lib/useMangaIndex";
import type { MangaListItem } from "@/lib/schema";

type Item = Array<string | number | null>; // [slug, vol, title]
type MonthData = { days: Record<string, Item[]>; unknown: Item[] };
type Beyond = { items: Array<[string, number | null, string, string]> }; // [slug,vol,title,ym(-dd)]

const WEEK = ["日", "月", "火", "水", "木", "金", "土"];

function addMonths(ym: string, k: number): string {
  const y = Number(ym.slice(0, 4));
  const m = Number(ym.slice(5, 7)) + k;
  const yy = y + Math.floor((m - 1) / 12);
  const mm = ((m - 1) % 12) + 1;
  return `${yy}-${String(mm).padStart(2, "0")}`;
}

/**
 * 発売カレンダー(2026-07-06 全面刷新):
 *  ・当月〜3ヶ月後の4パネル + 「以降・未定」一覧の計5パネルを横スワイプ(scroll-snap)。
 *  ・過去ナビ/創刊ビューは廃止(過去=タイムマシン・創刊=検索側フィルターの守備範囲)。
 *  ・タブの下線がスワイプ量に追従。データは /calendar/release/*.json 遅延fetch。
 *  ・previewはページ実在フィルタ済みJSON=「載っている→必ず飛べる」。
 */
export default function CalendarView() {
  const [current, setCurrent] = useState("");
  const [months, setMonths] = useState<Record<string, MonthData | null>>({});
  const [beyond, setBeyond] = useState<Beyond | null>(null);
  const [active, setActive] = useState(0);
  const [progress, setProgress] = useState(0); // 0..4 スワイプ実数(下線追従)
  const [sel, setSel] = useState<string | null>(null); // "ym-dd"
  const scroller = useRef<HTMLDivElement>(null);

  const index = useMangaIndex();
  const bySlug = useMemo(() => {
    const m = new Map<string, MangaListItem>();
    for (const it of index ?? []) m.set(it.slug, it);
    return m;
  }, [index]);

  useEffect(() => {
    fetch("/calendar/manifest.json")
      .then((r) => r.json())
      .then((m: { current: string }) => setCurrent(m.current))
      .catch(() => {});
  }, []);

  const panelYms = useMemo(
    () => (current ? [0, 1, 2, 3].map((k) => addMonths(current, k)) : []),
    [current],
  );

  useEffect(() => {
    if (!panelYms.length) return;
    for (const ym of panelYms) {
      fetch(`/calendar/release/${ym}.json`)
        .then((r) => (r.ok ? r.json() : { days: {}, unknown: [] }))
        .then((d: MonthData) => setMonths((prev) => ({ ...prev, [ym]: d })))
        .catch(() => setMonths((prev) => ({ ...prev, [ym]: { days: {}, unknown: [] } })));
    }
    fetch("/calendar/release/beyond.json")
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then(setBeyond)
      .catch(() => setBeyond({ items: [] }));
  }, [panelYms]);

  // スワイプ追従(下線) + アクティブ判定
  const onScroll = () => {
    const el = scroller.current;
    if (!el) return;
    const p = el.scrollLeft / Math.max(1, el.clientWidth);
    setProgress(p);
    setActive(Math.round(p));
  };
  const goto = (i: number) => {
    const el = scroller.current;
    if (el) el.scrollTo({ left: i * el.clientWidth, behavior: "smooth" });
  };
  // ★可変高(2026-07-06 ユーザ要望): コンテナ高さ=表示中パネルの実高さ。
  //   flexの既定(最大子に揃う)だと「以降・未定」の長さに引っ張られ月表示の下が巨大空白になるため。
  const [panelH, setPanelH] = useState<number | undefined>(undefined);
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const panel = el.children[active] as HTMLElement | undefined;
    if (!panel) return;
    const measure = () => setPanelH(panel.scrollHeight);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(panel);
    return () => ro.disconnect();
  }, [active, months, beyond]);

  if (!current) return <div className="py-6 text-center text-[11px] text-ink/45">カレンダー読込中…</div>;

  const tabs = [...panelYms.map((ym, i) => (i === 0 ? "今月" : `${Number(ym.slice(5, 7))}月`)), "以降・未定"];

  const renderItem = (it: Item, key: string) => {
    const slug = String(it[0]);
    const vol = it[1] as number | null;
    const embedded = it[2] as string | undefined;
    const m = bySlug.get(slug);
    return (
      <li key={key}>
        <Link href={`/manga/${slug}`} className="spring-press flex items-baseline gap-2">
          <span className="h-1.5 w-1.5 shrink-0 translate-y-[-1px] rounded-full bg-[var(--color-accent)]" />
          <span className="min-w-0 flex-1 truncate text-[12.5px] text-ink/85">
            {m?.title ?? embedded ?? slug}
            {vol ? <span className="text-ink/45"> {vol}巻</span> : null}
          </span>
          <span className="shrink-0 text-[10px] text-ink/45">{m?.authors?.map((a) => a.name).join("・") ?? ""}</span>
        </Link>
      </li>
    );
  };

  const monthPanel = (ym: string) => {
    const data = months[ym];
    const dayMap = new Map<number, Item[]>();
    if (data) for (const [d, items] of Object.entries(data.days)) dayMap.set(Number(d), items);
    const maxN = Math.max(1, ...[...dayMap.values()].map((x) => x.length));
    const [yy, mm] = ym.split("-");
    const first = new Date(`${ym}-01T00:00:00`);
    const pad = first.getDay();
    const last = new Date(Number(yy), Number(mm), 0).getDate();
    const cells = [];
    for (let i = 0; i < pad; i++) cells.push(<span key={`p${i}`} />);
    for (let d = 1; d <= last; d++) {
      const n = dayMap.get(d)?.length ?? 0;
      const op = n === 0 ? 0 : 0.25 + 0.75 * (n / maxN);
      const k = `${ym}-${d}`;
      cells.push(
        <button
          key={d}
          onClick={() => setSel(sel === k ? null : k)}
          disabled={n === 0}
          className={`spring-press relative flex h-8 flex-col items-center justify-center rounded text-[10px] ${
            sel === k ? "ring-2 ring-[var(--color-accent)]" : ""
          } ${n === 0 ? "text-ink/30" : "text-ink/70"}`}
          style={n ? { backgroundColor: `color-mix(in srgb, var(--color-accent) ${Math.round(op * 28)}%, transparent)` } : undefined}
        >
          {d}
          {n > 0 && <span className="text-[8px] font-bold text-[var(--color-accent)]">{n}</span>}
        </button>,
      );
    }
    const selDay = sel && sel.startsWith(ym + "-") ? Number(sel.slice(8)) : null;
    const selItems = selDay != null ? dayMap.get(selDay) ?? [] : [];
    return (
      <div className="w-full shrink-0 snap-center px-0.5" key={ym}>
        <p className="text-center text-[12px] font-bold text-ink/70">{yy}年{Number(mm)}月</p>
        <div className="mt-1 grid grid-cols-7 gap-0.5 text-center text-[9px] text-ink/45">
          {WEEK.map((w) => <span key={w}>{w}</span>)}
        </div>
        <div className="mt-0.5 grid grid-cols-7 gap-0.5">{cells}</div>
        {!data && <p className="py-3 text-center text-[11px] text-ink/40">読込中…</p>}
        {selDay != null && selItems.length > 0 && (
          <div className="mt-2 rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-2)]/50 p-2.5">
            <p className="text-[11px] font-bold text-ink/60">{Number(mm)}月{selDay}日の発売 − {selItems.length}件</p>
            <ul className="mt-1.5 space-y-1">{selItems.map((it, i) => renderItem(it, `${sel}-${i}`))}</ul>
          </div>
        )}
        {data && data.unknown.length > 0 && (
          <details className="mt-2">
            <summary className="cursor-pointer text-[11px] text-ink/50">日付未定({data.unknown.length})</summary>
            <ul className="mt-1.5 space-y-1">{data.unknown.map((it, i) => renderItem(it, `${ym}-u${i}`))}</ul>
          </details>
        )}
      </div>
    );
  };

  return (
    <div>
      {/* タブ + 追従下線 */}
      <div className="relative">
        <div className="grid grid-cols-5 text-center">
          {tabs.map((t, i) => (
            <button
              key={t}
              onClick={() => goto(i)}
              className={`spring-press py-1.5 text-[12px] font-bold transition-colors ${active === i ? "text-[var(--color-accent)]" : "text-ink/50"}`}
            >
              {t}
            </button>
          ))}
        </div>
        <div
          className="absolute bottom-0 h-[2.5px] w-1/5 rounded-full bg-[var(--color-accent)]"
          style={{ transform: `translateX(${progress * 100}%)` }}
        />
      </div>

      {/* 5パネル横スワイプ */}
      <div
        ref={scroller}
        onScroll={onScroll}
        className="mt-2 flex snap-x snap-mandatory items-start overflow-x-auto overflow-y-hidden overscroll-x-contain transition-[height] duration-300 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        style={panelH !== undefined ? { height: panelH } : undefined}
      >
        {panelYms.map((ym) => monthPanel(ym))}
        {/* 5枚目: 以降・未定(一覧表) */}
        <div className="w-full shrink-0 snap-center px-0.5">
          <p className="text-center text-[12px] font-bold text-ink/70">{Number(addMonths(current, 4).slice(5, 7))}月以降・発売日未定</p>
          {!beyond && <p className="py-3 text-center text-[11px] text-ink/40">読込中…</p>}
          {beyond && beyond.items.length === 0 && (
            <p className="py-4 text-center text-[11px] text-ink/40">現在、掲載できる先の予定はありません</p>
          )}
          {beyond && beyond.items.length > 0 && (
            <ul className="mt-2 space-y-1.5">
              {beyond.items.map((it, i) => (
                <li key={i}>
                  <Link href={`/manga/${it[0]}`} className="spring-press flex items-baseline gap-2">
                    <span className="shrink-0 rounded bg-[var(--color-surface-2)] px-1.5 py-0.5 text-[10px] tabular-nums text-ink/60">
                      {it[3] ? String(it[3]).replaceAll("-", "/") : "未定"}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-[12.5px] text-ink/85">
                      {bySlug.get(it[0])?.title ?? it[2] ?? it[0]}
                      {it[1] ? <span className="text-ink/45"> {it[1]}巻</span> : null}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <p className="mt-1.5 text-[10px] text-ink/40">左右スワイプで月を移動 ・ 日付タップでその日の一覧</p>
    </div>
  );
}

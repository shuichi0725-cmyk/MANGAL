"use client";

import { useEffect, useMemo, useState } from "react";
import EditionRow from "@/components/EditionRow";
import KanaShelf from "@/components/KanaShelf";
import { TYPE_JA, type AizItem } from "@/components/EditionCorners";
import { jaCollator } from "@/lib/collator";

/** 愛蔵版・合本の一覧(/aizouban)。版種チップで絞り込み、並びは**50音順**
 *  (2026-09-06 ユーザ指示「名前の順に。フリガナを参考に」= title_kana キー。
 *   一覧表の「50音順」= lib/listSort と同じ比較で揃える)。
 *  ★同日: 本屋ふうの50音索引(KanaShelf)+ 今月の新刊と同じ行(EditionRow=
 *    書影105×150を押すとAmazon / 小さい「詳細」で作品ページ)に統一。 */
const ORDER = ["aizoban", "kanzenban", "wideban", "shinsoban", "deluxe", "other"];

export default function AizoubanListClient() {
  const [rows, setRows] = useState<AizItem[] | null>(null);
  const [type, setType] = useState<string>("all");
  useEffect(() => {
    fetch("/data/aizouban-stock.json")
      .then((r) => (r.ok ? r.json() : []))
      .then(setRows)
      .catch(() => setRows([]));
  }, []);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const r of rows ?? []) c[r.e] = (c[r.e] ?? 0) + 1;
    return c;
  }, [rows]);

  const list = useMemo(() => {
    const src = (rows ?? []).filter((r) => type === "all" || r.e === type);
    // ★50音順=フリガナ(title_kana)基準。無い頁だけ題名で代替(lib/listSort の kana と同式)
    return [...src].sort(
      (a, b) => jaCollator.compare(a.k || a.t, b.k || b.t) || a.v - b.v,
    );
  }, [rows, type]);

  if (rows === null) return <p className="px-4 text-[13px] text-ink/60">読み込み中…</p>;

  const chips: Array<[string, string, number]> = [
    ["all", "すべて", rows.length],
    ...ORDER.filter((k) => counts[k]).map((k) => [k, TYPE_JA[k] ?? k, counts[k]] as [string, string, number]),
  ];

  return (
    <div className="px-4 pb-8">
      <div className="-mx-4 mb-2.5 flex gap-1.5 overflow-x-auto px-4 pb-1 no-scrollbar">
        {chips.map(([k, label, n]) => (
          <button
            key={k}
            type="button"
            onClick={() => setType(k)}
            aria-pressed={type === k}
            className={`shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-bold spring-press ${
              type === k
                ? "border-transparent bg-[var(--color-accent)] text-[var(--color-on-accent)]"
                : "border-[var(--color-line)] bg-[var(--color-surface)] text-ink/70"
            }`}
          >
            {label} <span className="tabular-nums opacity-70">{n}</span>
          </button>
        ))}
      </div>

      <KanaShelf
        items={list}
        kanaOf={(e) => e.k || e.t}
        keyOf={(e) => `${e.s}-${e.e}-${e.v}`}
        caption={<>{list.length}点・フリガナの50音順。頭文字をタップでその棚へ。</>}
        render={(e) => (
          <EditionRow
            slug={e.s}
            title={e.t}
            authors={e.a}
            cover={e.c}
            isbn={e.i}
            badge={TYPE_JA[e.e] ?? e.e}
            query={`${e.t} ${TYPE_JA[e.e] ?? ""}`.trim()}
            meta={
              <>
                全{e.sv}巻 → <b className="text-ink/85">{e.v}巻</b>
                {e.d ? <span className="text-ink/35"> ・{e.d}年</span> : null}
              </>
            }
            note={e.l}
          />
        )}
      />
      <p className="mt-5 text-[10px] text-ink/40">[PR] Amazonリンクにはアフィリエイト広告を含みます</p>
    </div>
  );
}

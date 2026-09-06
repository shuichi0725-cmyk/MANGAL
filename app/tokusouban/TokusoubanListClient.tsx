"use client";

import { useEffect, useMemo, useState } from "react";
import EditionRow from "@/components/EditionRow";
import KanaShelf from "@/components/KanaShelf";
import type { TksItem } from "@/components/EditionCorners";
import { jaCollator } from "@/lib/collator";

/** 特装版・限定版の一覧(/tokusouban)。並びは**50音順**(2026-09-06 ユーザ指示「名前の順に。
 *  フリガナを参考に」= title_kana キー)。同じ作品の特装版が隣り合う。
 *  ★同日: 本屋ふうの50音索引(KanaShelf)+ 今月の新刊と同じ行(EditionRow=
 *    書影105×150を押すとAmazon / 小さい「詳細」で作品ページ)に統一。
 *  「新しい順」も残す(こちらは索引なしの通し表示=時系列が切れないように)。 */
type Sort = "kana" | "new";

export default function TokusoubanListClient() {
  const [rows, setRows] = useState<TksItem[] | null>(null);
  const [sort, setSort] = useState<Sort>("kana");
  useEffect(() => {
    fetch("/data/tokusouban-stock.json")
      .then((r) => (r.ok ? r.json() : []))
      .then(setRows)
      .catch(() => setRows([]));
  }, []);

  const list = useMemo(() => {
    // ★50音順=フリガナ(title_kana)基準。無い頁だけ題名で代替(lib/listSort の kana と同式)
    const byKana = (a: TksItem, b: TksItem) =>
      jaCollator.compare(a.k || a.t, b.k || b.t) || (a.v ?? 0) - (b.v ?? 0);
    const src = [...(rows ?? [])];
    if (sort === "new") {
      return src.sort((a, b) => (b.d ?? "").localeCompare(a.d ?? "") || byKana(a, b));
    }
    return src.sort(byKana);
  }, [rows, sort]);

  if (rows === null) return <p className="px-4 text-[13px] text-ink/60">読み込み中…</p>;
  const works = new Set(rows.map((r) => r.s)).size;

  const Row = (e: TksItem) => (
    <EditionRow
      slug={e.s}
      title={e.t}
      authors={e.a}
      cover={e.c}
      isbn={e.i}
      badge={e.l}
      query={`${e.t} ${e.v ?? ""} ${e.l}`.trim()}
      meta={
        <>
          {e.v ? `${e.v}巻` : "特装"}
          {e.d ? <span className="text-ink/35"> ・{e.d}年</span> : null}
        </>
      }
    />
  );

  return (
    <div className="px-4 pb-8">
      <div className="mb-2.5 flex items-baseline justify-between gap-2">
        <p className="text-[11px] text-ink/50">
          {rows.length}点 / {works}作品
        </p>
        <div className="flex gap-1.5">
          {([["kana", "50音順"], ["new", "新しい順"]] as Array<[Sort, string]>).map(([k, label]) => (
            <button
              key={k}
              type="button"
              onClick={() => setSort(k)}
              aria-pressed={sort === k}
              className={`rounded-full border px-2.5 py-1 text-[11px] font-bold spring-press ${
                sort === k
                  ? "border-transparent bg-[var(--color-accent)] text-[var(--color-on-accent)]"
                  : "border-[var(--color-line)] bg-[var(--color-surface)] text-ink/70"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {sort === "kana" ? (
        <KanaShelf
          items={list}
          kanaOf={(e) => e.k || e.t}
          keyOf={(e) => `${e.s}-${e.v}-${e.l}`}
          caption={<>{list.length}点・フリガナの50音順。頭文字をタップでその棚へ。</>}
          render={Row}
        />
      ) : (
        <ul className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
          {list.map((e) => (
            <li key={`${e.s}-${e.v}-${e.l}`}>{Row(e)}</li>
          ))}
        </ul>
      )}
      <p className="mt-5 text-[10px] text-ink/40">[PR] Amazonリンクにはアフィリエイト広告を含みます</p>
    </div>
  );
}

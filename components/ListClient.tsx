"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import FilterPanel from "@/components/FilterPanel";
import {
  applyFilters,
  authorsWithKana,
  emptyFilterState,
  yearBounds,
  type FilterState,
} from "@/lib/filters";

function activeCount(s: FilterState): number {
  const e = emptyFilterState() as Record<string, unknown>;
  let n = 0;
  for (const k of Object.keys(e)) {
    if (k === "sortKey") continue;
    if (JSON.stringify((s as Record<string, unknown>)[k]) !== JSON.stringify(e[k])) n++;
  }
  return n;
}
import type { ListBundle, MangaListItem } from "@/lib/schema";
import { useMangaIndex } from "@/lib/useMangaIndex";

/** 一覧表クライアント: 絞り込み=既存の多窓フィルター(トップと同じ)、並び順=独立チップ。
 *  「完結×ジャンル×作者×開始が古い順」のような自由なAND合成が成立する。 */

type SortId = "kana" | "year-asc" | "year-desc" | "vols-desc" | "latest-desc";
const SORTS: Array<{ id: SortId; label: string }> = [
  { id: "kana", label: "50音順" },
  { id: "year-asc", label: "開始が古い" },
  { id: "year-desc", label: "開始が新しい" },
  { id: "vols-desc", label: "巻数が多い" },
  { id: "latest-desc", label: "最新刊が新しい" },
];

function volCount(m: MangaListItem): number {
  return m.max_edition_volumes;
}
function latestDate(m: MangaListItem): string {
  return m.latest_date ?? "";
}

export default function ListClient({ data }: { data: ListBundle }) {
  const [state, setState] = useState<FilterState>(emptyFilterState());
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortId>("kana");
  const [limit, setLimit] = useState(200);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  // ★manga は軽量索引をクライアント遅延ロード (= SSR props で 65k を送らない)
  const mangaIndex = useMangaIndex();
  const manga = useMemo(() => mangaIndex ?? [], [mangaIndex]);
  const indexLoading = mangaIndex === null;
  const liveData = useMemo(() => ({ ...data, manga }), [data, manga]);
  const bounds = useMemo(() => yearBounds(manga), [manga]);
  const authors = useMemo(() => authorsWithKana(manga, true), [manga]);
  const nActive = activeCount(state);

  const rows = useMemo(() => {
    let r = applyFilters(manga, state);
    const needle = q.trim().toLowerCase();
    if (needle) {
      r = r.filter(
        (m) =>
          m.title.toLowerCase().includes(needle) ||
          (m.title_kana || "").includes(q.trim()) ||
          m.authors.some((a) => a.name.toLowerCase().includes(needle)),
      );
    }
    const sorted = [...r].sort((a, b) => {
      switch (sort) {
        case "year-asc":
          return (a.year_started ?? 9999) - (b.year_started ?? 9999);
        case "year-desc":
          return (b.year_started ?? 0) - (a.year_started ?? 0);
        case "vols-desc":
          return volCount(b) - volCount(a);
        case "latest-desc":
          return latestDate(b).localeCompare(latestDate(a));
        default:
          return (a.title_kana || a.title).localeCompare(b.title_kana || b.title, "ja");
      }
    });
    return sorted;
  }, [manga, state, q, sort]);

  return (
    <div>
      {/* ── コントロール: 検索 / フィルターボタン / 並び順チップ ── */}
      <div className="px-3 pt-2.5">
        <div className="flex items-center gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="題名・よみ・著者で検索…"
            className="min-w-0 flex-1 rounded-full border border-[var(--color-line)] bg-white px-3.5 py-1.5 text-[13px] outline-none focus:border-[var(--color-accent)]"
          />
          <button
            onClick={() => setOpen(true)}
            className={`spring-press shrink-0 rounded-full px-3 py-1.5 text-[12px] font-bold ${
              nActive > 0 ? "bg-[var(--color-accent)] text-white" : "border border-[var(--color-line)] bg-[var(--color-surface)] text-ink/75"
            }`}
          >
            ⚙ フィルター{nActive > 0 ? ` (${nActive})` : ""}
          </button>
        </div>
        <div className="mt-2 flex items-center gap-1.5 overflow-x-auto pb-1">
          <span className="shrink-0 text-[10px] font-bold text-ink/45">並び順</span>
          {SORTS.map((s) => (
            <button
              key={s.id}
              onClick={() => setSort(s.id)}
              className={`spring-press shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                sort === s.id ? "bg-ink text-white" : "border border-[var(--color-line)] bg-[var(--color-surface)] text-ink/65"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>
      <p className="px-3 pb-1 text-[11px] text-ink/50">
        {rows.length.toLocaleString()} 件{nActive > 0 || q ? <span className="text-ink/40">(絞り込み中)</span> : null}
      </p>

      {/* ── 表 ── */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] border-collapse text-[12px]">
          <thead className="sticky top-0 bg-[var(--color-surface-2)] text-left text-[11px] text-ink/65">
            <tr className="[&>th]:border-b [&>th]:border-[var(--color-line)] [&>th]:px-2 [&>th]:py-2">
              <th>題名</th>
              <th>著者</th>
              <th className="w-12 text-right">巻</th>
              <th className="w-14 text-right">開始</th>
              <th className="w-12">状態</th>
              <th className="w-20 text-right">最新刊</th>
            </tr>
          </thead>
          <tbody>
            {indexLoading && (
              <tr>
                <td colSpan={6} className="py-10 text-center text-sm text-ink/55">
                  📚 作品データを読み込み中…
                </td>
              </tr>
            )}
            {rows.slice(0, limit).map((m, i) => (
              <tr key={m.slug} className={i % 2 ? "bg-[var(--color-surface)]/60" : ""}>
                <td className="max-w-[200px] border-b border-[var(--color-line)]/60 px-2 py-1.5">
                  {/* DEBUG: フォルダ名(slug)表示。 本番前に削除する */}
                  <span className="block truncate font-mono text-[10px] text-rose-600/80">{m.slug}</span>
                  <Link href={`/manga/${m.slug}`} className="spring-press block truncate font-medium text-[#1f4e79] active:underline">
                    {m.title}
                  </Link>
                </td>
                <td className="max-w-[120px] truncate border-b border-[var(--color-line)]/60 px-2 py-1.5 text-ink/75">
                  {m.authors.map((a) => a.name).join("・")}
                </td>
                <td className="border-b border-[var(--color-line)]/60 px-2 py-1.5 text-right tabular-nums">{volCount(m)}</td>
                <td className="border-b border-[var(--color-line)]/60 px-2 py-1.5 text-right tabular-nums text-ink/70">{m.year_started ?? "—"}</td>
                <td className="border-b border-[var(--color-line)]/60 px-2 py-1.5">
                  {m.status === "completed" ? <span className="text-ink/60">完結</span> : <span className="font-semibold text-emerald-700">連載</span>}
                </td>
                <td className="border-b border-[var(--color-line)]/60 px-2 py-1.5 text-right tabular-nums text-ink/60">{latestDate(m) || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > limit && (
        <div className="py-3 text-center">
          <button onClick={() => setLimit((l) => l + 300)} className="spring-press rounded-full border border-[var(--color-line)] bg-[var(--color-surface)] px-4 py-1.5 text-[12px] font-semibold text-ink/70">
            さらに表示({(rows.length - limit).toLocaleString()}件)
          </button>
        </div>
      )}

      {/* ── フィルターオーバーレイ(トップと同じFilterPanelを再利用) ── */}
      {open && (
        <div className="fixed inset-0 z-50">
          {/* ★透過オーバーレイ(ユーザ裁定): 背景の一覧がうっすら見える=どこに居るか分かる */}
          <div className="absolute inset-0 bg-black/15" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 right-0 w-[86%] max-w-sm overflow-y-auto border-l border-[var(--color-line)] bg-[var(--color-surface)]/80 p-4 shadow-2xl backdrop-blur-md">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm font-bold">フィルター</p>
              <div className="flex gap-2">
                <button onClick={() => setState(emptyFilterState())} className="spring-press rounded-full border border-[var(--color-line)] px-3 py-1 text-[11px] text-ink/65">
                  リセット
                </button>
                <button onClick={() => setOpen(false)} className="spring-press rounded-full bg-ink px-3 py-1 text-[11px] font-bold text-white">
                  閉じる
                </button>
              </div>
            </div>
            <FilterPanel data={liveData} state={state} setState={setState} yearBounds={bounds} authorEntries={authors} />
          </div>
        </div>
      )}
    </div>
  );
}

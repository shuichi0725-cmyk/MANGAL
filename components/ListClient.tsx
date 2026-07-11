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

type SortId = "kana" | "year-asc" | "year-desc" | "vols-desc" | "latest-desc" | "popularity";
const SORTS: Array<{ id: SortId; label: string }> = [
  { id: "popularity", label: "人気順" },
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
  // ★テストモード判定(HomeClientと同じ): preview/localhost or #debug。テスト時は題名列を最長題に合わせる(チェック用・ユーザ要望 2026-07-06)
  const [isPreview, setIsPreview] = useState(false);
  useEffect(() => {
    const h = window.location.hostname;
    setIsPreview(h.includes("preview") || h === "localhost" || h === "127.0.0.1" || localStorage.getItem("mangal-diag") === "1");
  }, []);
  const [state, setState] = useState<FilterState>(emptyFilterState());
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");             // 確定済み検索語(=絞込に効く)
  const [qInput, setQInput] = useState("");   // 入力中の文字(★ボタン/Enterまで検索しない 2026-07-11 ユーザ仕様)
  // ★URL ?q= を初期値に(2026-07-06 PCサイドバー検索からの遷移受け)
  useEffect(() => {
    const uq = new URLSearchParams(window.location.search).get("q");
    if (uq) {
      setQ(uq);
      setQInput(uq);
    }
  }, []);
  // ★q変更をURLへ書き戻し(replace=履歴を汚さない)。詳細→OS戻るで検索語が消えない(2026-07-10 ユーザ相談)
  useEffect(() => {
    const url = new URL(window.location.href);
    if (q) url.searchParams.set("q", q);
    else url.searchParams.delete("q");
    window.history.replaceState(null, "", url.toString());
  }, [q]);
  // ★既定=人気順(2026-07-11 ユーザ仕様: 検索前のデフォルトは人気順)
  const [sort, setSort] = useState<SortId>("popularity");
  const [sortTouched, setSortTouched] = useState(false);
  const [limit, setLimit] = useState(200);
  const [slugfixOnly, setSlugfixOnly] = useState(false);

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
    if (slugfixOnly) r = r.filter((m) => m._slugfix);
    const needle = q.trim().toLowerCase();
    if (needle) {
      r = r.filter(
        (m) =>
          m.title.toLowerCase().includes(needle) ||
          (m.title_kana || "").includes(q.trim()) ||
          m.authors.some((a) => a.name.toLowerCase().includes(needle)),
      );
    }
    // ★検索時の既定=人気順(2026-07-05 ユーザ要望: 検索したら人気順で出る)。手動選択があればそれを尊重
    const effSort: SortId = q.trim() && !sortTouched ? "popularity" : sort;
    const sorted = [...r].sort((a, b) => {
      switch (effSort) {
        case "popularity":
          return (b.popularity ?? 0) - (a.popularity ?? 0) || (b.score ?? 0) - (a.score ?? 0) || a.title_kana.localeCompare(b.title_kana, "ja");
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
  }, [manga, state, q, sort, sortTouched, slugfixOnly]);

  return (
    <div>
      {/* ── コントロール: 検索 / フィルターボタン / 並び順チップ ── */}
      <div className="px-3 pt-2.5">
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setQ(qInput.trim());
          }}
        >
          <input
            value={qInput}
            onChange={(e) => {
              setQInput(e.target.value);
              if (e.target.value === "" && q) setQ(""); // 全消しは即解除(押し直し不要)
            }}
            placeholder="題名・よみ・著者で検索…"
            className="min-w-0 flex-1 rounded-full border border-[var(--color-line)] bg-white px-3.5 py-1.5 text-[13px] outline-none focus:border-[var(--color-accent)]"
          />
          <button
            type="submit"
            className="spring-press shrink-0 rounded-full bg-[var(--color-accent)] px-3.5 py-1.5 text-[12px] font-bold text-white"
          >
            検索
          </button>
          <button
            type="button"
            onClick={() => setOpen(true)}
            className={`spring-press shrink-0 rounded-full px-3 py-1.5 text-[12px] font-bold ${
              nActive > 0 ? "bg-[var(--color-accent)] text-white" : "border border-[var(--color-line)] bg-[var(--color-surface)] text-ink/75"
            }`}
          >
            ⚙ フィルター{nActive > 0 ? ` (${nActive})` : ""}
          </button>
        </form>
        <div className="mt-2 flex items-center gap-1.5 overflow-x-auto pb-1">
          <span className="shrink-0 text-[10px] font-bold text-ink/45">並び順</span>
          {SORTS.map((s) => (
            <button
              key={s.id}
              onClick={() => { setSort(s.id); setSortTouched(true); }}
              className={`spring-press shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                sort === s.id ? "bg-ink text-white" : "border border-[var(--color-line)] bg-[var(--color-surface)] text-ink/65"
              }`}
            >
              {s.label}
            </button>
          ))}
          <button
            onClick={() => setSlugfixOnly((v) => !v)}
            className={`spring-press shrink-0 rounded-full px-2.5 py-1 text-[11px] font-bold ${
              slugfixOnly ? "bg-[var(--color-accent)] text-white" : "border border-[var(--color-accent)]/40 bg-[var(--color-surface)] text-[var(--color-accent)]"
            }`}
          >
            slug修正のみ
          </button>
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
                <td className={`${isPreview ? "" : "max-w-[200px] "}border-b border-[var(--color-line)]/60 px-2 py-1.5`}>
                  {/* ★題名は切らない(2026-07-06 ユーザ要望): truncate廃止→セル内横スクロール(whitespace-nowrap+overflow-x-auto) */}
                  <div className="max-w-full overflow-x-auto" style={{ scrollbarWidth: "none" }}>
                    {/* DEBUG: フォルダ名(slug)表示。 本番前に削除する */}
                    <span className="block whitespace-nowrap font-mono text-[10px] text-rose-600/80">{m.slug}</span>
                    {m._slugfix && m._slugfix_new && m._slugfix_new !== m.slug && (
                      <span className="block whitespace-nowrap font-mono text-[10px] font-bold text-emerald-600">→ {m._slugfix_new}</span>
                    )}
                    <Link href={`/manga/${m.slug}`} className="spring-press block whitespace-nowrap font-medium text-[#1f4e79] active:underline">
                      {m.title}
                    </Link>
                  </div>
                </td>
                <td className={`${isPreview ? "" : "max-w-[120px] "}border-b border-[var(--color-line)]/60 px-2 py-1.5 text-ink/75`}>
                  <div className="max-w-full overflow-x-auto whitespace-nowrap" style={{ scrollbarWidth: "none" }}>
                    {m.authors.map((a) => a.name).join("・")}
                  </div>
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

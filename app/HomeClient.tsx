"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import CategoryHub from "@/components/CategoryHub";
import FilterPanel from "@/components/FilterPanel";
import MangaGrid from "@/components/MangaGrid";
import SearchBox from "@/components/SearchBox";
import Pager from "@/components/ui/Pager";
import {
  applyFilters,
  emptyFilterState,
  filtersFromSearchParams,
  uniqueAuthors,
  yearBounds,
} from "@/lib/filters";
import type { DataBundle } from "@/lib/schema";

type Props = { data: DataBundle };

const PAGE_SIZE = 100;

export default function HomeClient({ data }: Props) {
  const searchParams = useSearchParams();
  const [state, setState] = useState(emptyFilterState());
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const listTopRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // URL の検索 params が source of truth。 前 state を merge せず、
    // emptyFilterState + URL params で毎回 fresh に組み直す。 これによって
    // CategoryHub click や browser back/forward で前の filter が累積せず
    // 「期待した内容だけ」 が反映される。 ユーザの FilterPanel 手動編集は
    // URL を更新しないので state には残るが、 URL 経由の navigation で
    // reset される (= 期待挙動)。
    const patch = filtersFromSearchParams(searchParams);
    setState({ ...emptyFilterState(), ...patch });
  }, [searchParams]);

  const bounds = useMemo(() => yearBounds(data.manga), [data.manga]);
  const authors = useMemo(() => uniqueAuthors(data.manga, true), [data.manga]);
  const filtered = useMemo(() => applyFilters(data.manga, state), [data.manga, state]);

  // 絞り込み/検索が変わったらページを1に戻す
  useEffect(() => {
    setPage(1);
  }, [state]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const curPage = Math.min(page, totalPages);
  const paged = filtered.slice((curPage - 1) * PAGE_SIZE, curPage * PAGE_SIZE);
  const rangeStart = filtered.length === 0 ? 0 : (curPage - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(curPage * PAGE_SIZE, filtered.length);

  const goPage = (p: number) => {
    setPage(p);
    listTopRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const scrollTop = () =>
    window.scrollTo({ top: 0, behavior: "smooth" });

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <section className="mb-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
            日本の漫画から探す
          </h1>
          <p className="text-sm text-ink/60 mt-1">
            年・著者・出版社・分野・ジャンルで絞り込めます。 全{" "}
            <span className="font-semibold text-ink/80 tabular-nums">{filtered.length}</span> 件中{" "}
            <span className="tabular-nums">{rangeStart}–{rangeEnd}</span> 件表示
            {totalPages > 1 && (
              <span className="text-ink/45">（{curPage} / {totalPages} ページ）</span>
            )}
            。
          </p>
        </div>
        <div className="md:w-96">
          <SearchBox value={state.query} onChange={(q) => setState({ ...state, query: q })} />
        </div>
      </section>

      <CategoryHub data={data} />

      <button
        type="button"
        className="tactile-chip md:hidden mb-4 px-3 py-2.5 text-sm font-medium rounded-card w-full active:scale-[0.99] transition"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "✕ フィルタを閉じる" : "⚙ フィルタで絞り込む"}
      </button>

      <div className="grid md:grid-cols-[240px_1fr] gap-6">
        <div className={(open ? "block" : "hidden") + " md:block"}>
          <FilterPanel
            data={data}
            state={state}
            setState={setState}
            yearBounds={bounds}
            authorOptions={authors}
          />
        </div>
        <div>
          <div ref={listTopRef} className="scroll-mt-20" />
          <MangaGrid
            items={paged}
            publishers={data.publishers}
            genres={data.genres}
            demographics={data.demographics}
          />
          <Pager page={curPage} totalPages={totalPages} onChange={goPage} />
          {filtered.length > 0 && (
            <div className="mt-8 text-center">
              <button
                type="button"
                onClick={scrollTop}
                className="tactile-chip inline-flex items-center rounded-card px-4 py-2 text-sm font-medium active:scale-[0.96] transition"
              >
                ↑ ページ上部へ戻る
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

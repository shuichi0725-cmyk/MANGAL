"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import CategoryHub from "@/components/CategoryHub";
import FilterPanel from "@/components/FilterPanel";
import MangaGrid from "@/components/MangaGrid";
import SearchBox from "@/components/SearchBox";
import {
  applyFilters,
  emptyFilterState,
  filtersFromSearchParams,
  uniqueAuthors,
  yearBounds,
} from "@/lib/filters";
import type { DataBundle } from "@/lib/schema";

type Props = { data: DataBundle };

export default function HomeClient({ data }: Props) {
  const searchParams = useSearchParams();
  const [state, setState] = useState(emptyFilterState());
  const [open, setOpen] = useState(false);

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

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <section className="mb-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
            日本の漫画から探す
          </h1>
          <p className="text-sm text-black/60 mt-1">
            年・著者・出版社・分野・ジャンルで絞り込めます。 全 {data.manga.length} 作品中 {filtered.length} 件表示。
          </p>
        </div>
        <div className="md:w-96">
          <SearchBox value={state.query} onChange={(q) => setState({ ...state, query: q })} />
        </div>
      </section>

      <CategoryHub data={data} />

      <button
        type="button"
        className="md:hidden mb-4 px-3 py-2 text-sm rounded border border-black/15 w-full"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "フィルタを閉じる" : "フィルタを開く"}
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
        <MangaGrid
          items={filtered}
          publishers={data.publishers}
          genres={data.genres}
          demographics={data.demographics}
        />
      </div>
    </div>
  );
}

"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
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
    const patch = filtersFromSearchParams(searchParams);
    if (Object.keys(patch).length > 0) {
      setState((prev) => ({ ...emptyFilterState(), ...prev, ...patch }));
    }
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

"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import CategoryHub from "@/components/CategoryHub";
import FilterPanel from "@/components/FilterPanel";
import MangaGrid from "@/components/MangaGrid";
import ArtBookCard from "@/components/ArtBookCard";
import SearchBox from "@/components/SearchBox";
import Pager from "@/components/ui/Pager";
import {
  applyArtBookFilters,
  applyFilters,
  emptyFilterState,
  filtersFromSearchParams,
  uniqueAuthors,
  yearBounds,
} from "@/lib/filters";
import type { ArtBook, DataBundle, Manga } from "@/lib/schema";

type Props = { data: DataBundle };

const PAGE_SIZE = 100;

export default function HomeClient({ data }: Props) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [state, setState] = useState(emptyFilterState());
  const [open, setOpen] = useState(false);
  const listTopRef = useRef<HTMLDivElement>(null);

  // フィルタ系 URL params(?page を除く)の署名。 ページ送りでフィルタ effect が
  // 再発火して手動フィルタを消さないよう、 page だけの変化では発火させない。
  const filterKey = useMemo(() => {
    const p = new URLSearchParams(searchParams.toString());
    p.delete("page");
    return p.toString();
  }, [searchParams]);

  useEffect(() => {
    // URL の検索 params が source of truth。 emptyFilterState + URL params で
    // 毎回 fresh に組み直す(CategoryHub click や back/forward で filter が累積しない)。
    const patch = filtersFromSearchParams(searchParams);
    setState({ ...emptyFilterState(), ...patch });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterKey]);

  const bounds = useMemo(() => yearBounds(data.manga), [data.manga]);
  const authors = useMemo(() => uniqueAuthors(data.manga, true), [data.manga]);
  // ★画集モード = 一覧を画集に切替(ジャンル欄「画集」チップ)。 漫画用フィルタは非適用。
  const showArt = state.artBooks;
  const filteredManga = useMemo(() => applyFilters(data.manga, state), [data.manga, state]);
  const filteredArt = useMemo(() => applyArtBookFilters(data.artBooks, state), [data.artBooks, state]);
  const filtered: (Manga | ArtBook)[] = showArt ? filteredArt : filteredManga;

  // ページは URL(?page)から導出 = リロード/共有/戻るで復元。 フィルタURL変更
  // (CategoryHub 等)は ?page を含まないので自然と1ページ目に戻る。
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const urlPage = Math.max(1, Number(searchParams.get("page")) || 1);
  const curPage = Math.min(urlPage, totalPages);
  const paged = filtered.slice((curPage - 1) * PAGE_SIZE, curPage * PAGE_SIZE);
  const rangeStart = filtered.length === 0 ? 0 : (curPage - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(curPage * PAGE_SIZE, filtered.length);

  const goPage = (p: number) => {
    const params = new URLSearchParams(searchParams.toString());
    if (p <= 1) params.delete("page");
    else params.set("page", String(p));
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    listTopRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const scrollTop = () =>
    window.scrollTo({ top: 0, behavior: "smooth" });

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <section className="mb-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
            {showArt ? "画集から探す" : "日本の漫画から探す"}
          </h1>
          <p className="text-sm text-ink/60 mt-1">
            {showArt
              ? "漫画家の画集・原画集・イラスト集。 "
              : "年・著者・出版社・分野・ジャンルで絞り込めます。 "}
            全{" "}
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
          {showArt ? (
            <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {(paged as ArtBook[]).map((a) => (
                <li key={a.slug}>
                  <ArtBookCard artBook={a} />
                </li>
              ))}
            </ul>
          ) : (
            <MangaGrid
              items={paged as Manga[]}
              publishers={data.publishers}
              genres={data.genres}
              demographics={data.demographics}
            />
          )}
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

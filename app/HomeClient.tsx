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
  authorsWithKana,
  searchMatches,
  yearBounds,
} from "@/lib/filters";
import type { ArtBook, ListBundle, MangaListItem } from "@/lib/schema";
import { useMangaIndex, useSearchIndex } from "@/lib/useMangaIndex";

type Props = { data: ListBundle };

const PAGE_SIZE = 100;

export default function HomeClient({ data }: Props) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [state, setState] = useState(emptyFilterState());
  const [open, setOpen] = useState(false);
  const listTopRef = useRef<HTMLDivElement>(null);
  // ★テスト環境限定機能(画像なしフィルタ / 情報コピー)。 本番(workers.dev)では非表示。
  const [noCover, setNoCover] = useState(false);
  const [soloNonfirst, setSoloNonfirst] = useState(false);
  const [multiVol, setMultiVol] = useState(false);
  const [noAuthor, setNoAuthor] = useState(false);
  const [mv2026, setMv2026] = useState(false);
  const [volGap, setVolGap] = useState(false);
  const [copied, setCopied] = useState(false);
  const isNoAuthor = (m: MangaListItem) =>
    !m.authors?.length || m.authors.every((a) => !a.name || a.name === "(unknown)");
  const isMv2026 = (m: MangaListItem) => (m.total_volumes ?? 0) >= 2 && m.year_started === 2026;
  const [isPreview, setIsPreview] = useState(false);
  useEffect(() => {
    const h = window.location.hostname;
    setIsPreview(h.includes("preview") || h === "localhost" || h === "127.0.0.1");
  }, []);

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

  // ★フィルターオーバーレイ表示中は背景スクロールを止める(モバイル)
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  // ★一覧 manga は軽量索引をクライアント遅延ロード (= SSR props で 65k を送らない)。
  //   master/画集は props(軽量)。 索引到着までは loading。
  const mangaIndex = useMangaIndex();
  const manga = useMemo(() => mangaIndex ?? [], [mangaIndex]);
  const liveData = useMemo(() => ({ ...data, manga }), [data, manga]);
  const indexLoading = mangaIndex === null;

  // ★検索は別索引(検索索引)を query 有の時だけ遅延ロード → matchedSlugs を一覧 filter と AND 合成。
  const hasQuery = state.query.trim().length > 0;
  const searchIndex = useSearchIndex(hasQuery);
  const searchLoading = hasQuery && searchIndex === null;
  const matchedSlugs = useMemo(
    () => (hasQuery ? searchMatches(state.query, searchIndex ?? []) : null),
    [hasQuery, state.query, searchIndex],
  );

  const bounds = useMemo(() => yearBounds(manga), [manga]);
  const authors = useMemo(() => authorsWithKana(manga, true), [manga]);
  // ★画集モード = 一覧を画集に切替(ジャンル欄「画集」チップ)。 漫画用フィルタは非適用。
  const showArt = state.artBooks;
  const filteredManga = useMemo(() => applyFilters(manga, state, matchedSlugs), [manga, state, matchedSlugs]);
  const filteredArt = useMemo(() => applyArtBookFilters(data.artBooks, state), [data.artBooks, state]);
  // ★テスト専用フィルタ: 画像なし(cover=null) / 1冊≠1巻(solo_nonfirst=統合失敗signal)。
  const filtered: (MangaListItem | ArtBook)[] = useMemo(() => {
    let base = showArt ? filteredArt : filteredManga;
    if (!showArt) {
      if (noCover) base = (base as MangaListItem[]).filter((m) => !m.cover);
      if (soloNonfirst) base = (base as MangaListItem[]).filter((m) => m.solo_nonfirst);
      if (multiVol) base = (base as MangaListItem[]).filter((m) => (m.total_volumes ?? 0) >= 2);
      if (noAuthor) base = (base as MangaListItem[]).filter(isNoAuthor);
      if (mv2026) base = (base as MangaListItem[]).filter(isMv2026);
      if (volGap) base = (base as MangaListItem[]).filter((m) => m.vol_gap);
    }
    return base;
  }, [showArt, filteredArt, filteredManga, noCover, soloNonfirst, multiVol, noAuthor, mv2026, volGap]);
  const noCoverCount = useMemo(
    () => (showArt ? 0 : filteredManga.filter((m) => !m.cover).length),
    [showArt, filteredManga],
  );
  const soloNonfirstCount = useMemo(
    () => (showArt ? 0 : filteredManga.filter((m) => m.solo_nonfirst).length),
    [showArt, filteredManga],
  );
  const multiVolCount = useMemo(
    () => (showArt ? 0 : filteredManga.filter((m) => (m.total_volumes ?? 0) >= 2).length),
    [showArt, filteredManga],
  );
  const noAuthorCount = useMemo(
    () => (showArt ? 0 : filteredManga.filter(isNoAuthor).length),
    [showArt, filteredManga],
  );
  const mv2026Count = useMemo(
    () => (showArt ? 0 : filteredManga.filter(isMv2026).length),
    [showArt, filteredManga],
  );
  const volGapCount = useMemo(
    () => (showArt ? 0 : filteredManga.filter((m) => m.vol_gap).length),
    [showArt, filteredManga],
  );
  // ★表示中(フィルタ後)の情報をクリップボードへ(テスト専用・私への共有用)。
  const copyFiltered = async () => {
    const items = filtered as MangaListItem[];
    const header = "slug\ttitle\tauthors\tpublisher\tvols\tcover";
    const lines = items.map((m) =>
      [
        m.slug,
        m.title,
        (m.authors || []).map((a) => a.name).join(",").slice(0, 50),
        m.publisher || "",
        m.total_volumes ?? "",
        m.cover ? "有" : "無",
      ].join("\t"),
    );
    const text = `# ${items.length}件${noCover ? " (画像なしのみ)" : ""}\n${header}\n${lines.join("\n")}`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      alert("コピー失敗(クリップボード権限)");
    }
  };

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
    <div className={`mx-auto max-w-6xl px-4 py-6${isPreview ? " preview-mode" : ""}`}>
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

      <CategoryHub data={liveData} />

      {/* ★テスト環境限定ツールバー(本番=workers.dev では非表示)。
          ①画像なし=cover無だけ表示 ②コピー=表示中の情報をクリップボードへ(私への共有用) */}
      {isPreview && !showArt && (
        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-card border border-dashed border-[var(--color-accent)]/50 bg-[var(--color-accent)]/5 p-2 text-sm">
          <span className="text-xs font-semibold text-[var(--color-accent)]">🧪 テスト専用</span>
          <button
            type="button"
            onClick={() => setNoCover((v) => !v)}
            className={`tactile-chip rounded-card px-3 py-1.5 font-medium transition active:scale-95 ${
              noCover ? "bg-[var(--color-accent)] text-white" : ""
            }`}
          >
            画像なし{noCover ? " ✓" : ""}（{noCoverCount}）
          </button>
          <button
            type="button"
            onClick={() => setSoloNonfirst((v) => !v)}
            className={`tactile-chip rounded-card px-3 py-1.5 font-medium transition active:scale-95 ${
              soloNonfirst ? "bg-[var(--color-accent)] text-white" : ""
            }`}
            title="1冊しか無いのに その巻が1巻でない(統合失敗/取りこぼし)"
          >
            1冊≠1巻{soloNonfirst ? " ✓" : ""}（{soloNonfirstCount}）
          </button>
          <button
            type="button"
            onClick={() => setMultiVol((v) => !v)}
            className={`tactile-chip rounded-card px-3 py-1.5 font-medium transition active:scale-95 ${
              multiVol ? "bg-[var(--color-accent)] text-white" : ""
            }`}
            title="複数巻ある作品(今回統合した型1の検証用)"
          >
            複数巻{multiVol ? " ✓" : ""}（{multiVolCount}）
          </button>
          <button
            type="button"
            onClick={() => setNoAuthor((v) => !v)}
            className={`tactile-chip rounded-card px-3 py-1.5 font-medium transition active:scale-95 ${
              noAuthor ? "bg-[var(--color-accent)] text-white" : ""
            }`}
            title="著者が(unknown)/空(アンソロ/非漫画の疑い)"
          >
            著者なし{noAuthor ? " ✓" : ""}（{noAuthorCount}）
          </button>
          <button
            type="button"
            onClick={() => setMv2026((v) => !v)}
            className={`tactile-chip rounded-card px-3 py-1.5 font-medium transition active:scale-95 ${
              mv2026 ? "bg-[var(--color-accent)] text-white" : ""
            }`}
            title="複数巻あるのに開始年が2026(年繰上げ漏れ/巻誤統合の疑い・要確認)"
          >
            複数巻2026{mv2026 ? " ✓" : ""}（{mv2026Count}）
          </button>
          <button
            type="button"
            onClick={() => setVolGap((v) => !v)}
            className={`tactile-chip rounded-card px-3 py-1.5 font-medium transition active:scale-95 ${
              volGap ? "bg-[var(--color-accent)] text-white" : ""
            }`}
            title="複数巻あるのに途中の巻が抜けている(fill漏れ/欠番・要確認)"
          >
            巻抜け{volGap ? " ✓" : ""}（{volGapCount}）
          </button>
          <button
            type="button"
            onClick={copyFiltered}
            className="tactile-chip rounded-card px-3 py-1.5 font-medium transition active:scale-95"
          >
            {copied ? "✓ コピーした" : `コピー（${filtered.length}）`}
          </button>
        </div>
      )}

      {/* モバイル: フィルター起動(全画面オーバーレイを開く)。 PC版は右サイドバー常時表示 */}
      <button
        type="button"
        className="tactile-chip md:hidden mb-4 px-3 py-2.5 text-sm font-medium rounded-card w-full active:scale-[0.99] transition"
        onClick={() => setOpen(true)}
      >
        ⚙ フィルターで絞り込む
      </button>

      <div className="grid md:grid-cols-[240px_1fr] gap-6">
        {/* デスクトップ: 常時サイドバー(PC版は不変) */}
        <div className="hidden md:block">
          <FilterPanel
            data={liveData}
            state={state}
            setState={setState}
            yearBounds={bounds}
            authorEntries={authors}
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
          ) : indexLoading || searchLoading ? (
            <div className="tactile rounded-card py-16 text-center">
              <p className="text-2xl animate-pulse" aria-hidden="true">{searchLoading ? "🔍" : "📚"}</p>
              <p className="mt-2 text-sm text-ink/55">
                {searchLoading ? "検索しています…" : "作品データを読み込み中…"}
              </p>
            </div>
          ) : (
            <MangaGrid
              items={paged as MangaListItem[]}
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

      {/* ★モバイル: 全画面オーバーレイ フィルター。 ボタンで徐々に拡大、 ×で徐々に畳む。
          背景は blur+暗転(背後の文脈は見えるが文字は読める)。 PC版(md:)は出さない。 */}
      <div
        className={`md:hidden fixed inset-0 z-50 transition-[opacity,visibility] duration-300 ${
          open ? "visible opacity-100" : "invisible opacity-0 pointer-events-none"
        }`}
        aria-hidden={!open}
      >
        {/* パネル: 下(ボタン側)から徐々に全画面へ拡大。 ★半透過(frosted glass)で
            背後の漫画リストがうっすら透ける。 backdrop-blur で文字も読める。 */}
        <div
          className={`absolute inset-3 flex flex-col overflow-hidden rounded-[26px] border-4 border-white ring-1 ring-black/30 shadow-2xl backdrop-blur-sm origin-bottom transition-[transform,opacity] duration-300 ease-out ${
            open ? "scale-100 opacity-100" : "scale-90 opacity-0"
          }`}
          style={{ background: "color-mix(in srgb, var(--color-surface) 28%, transparent)" }}
        >
          <header className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-line)] shrink-0">
            <h2 className="font-bold text-base">フィルター</h2>
            <button
              type="button"
              aria-label="閉じる"
              onClick={() => setOpen(false)}
              className="tactile-chip rounded-full w-9 h-9 flex items-center justify-center text-lg leading-none active:scale-90 transition"
            >
              ✕
            </button>
          </header>
          <div className="flex-1 overflow-y-auto px-4 py-4 overscroll-contain">
            <FilterPanel
              data={liveData}
              state={state}
              setState={setState}
              yearBounds={bounds}
              authorEntries={authors}
            />
          </div>
          <div className="shrink-0 border-t border-[var(--color-line)] p-3">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="w-full rounded-card bg-[var(--color-accent)] text-white font-semibold py-2.5 active:scale-[0.98] transition"
            >
              結果を見る（{filtered.length}）
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

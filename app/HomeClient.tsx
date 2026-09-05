"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import CategoryHub from "@/components/CategoryHub";
import FilterPanel from "@/components/FilterPanel";
import MangaGrid from "@/components/MangaGrid";
import ArtBookCard from "@/components/ArtBookCard";
import SearchBox from "@/components/SearchBox";
import ShareButtons from "@/components/ShareButtons";
import Pager from "@/components/ui/Pager";
import {
  applyArtBookFilters,
  applyFilters,
  emptyFilterState,
  filtersFromSearchParams,
  filtersToSearchParams,
  type FilterState,
  authorsWithKana,
} from "@/lib/filters";
import { isAltLoading, onAltLoaded, prewarmSearch, searchWithTiers } from "@/lib/clientSearch";
import { ensureFullIndex, isFullIndexLoaded } from "@/lib/useMangaIndex";
import { perfDiag } from "@/lib/perfDiag";
import type { IndexSummary, ArtBook, ListBundle, MangaListItem } from "@/lib/schema";
import { useMangaIndex } from "@/lib/useMangaIndex";

type Props = {
  data: ListBundle;
  /** ★ビルド時に集計した総数・分類件数(2026-08-01)。
   *  フル索引(6MB)が届くまで head 100件だけで件数を計算し、
   *  「全100件」と嘘をついていたのを止めるための先出し値。 */
  summary?: IndexSummary | null;
};

const PAGE_SIZE = 100;

export default function HomeClient({ data, summary }: Props) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  // ★初期stateはURLから同期で組む(2026-08-31 週次前レビュー): ホームwarm+SPA遷移だと
  //   マウント時点でフル索引が手元に在るため、旧 emptyFilterState() 初期化は
  //   「q未適用の全67k件を絞り込み+ソートして一瞬描画→effectでqを当てて作り直し」
  //   という無駄な全件計算+全件グリッドのフラッシュを毎回踏んでいた(MPA時代は
  //   索引到着がeffectより後だったので実害が無かった穴)。
  const [state, setState] = useState(() => ({ ...emptyFilterState(), ...filtersFromSearchParams(searchParams) }));
  const [open, setOpen] = useState(false);
  // ★画面幅に合わないフィルターを外す(2026-08-01)。
  //   旧: PC用サイドバー(hidden md:block)とモバイル用抽斗(md:hidden)の両方が
  //   常時マウントされ、CSSで隠れているだけだった。FilterPanel の動的件数は
  //   67k件の絞り込みを毎回6パス走らせる(本番実測568ms)ので、どの画面幅でも
  //   必ず片方分(568ms)を見えないパネルのために捨てていた。
  //   初期値を "both"(=静的HTMLと同じ両方描画)にしてから水和直後に確定させるので、
  //   水和不一致も起きないし、外す側はもともと display:none = 見た目は1ドットも動かない。
  //   索引(67k)の到着は水和よりずっと後なので、不要な側は重い計算を一度もしない。
  const [viewport, setViewport] = useState<"both" | "desktop" | "mobile">("both");
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)"); // = Tailwind の md ブレイクポイント
    const apply = () => setViewport(mq.matches ? "desktop" : "mobile");
    apply();
    mq.addEventListener("change", apply); // 回転・リサイズで切り替え
    return () => mq.removeEventListener("change", apply);
  }, []);
  const listTopRef = useRef<HTMLDivElement>(null);
  // ★テスト環境限定機能(画像なしフィルタ / 情報コピー)。 本番(workers.dev)では非表示。
  const [noCover, setNoCover] = useState(false);
  const [soloNonfirst, setSoloNonfirst] = useState(false);
  const [multiVol, setMultiVol] = useState(false);
  const [noAuthor, setNoAuthor] = useState(false);
  const [mv2026, setMv2026] = useState(false);
  const [volGap, setVolGap] = useState(false);
  const [coverGap, setCoverGap] = useState(false);
  const [anthology, setAnthology] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copied2, setCopied2] = useState(false);
  const isNoAuthor = (m: MangaListItem) =>
    !m.authors?.length || m.authors.every((a) => !a.name || a.name === "(unknown)");
  const isMv2026 = (m: MangaListItem) => (m.total_volumes ?? 0) >= 2 && m.year_started === 2026;
  const [isPreview, setIsPreview] = useState(false);
  useEffect(() => {
    const h = window.location.hostname;
    // ★隠しコマンド(2026-07-03): URL末尾 #debug で本番でも診断チップON(localStorage永続)・#nodebug でOFF
    if (window.location.hash === "#debug") localStorage.setItem("mangal-diag", "1");
    if (window.location.hash === "#nodebug") localStorage.removeItem("mangal-diag");
    setIsPreview(
      h.includes("preview") || h === "localhost" || h === "127.0.0.1" ||
      localStorage.getItem("mangal-diag") === "1"
    );
  }, []);

  // フィルタ系 URL params(?page を除く)の署名。 ページ送りでフィルタ effect が
  // 再発火して手動フィルタを消さないよう、 page だけの変化では発火させない。
  const filterKey = useMemo(() => {
    const p = new URLSearchParams(searchParams.toString());
    p.delete("page");
    return p.toString();
  }, [searchParams]);

  // ★初回マウントはskip(2026-08-31): useState初期化が同じsearchParamsから組んだ直後なので、
  //   ここで同内容のsetStateを打つと state の参照が替わり filteredManga(67k絞り込み)を
  //   もう一度払う。URL変化(back/forward・CategoryHub)時だけ組み直す。
  const filterKeyInitRef = useRef(true);
  useEffect(() => {
    if (filterKeyInitRef.current) {
      filterKeyInitRef.current = false;
      return;
    }
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
  const mangaIndex = useMangaIndex({ withCatch: true }); // カード表示=キャッチ文が要る
  const manga = useMemo(() => mangaIndex ?? [], [mangaIndex]);
  const liveData = useMemo(() => ({ ...data, manga }), [data, manga]);
  const indexLoading = mangaIndex === null;

  // ★検索v2(2026-07-14): 検索専用索引を廃止し一覧索引を共有(前計算haystack+逐次絞り込み+2段照合)。
  //   alt(別名)は題名ヒット0の時だけ遅延fetch → 到着したら altTick で再検索。
  const hasQuery = state.query.trim().length > 0;
  const [altTick, setAltTick] = useState(0);
  useEffect(() => onAltLoaded(() => setAltTick((v) => v + 1)), []);
  useEffect(() => {
    if (mangaIndex) prewarmSearch(mangaIndex); // 手すきで前計算(検索開始時のワンショット遅延を消す)
  }, [mangaIndex]);
  useEffect(() => {
    if (hasQuery) ensureFullIndex(); // 検索確定=フル索引を即時要求(head 200件だけの誤答窓を閉じる)
  }, [hasQuery]);
  const searchLoading = hasQuery && mangaIndex === null;
  // ★偽0件対策=B案(2026-08-18 ユーザ裁定): フル索引が届く前(head100件だけ)や、題名ヒット0で
  //   別名(alt)照合がまだの間は「検索が確定していない」。この間は
  //   ①0件と断言しない(検索中表示に差し替え) ②部分結果には「検索中」バッジを重ねる。
  //   再計算タイミング: full到着=_indexListeners→再レンダー / alt到着=altTick で担保される。
  const searchPending = hasQuery && (!isFullIndexLoaded() || isAltLoading());
  // ★フィルターパネルへ渡す「まだ確定していない」signal(2026-09-05)。
  //   索引未到着/検索確定前は全facetが0になり、絞り込んで0件になった廃墟と区別が付かなかった。
  const panelLoading = indexLoading || searchLoading || searchPending;
  const searchTiers = useMemo(
    () => (hasQuery ? searchWithTiers(state.query, manga) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [hasQuery, state.query, manga, altTick],
  );
  const matchedSlugs = useMemo(
    () => (searchTiers ? new Set(searchTiers.keys()) : null),
    [searchTiers],
  );

  const authors = useMemo(() => authorsWithKana(manga, true), [manga]);
  // ★画集モード = 一覧を画集に切替(ジャンル欄「画集」チップ)。 漫画用フィルタは非適用。
  const showArt = state.artBooks;
  // ★空状態(フィルタ無し・検索無し)の結果はキャッシュ(2026-07-22): 検索×リセット時に
  //   フル索引67kの絞り込み+ソートを同期でやり直してもたつく問題の是正。
  //   stateはeffectで毎回新objectに再構築されるため、参照でなく「空かどうか」で判定する。
  const emptyCacheRef = useRef<{ manga: MangaListItem[]; out: MangaListItem[] } | null>(null);
  const filteredManga = useMemo(() => {
    const isEmpty = !matchedSlugs && filtersToSearchParams(state).toString() === "";
    if (isEmpty && emptyCacheRef.current?.manga === manga) return emptyCacheRef.current.out;
    let out = applyFilters(manga, state, matchedSlugs);
    // ★案A(2026-07-23): 検索中×並び順既定 → 一致の強い順(完全一致→前方→部分→著者→ローマ字)。
    //   Array.sortは安定なので同tier内は既定の人気順が保たれる。手動選択時は尊重(現行ルール)。
    if (searchTiers && state.sort === "default") {
      out = [...out].sort((a, b) => (searchTiers.get(a.slug) ?? 9) - (searchTiers.get(b.slug) ?? 9));
    }
    if (isEmpty) emptyCacheRef.current = { manga, out };
    return out;
  }, [manga, state, matchedSlugs, searchTiers]);
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
      if (coverGap) base = (base as MangaListItem[]).filter((m) => m.cover_gap);
      if (anthology) base = (base as MangaListItem[]).filter((m) => m._anthology);
    }
    return base;
  }, [showArt, filteredArt, filteredManga, noCover, soloNonfirst, multiVol, noAuthor, mv2026, volGap, coverGap, anthology]);
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
  const anthologyCount = useMemo(
    () => (showArt ? 0 : filteredManga.filter((m) => m._anthology).length),
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

  // ★コピー2(テスト専用 2026-07-16): 「漫画名　作者名」の2項目だけを1作1行で(ユーザ要望)。
  const copyFiltered2 = async () => {
    const items = filtered as MangaListItem[];
    const lines = items.map(
      (m) => `${m.title}　${(m.authors || []).map((a) => a.name).join("・")}`,
    );
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      setCopied2(true);
      setTimeout(() => setCopied2(false), 2000);
    } catch {
      alert("コピー失敗(クリップボード権限)");
    }
  };

  // ページは URL(?page)から導出 = リロード/共有/戻るで復元。 フィルタURL変更
  // (CategoryHub 等)は ?page を含まないので自然と1ページ目に戻る。
  // ★フル索引が届く前は head(100件)しか手元に無い。絞り込みも検索も無い間は
  //   その100件を数えた値でなく、ビルド時に全件を集計した summary を見せる。
  //   絞り込んだ瞬間には実データの件数へ戻る(嘘の交差件数を出さない)。 2026-08-01
  const noNarrowing = !matchedSlugs && filtersToSearchParams(state).toString() === "";
  const useSummary = !!summary && !showArt && noNarrowing && !isFullIndexLoaded();
  const shownTotal = useSummary && summary ? summary.total : filtered.length;
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

  // ★フィルタ変更をURLへ反映(2026-07-22): URLがsource of truthなのにFilterPanelの
  //   変更が書かれておらず、詳細→戻るで全フィルタが消えていた(ユーザ報告)。
  //   検索(?q)と同機構: replaceで書く+?pageはリセット。effectがURLから再構築する。
  // ★フィルタ(検索語以外)が有効か = リセットボタンの表示条件
  const hasActiveFilters = useMemo(() => {
    const p = filtersToSearchParams(state);
    p.delete("q");
    return p.toString() !== "";
  }, [state]);
  const applyState = (next: FilterState) => {
    setState(next);
    const params = filtersToSearchParams(next, new URLSearchParams(searchParams.toString()));
    params.delete("page");
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

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
            <span className="font-semibold text-ink/80 tabular-nums">{shownTotal.toLocaleString()}</span> 件中{" "}
            <span className="tabular-nums">{rangeStart}–{rangeEnd}</span> 件表示
            {useSummary ? (
              <span className="text-ink/45">（読み込み中…）</span>
            ) : (
              totalPages > 1 && (
                <span className="text-ink/45">（{curPage} / {totalPages} ページ）</span>
              )
            )}
            。
          </p>
        </div>
        <div className="md:w-96">
          {/* ★確定した検索語はURL(?q=)へ書く=source of truth。詳細→戻るで検索語・結果が復元される(2026-07-11 ユーザ仕様) */}
          <SearchBox
            value={state.query}
            onChange={(q) => {
              setState({ ...state, query: q });
              const params = new URLSearchParams(searchParams.toString());
              if (q) params.set("q", q);
              else params.delete("q");
              params.delete("page");
              const qs = params.toString();
              router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
            }}
          />
        </div>
      </section>

      {/* ★filtered=現在の絞り込み後(検索込み)を渡す=タイル件数が交差件数になる(2026-07-12) */}
      <CategoryHub data={liveData} filtered={showArt ? undefined : filteredManga} summary={useSummary ? summary : null} />

      {/* ★テスト環境限定ツールバー(本番=workers.dev では非表示)。
          ①画像なし=cover無だけ表示 ②コピー=表示中の情報をクリップボードへ(私への共有用) */}
      {/* ★実機の実数字(2026-08-01)。PCの測定では当たらないので端末側で拾う。
          ★haystack同期 = 検索を押した瞬間に残りを同期で埋めた時間(=固まりの最有力候補) */}
      {isPreview && (
        <div className="mb-3 rounded-card border border-dashed border-[var(--color-accent)]/40 px-3 py-2 text-[10px] leading-relaxed text-ink/60">
          <span className="font-bold text-[var(--color-accent)]">診断</span>{" "}
          索引: 取得{perfDiag.fullFetchMs ?? "–"}ms / デコード{perfDiag.fullDecodeMs ?? "–"}ms{" · "}
          <span className="font-bold text-rose-600">
            haystack同期{perfDiag.haySyncMs}ms({perfDiag.haySyncRows.toLocaleString()}行)
          </span>{" · "}
          空き時間{perfDiag.hayIdleMs}ms({perfDiag.hayIdleRows.toLocaleString()}行){" · "}
          検索{perfDiag.searchMs ?? "–"}ms({perfDiag.searchHits ?? "–"}件){" · "}
          別名{perfDiag.altFetchMs ?? "–"}ms{" · "}
          索引{isFullIndexLoaded() ? "完備" : "読込中"}({manga.length.toLocaleString()}件)
        </div>
      )}
      {isPreview && !showArt && (
        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-card border border-dashed border-[var(--color-accent)]/50 bg-[var(--color-accent)]/5 p-2 text-sm">
          <span className="text-xs font-semibold text-[var(--color-accent)]">🧪 テスト専用</span>
          <button
            type="button"
            onClick={() => setNoCover((v) => !v)}
            className={`tactile-chip rounded-card px-3 py-1.5 font-medium transition active:scale-95 ${
              noCover ? "bg-[var(--color-accent)] text-[var(--color-on-accent)]" : ""
            }`}
          >
            画像なし{noCover ? " ✓" : ""}（{noCoverCount}）
          </button>
          <button
            type="button"
            onClick={() => setSoloNonfirst((v) => !v)}
            className={`tactile-chip rounded-card px-3 py-1.5 font-medium transition active:scale-95 ${
              soloNonfirst ? "bg-[var(--color-accent)] text-[var(--color-on-accent)]" : ""
            }`}
            title="1冊しか無いのに その巻が1巻でない(統合失敗/取りこぼし)"
          >
            1冊≠1巻{soloNonfirst ? " ✓" : ""}（{soloNonfirstCount}）
          </button>
          <button
            type="button"
            onClick={() => setMultiVol((v) => !v)}
            className={`tactile-chip rounded-card px-3 py-1.5 font-medium transition active:scale-95 ${
              multiVol ? "bg-[var(--color-accent)] text-[var(--color-on-accent)]" : ""
            }`}
            title="複数巻ある作品(今回統合した型1の検証用)"
          >
            複数巻{multiVol ? " ✓" : ""}（{multiVolCount}）
          </button>
          <button
            type="button"
            onClick={() => setNoAuthor((v) => !v)}
            className={`tactile-chip rounded-card px-3 py-1.5 font-medium transition active:scale-95 ${
              noAuthor ? "bg-[var(--color-accent)] text-[var(--color-on-accent)]" : ""
            }`}
            title="著者が(unknown)/空(アンソロ/非漫画の疑い)"
          >
            著者なし{noAuthor ? " ✓" : ""}（{noAuthorCount}）
          </button>
          <button
            type="button"
            onClick={() => setMv2026((v) => !v)}
            className={`tactile-chip rounded-card px-3 py-1.5 font-medium transition active:scale-95 ${
              mv2026 ? "bg-[var(--color-accent)] text-[var(--color-on-accent)]" : ""
            }`}
            title="複数巻あるのに開始年が2026(年繰上げ漏れ/巻誤統合の疑い・要確認)"
          >
            複数巻2026{mv2026 ? " ✓" : ""}（{mv2026Count}）
          </button>
          <button
            type="button"
            onClick={() => setVolGap((v) => !v)}
            className={`tactile-chip rounded-card px-3 py-1.5 font-medium transition active:scale-95 ${
              volGap ? "bg-[var(--color-accent)] text-[var(--color-on-accent)]" : ""
            }`}
            title="複数巻あるのに途中の巻が抜けている(fill漏れ/欠番・要確認)"
          >
            巻抜け{volGap ? " ✓" : ""}（{volGapCount}）
          </button>
          <button
            type="button"
            onClick={() => setCoverGap((v) => !v)}
            className={`tactile-chip rounded-card px-3 py-1.5 font-medium transition active:scale-95 ${
              coverGap ? "bg-[var(--color-accent)] text-[var(--color-on-accent)]" : ""
            }`}
            title="複数巻あるのに途中の巻が抜けている(fill漏れ/欠番・要確認)"
          >
            書影欠け{coverGap ? " ✓" : ""}（{manga.filter((m) => m.cover_gap).length}）
          </button>
          <button
            type="button"
            onClick={() => setAnthology((v) => !v)}
            className={`tactile-chip rounded-card px-3 py-1.5 font-medium transition active:scale-95 ${
              anthology ? "bg-[var(--color-accent)] text-[var(--color-on-accent)]" : ""
            }`}
            title="アンソロジー統合ページ(本番化前の点検用)"
          >
            アンソロジー{anthology ? " ✓" : ""}（{anthologyCount}）
          </button>
          <button
            type="button"
            onClick={copyFiltered}
            className="tactile-chip rounded-card px-3 py-1.5 font-medium transition active:scale-95"
          >
            {copied ? "✓ コピーした" : `コピー（${filtered.length}）`}
          </button>
          <button
            type="button"
            onClick={copyFiltered2}
            className="tactile-chip rounded-card px-3 py-1.5 font-medium transition active:scale-95"
          >
            {copied2 ? "✓ コピーした" : `コピー2（${filtered.length}）`}
          </button>
        </div>
      )}

      {/* モバイル: フィルター起動(全画面オーバーレイを開く)。 PC版は右サイドバー常時表示 */}
      <button
        type="button"
        className="tactile-chip md:hidden mb-2 px-3 py-2.5 text-sm font-medium rounded-card w-full active:scale-[0.99] transition"
        onClick={() => setOpen(true)}
      >
        ⚙ フィルターで絞り込む
      </button>
      {/* ★フィルタ有効時のみ: その場でリセット(2026-07-22 ユーザ要望=パネルを開かず解除。
          空状態キャッシュに当たるので即時に既定表示へ戻る) */}
      {hasActiveFilters && (
        <button
          type="button"
          className="md:hidden mb-4 px-3 py-2 text-xs rounded-card w-full border border-[var(--color-line)] bg-[var(--color-surface)] text-ink/70 active:scale-[0.99] transition"
          onClick={() => applyState({ ...emptyFilterState(), query: state.query })}
        >
          ✕ フィルターをリセット
        </button>
      )}
      {/* 共有(X/LINE/共有=詳細頁と同型。2026-08-03 ユーザ要望「絞り込むの下」)。
          URLは押した瞬間の現在URL(絞り込み条件つき)=受け取った人に同じ検索結果が出る */}
      <ShareButtons
        title={`${state.query.trim() ? `漫画検索「${state.query.trim()}」` : "漫画を探す"} ${shownTotal.toLocaleString()}件 - MANGAL`}
        titleSuffix={false}
        url="https://mangal-db.com/browse"
        getUrl={() => window.location.href}
        className="mb-4 flex flex-wrap items-center gap-2"
      />

      <div className="grid md:grid-cols-[240px_1fr] gap-6">
        {/* デスクトップ: 常時サイドバー(PC版は不変。 モバイルでは水和直後に外す=見た目は不変) */}
        {viewport !== "mobile" && (
          <div className="hidden md:block">
            <FilterPanel
              data={liveData}
              state={state}
              setState={applyState}
              authorEntries={authors}
              matchedSlugs={matchedSlugs}
              loading={panelLoading}
              stickyTop="top-14"
            />
          </div>
        )}
        <div className="min-w-0">
          <div ref={listTopRef} className="scroll-mt-20" />
          {showArt ? (
            <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {(paged as ArtBook[]).map((a) => (
                <li key={a.slug}>
                  <ArtBookCard artBook={a} />
                </li>
              ))}
            </ul>
          ) : indexLoading || searchLoading || (searchPending && paged.length === 0) ? (
            /* ★検索確定前(フル索引/alt照合待ち)にヒット0でも「0件」と断言しない(B案) */
            <div className="tactile rounded-card py-16 text-center">
              <p className="text-2xl animate-pulse" aria-hidden="true">{hasQuery ? "🔍" : "📚"}</p>
              <p className="mt-2 text-sm text-ink/55">
                {hasQuery
                  ? summary?.total
                    ? `検索しています…(全${summary.total.toLocaleString()}作品を照合中)`
                    : "検索しています…"
                  : "作品データを読み込み中…"}
              </p>
            </div>
          ) : (
            <>
              {searchPending && (
                /* ★フル索引到着前の途中結果バッジ(B案: 部分ヒットは見せるが「まだ途中」と明示) */
                <p className="mb-3 flex items-center gap-1.5 text-[12px] text-ink/55">
                  <span className="animate-pulse" aria-hidden="true">🔍</span>
                  検索中…{summary?.total ? ` 全${summary.total.toLocaleString()}作品を照合しています` : ""}(ここまでの途中結果)
                </p>
              )}
              <MangaGrid
                items={paged as MangaListItem[]}
                publishers={data.publishers}
                genres={data.genres}
                demographics={data.demographics}
              />
            </>
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
          背景は blur+暗転(背後の文脈は見えるが文字は読める)。 PC版(md:)は出さない。
          ★PCでは水和直後に丸ごと外す(もともと md:hidden = 見た目不変、計算だけ消える) */}
      {viewport !== "desktop" && (
      <div
        className={`md:hidden fixed inset-0 z-50 transition-[opacity,visibility] duration-300 ${
          open ? "visible opacity-100" : "invisible opacity-0 pointer-events-none"
        }`}
        aria-hidden={!open}
      >
        {/* パネル: 下(ボタン側)から徐々に全画面へ拡大。
            ★地の不透明度(2026-09-05): 旧 28%(=72%透過)は背後の一覧が透けて見出し・件数が
            読めなかった(ユーザ報告)。frosted glass の意匠は blur で保ち、地は 94% へ寄せる。 */}
        <div
          className={`absolute inset-3 flex flex-col overflow-hidden rounded-[26px] border-4 border-white ring-1 ring-black/30 shadow-2xl backdrop-blur-sm origin-bottom transition-[transform,opacity] duration-300 ease-out ${
            open ? "scale-100 opacity-100" : "scale-90 opacity-0"
          }`}
          style={{ background: "color-mix(in srgb, var(--color-surface) 94%, transparent)" }}
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
              setState={applyState}
              authorEntries={authors}
              matchedSlugs={matchedSlugs}
              loading={panelLoading}
            />
          </div>
          <div className="shrink-0 border-t border-[var(--color-line)] p-3">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="w-full rounded-card bg-[var(--color-accent)] text-[var(--color-on-accent)] font-semibold py-2.5 active:scale-[0.98] transition"
            >
              結果を見る（{filtered.length}）
            </button>
          </div>
        </div>
      </div>
      )}
    </div>
  );
}

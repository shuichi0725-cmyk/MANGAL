"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import FilterPanel from "@/components/FilterPanel";
import ShareButtons from "@/components/ShareButtons";
import {
  applyFilters,
  authorsWithKana,
  emptyFilterState,
  filtersFromSearchParams,
  filtersToSearchParams,
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
import { isAltLoading, onAltLoaded, prewarmSearch, searchWithTiers } from "@/lib/clientSearch";
import { SORTS, sortRows, volCount, latestDate, type SortId } from "@/lib/listSort";
import { useMangaIndex, ensureFullIndex, isFullIndexLoaded } from "@/lib/useMangaIndex";

/** 一覧表クライアント: 絞り込み=既存の多窓フィルター(トップと同じ)、並び順=独立チップ。
 *  「完結×ジャンル×作者×開始が古い順」のような自由なAND合成が成立する。 */

// ★並べ替えは lib/listSort.ts に切り出し済み(2026-08-01)。
//   理由: 実索引に対するスナップショット試験(lib/searchSnapshot.test.ts)が
//   「本番と同じ並べ替え」を通せるようにするため。ここにコピーを持たない。

export default function ListClient({ data }: { data: ListBundle }) {
  // ★テストモード判定(HomeClientと同じ): preview/localhost or #debug。テスト時は題名列を最長題に合わせる(チェック用・ユーザ要望 2026-07-06)
  const [isPreview, setIsPreview] = useState(false);
  useEffect(() => {
    const h = window.location.hostname;
    setIsPreview(h.includes("preview") || h === "localhost" || h === "127.0.0.1" || localStorage.getItem("mangal-diag") === "1");
  }, []);
  // ★初期stateはURLから同期で組む(2026-09-01: HomeClient d8eff7ce6 の移植)。
  //   旧= emptyFilterState()で初期化→mount effectでURL反映。ホームのサイドバー検索が
  //   SPA遷移(/list?q=)で着地すると索引が手元に在るため「q未適用の全件を絞込+ソートして
  //   一瞬描画→effectでqを当てて作り直し」= 全件二重計算+人気順一覧のフラッシュを毎回踏んでいた
  //   (MPA時代は索引到着がeffectより後で見えなかった穴)。useSearchParams は静的書き出しで
  //   Suspense境界までCSRに落ちる(app/list/page.tsx)ので、旧window.location初期化にあった
  //   水和不一致の芽も同時に消える。
  //   ★q は FilterState.query に写さない: filtersFromSearchParams は q を query にも写す(browse用)が、
  //   ここで消さないと検索+絞り込みの二重適用になり「?q=で着地するとフィルター(1)が立って0件」
  //   (2026-07-29 ユーザ報告=サイドバー検索全滅の根因。書き込み側 applyState の params.delete("q") と対)。
  const searchParams = useSearchParams();
  const stateFromParams = (sp: { get(k: string): string | null; toString(): string }): FilterState => {
    const patch = filtersFromSearchParams(sp as unknown as URLSearchParams);
    delete (patch as { query?: string }).query;
    // ★artBooks も落とす(2026-09-05): 一覧表は画集を扱わない(列が巻/著者/最新刊日の漫画専用表で
    //   state.artBooks を一度も読まない)。落とさないと ?artBooks=true 着地で「フィルター(1)」だけが
    //   立ち、対応するチップも表示の変化も無い幽霊条件になる。
    delete (patch as { artBooks?: boolean }).artBooks;
    return { ...emptyFilterState(), ...patch };
  };
  const [state, setState] = useState<FilterState>(() => stateFromParams(searchParams));
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState(() => searchParams.get("q") ?? "");             // 確定済み検索語(=絞込に効く)
  const [qInput, setQInput] = useState(() => searchParams.get("q") ?? "");   // 入力中の文字(★ボタン/Enterまで検索しない 2026-07-11 ユーザ仕様)
  // ★URL変化(ホーム→/list?q=a→ホーム→/list?q=b のSPA再着地・back/forward)だけ組み直す。
  //   初回はuseState初期化と同内容なのでskip(同内容のsetStateでも参照が替わり67k絞込を払い直すため)。
  //   自前の history.replaceState 書き戻しも searchParams に映る(Next14.1+)ので、値が同じなら触らない。
  const spKey = searchParams.toString();
  const spInitRef = useRef(true);
  useEffect(() => {
    if (spInitRef.current) {
      spInitRef.current = false;
      return;
    }
    const uq = searchParams.get("q") ?? "";
    if (uq !== q) {
      setQ(uq);
      setQInput(uq);
    }
    const next = stateFromParams(searchParams);
    if (JSON.stringify(next) !== JSON.stringify(state)) setState(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spKey]);
  // ★フィルタ変更をURLへ書き戻し(q/n/sと同機構。replaceで履歴を汚さない)
  const applyState = (next: FilterState) => {
    setState(next);
    const url = new URL(window.location.href);
    const params = filtersToSearchParams(next, url.searchParams);
    params.delete("q"); // qは別state管理(下のeffectが書く)
    if (q) params.set("q", q);
    window.history.replaceState(null, "", url.toString());
  };
  // ★q変更をURLへ書き戻し(replace=履歴を汚さない)。詳細→OS戻るで検索語が消えない(2026-07-10 ユーザ相談)
  useEffect(() => {
    const url = new URL(window.location.href);
    if (q) url.searchParams.set("q", q);
    else url.searchParams.delete("q");
    window.history.replaceState(null, "", url.toString());
  }, [q]);
  // ★既定=人気順(2026-07-11 ユーザ仕様: 検索前のデフォルトは人気順)
  // ★表示件数(n)/並び順(s)もURLから復元(2026-07-14 ユーザ報告「さらに表示→詳細→戻るで先頭に戻る」。qと同じ手法)
  const [sort, setSort] = useState<SortId>(() => {
    if (typeof window === "undefined") return "popularity";
    const s = new URLSearchParams(window.location.search).get("s");
    return SORTS.some((x) => x.id === s) ? (s as SortId) : "popularity";
  });
  const [sortTouched, setSortTouched] = useState<boolean>(
    () => typeof window !== "undefined" && new URLSearchParams(window.location.search).has("s"),
  );
  // ★初期表示=100件(2026-06-13 ユーザ裁定「初期100件くらいが丁度よい」。実装が200のままだった
  //   のを2026-07-29 ユーザ指摘で是正)
  const [limit, setLimit] = useState<number>(() => {
    if (typeof window === "undefined") return 100;
    const n = parseInt(new URLSearchParams(window.location.search).get("n") || "", 10);
    return Number.isFinite(n) && n > 100 ? n : 100;
  });
  useEffect(() => {
    const url = new URL(window.location.href);
    if (limit > 100) url.searchParams.set("n", String(limit));
    else url.searchParams.delete("n");
    if (sortTouched) url.searchParams.set("s", sort);
    else url.searchParams.delete("s");
    window.history.replaceState(null, "", url.toString());
  }, [limit, sort, sortTouched]);
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
  // ★著者50音リストはフィルター抽斗を開くまで作らない(2026-08-01)。
  //   一覧の FilterPanel は open の時だけマウントされるのに、この useMemo は索引到着と同時に
  //   走っていた(67k件×著者を Map に畳んで日本語ソート。実測166ms)。抽斗を一度も開かない
  //   閲覧者はこの費用を丸ごと払わされ、しかも初期表示直後という一番効く瞬間に固まっていた。
  //   一度開いたら以後は manga 依存で保持する(開閉のたびに作り直さない)。
  const [filterUsed, setFilterUsed] = useState(false);
  useEffect(() => {
    if (open) setFilterUsed(true);
  }, [open]);
  const authors = useMemo(
    () => (filterUsed ? authorsWithKana(manga, true) : []),
    [manga, filterUsed],
  );
  const nActive = activeCount(state);

  // ★スクロール位置の復元(詳細→戻る): 遷移時にsessionStorageへ保存(下のLink onClick)→
  //   索引ロード後に復元。head先行(100件)→full到着で高さが伸びるため、目標に届くまで再試行し
  //   届いた時点(or full到着後)でキーを消す。
  useEffect(() => {
    if (indexLoading) return;
    const sv = sessionStorage.getItem("mangal-list-scroll");
    if (sv == null) return;
    const y = Number(sv);
    requestAnimationFrame(() => {
      window.scrollTo(0, y);
      if (Math.abs(window.scrollY - y) < 2 || manga.length > 250) {
        sessionStorage.removeItem("mangal-list-scroll");
      }
    });
  }, [indexLoading, manga]);

  // ★検索はトップと同じ本体(clientSearch)に統一(2026-07-21。旧: 素朴なincludes照合が
  //   ここだけ残り、かな/ローマ字/別名/複数語が効かず「トップで出るのに一覧表で出ない」非対称)
  useEffect(() => {
    if (mangaIndex) prewarmSearch(mangaIndex);
  }, [mangaIndex]);
  // ★検索クエリがある間はフル索引を即時要求(2026-07-31 ユーザ報告「検索押してから表示まで
  //   めっちゃ時間かかる」)。旧: idleの2秒待ちに乗るだけで、?q=着地(PCサイドバー検索)は
  //   head100件に対する誤答→数秒後にフル置換、という体感だった。
  useEffect(() => {
    if (q.trim()) ensureFullIndex();
  }, [q]);
  const [altTick, setAltTick] = useState(0);
  useEffect(() => onAltLoaded(() => setAltTick((v) => v + 1)), []);
  // ★検索の一致集合は rows の外へ出す(2026-09-05): フィルターパネルへ matchedSlugs として
  //   渡すため。旧: rows の内側に閉じていたので渡せず、パネルの件数だけが検索を無視した
  //   全件基準(ONE PIECE 15件のときに「完結 61,726」)で出ていた(/browse は元から渡していた)。
  const needle = q.trim();
  const searchTiers = useMemo(
    () => (needle ? searchWithTiers(needle, manga) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [needle, manga, altTick],
  );
  const matchedSlugs = useMemo(
    () => (searchTiers ? new Set(searchTiers.keys()) : null),
    [searchTiers],
  );
  const rows = useMemo(() => {
    let r = applyFilters(manga, state);
    if (slugfixOnly) r = r.filter((m) => m._slugfix);
    if (searchTiers) {
      const hit = searchTiers;
      r = r.filter((m) => hit.has(m.slug));
    }
    // ★検索時の既定=人気順(2026-07-05 ユーザ要望: 検索したら人気順で出る)。手動選択があればそれを尊重
    const effSort: SortId = needle && !sortTouched ? "popularity" : sort;
    return sortRows(r, effSort, searchTiers, sortTouched);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [manga, state, needle, searchTiers, sort, sortTouched, slugfixOnly]);

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
            className="min-w-0 flex-1 rounded-full border border-[var(--color-line)] bg-[var(--color-surface)] px-3.5 py-1.5 text-[13px] outline-none focus:border-[var(--color-accent)]"
          />
          <button
            type="submit"
            className="spring-press shrink-0 rounded-full bg-[var(--color-accent)] px-3.5 py-1.5 text-[12px] font-bold text-[var(--color-on-accent)]"
          >
            検索
          </button>
          <button
            type="button"
            onClick={() => setOpen(true)}
            className={`spring-press shrink-0 rounded-full px-3 py-1.5 text-[12px] font-bold ${
              nActive > 0 ? "bg-[var(--color-accent)] text-[var(--color-on-accent)]" : "border border-[var(--color-line)] bg-[var(--color-surface)] text-ink/75"
            }`}
          >
            ⚙ フィルター{nActive > 0 ? ` (${nActive})` : ""}
          </button>
          {/* ★フィルタ有効時のみ: パネルを開かずその場でリセット(2026-07-22 ユーザ要望) */}
          {nActive > 0 && (
            <button
              type="button"
              onClick={() => applyState(emptyFilterState())}
              className="spring-press shrink-0 rounded-full px-3 py-1.5 text-[12px] border border-[var(--color-line)] bg-[var(--color-surface)] text-ink/60"
            >
              ✕ リセット
            </button>
          )}
        </form>
        <div className="mt-2 flex items-center gap-1.5 overflow-x-auto no-scrollbar pb-1">
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
              slugfixOnly ? "bg-[var(--color-accent)] text-[var(--color-on-accent)]" : "border border-[var(--color-accent)]/40 bg-[var(--color-surface)] text-[var(--color-accent)]"
            }`}
          >
            slug修正のみ
          </button>
        </div>
      </div>
      <p className="px-3 pb-1 text-[11px] text-ink/50">
        {q.trim() && !isFullIndexLoaded() ? (
          // ★フル索引が届くまでの検索結果は暫定(head100件相当)。到着時にlistener経由で再レンダーされ確定する
          <span className="text-[var(--color-accent)]">検索中…(全作品データ読み込み中)</span>
        ) : (
          <>
            {rows.length.toLocaleString()} 件{nActive > 0 || q ? <span className="text-ink/40">(絞り込み中)</span> : null}
          </>
        )}
      </p>

      {/* 共有(X/LINE/共有=詳細頁と同型。2026-08-03 ユーザ要望「件数の下・題名の上」)。
          URLは押した瞬間の現在URL(検索語・絞り込み・並び順つき)=受け取った人に同じ一覧が出る */}
      <div className="px-3 pb-2">
        <ShareButtons
          title={`漫画一覧${q.trim() ? `「${q.trim()}」` : ""} ${rows.length.toLocaleString()}件 - MANGAL`}
          titleSuffix={false}
          url="https://mangal-db.com/list"
          getUrl={() => window.location.href}
          className="flex flex-wrap items-center gap-2"
        />
      </div>

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
                    <Link
                      href={`/manga/${m.slug}`}
                      onClick={() => sessionStorage.setItem("mangal-list-scroll", String(window.scrollY))}
                      className="spring-press block whitespace-nowrap font-medium text-[var(--list-link,#1f4e79)] active:underline"
                    >
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
                {/* ★applyState を通す(2026-09-05): 旧 setState は state だけ消して URL を残したため、
                    解除したはずの ?genre=... が残り、リロード・共有・戻るで条件が復活していた
                    (上部の「✕ リセット」は元から applyState = 2つのリセットで挙動が違った)。 */}
                <button onClick={() => applyState(emptyFilterState())} className="spring-press rounded-full border border-[var(--color-line)] px-3 py-1 text-[11px] text-ink/65">
                  リセット
                </button>
                <button onClick={() => setOpen(false)} className="spring-press rounded-full bg-ink px-3 py-1 text-[11px] font-bold text-white">
                  閉じる
                </button>
              </div>
            </div>
            <FilterPanel
              data={liveData}
              state={state}
              setState={applyState}
              authorEntries={authors}
              matchedSlugs={matchedSlugs}
              loading={indexLoading || (!!needle && (!isFullIndexLoaded() || isAltLoading()))}
              showSort={false}
              showArtBooks={false}
            />
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

import { useDeferredValue, useMemo, useState } from "react";
import {
  applyArtBookFilters,
  filterItems,
  emptyFilterState,
  volumeBucket,
  VOLUME_BUCKETS,
  type FilterState,
  type SortKey,
} from "@/lib/filters";
import type { ListBundle, MangaListItem, StatusT } from "@/lib/schema";
import { ChipButton } from "@/components/ui/Chip";
import AuthorKanaIndex from "@/components/AuthorKanaIndex";

type Props = {
  data: ListBundle;
  state: FilterState;
  setState: (next: FilterState) => void;
  authorEntries: { name: string; kana: string }[];
  /** ★検索中の一致slug集合(2026-08-01)。渡さないと applyFilters が state.query で全行を弾き、
   *  ファセット件数が全部0になる(68,724行を6回走査して0を出していた)。 */
  matchedSlugs?: Set<string> | null;
  /** ★索引/検索がまだ確定していない(2026-09-05)。全facet 0 の「廃墟」を
   *  「0件」と誤読させないための明示signal。 未指定なら索引の有無から推定。 */
  loading?: boolean;
  /** ★画集チップを出すか(2026-09-05)。 一覧表(/list)は state.artBooks を一度も読まない
   *  (列が 巻/著者/最新刊日 の漫画専用表)ので、押しても表が変わらない死んだUIだった。 */
  showArtBooks?: boolean;
  /** ★並び順セレクトを出すか(2026-09-05)。 一覧表(/list)は上部に本物の並び順チップが在り、
   *  そちらが最後に必ず sortRows で並べ直すため、ここのセレクトは押しても効かない死んだUIだった。 */
  showSort?: boolean;
  /** ★「適用中の絞り込み」ブロックの sticky 位置(2026-09-05)。
   *  モバイル全画面モーダル/一覧抽斗 = "top-0"、 PCサイドバーは共通ヘッダー(sticky)の下 = "top-14"。 */
  stickyTop?: string;
};

function toggle<T>(arr: T[], v: T): T[] {
  return arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v];
}

export default function FilterPanel({
  data,
  state,
  setState,
  authorEntries, matchedSlugs, loading, showSort = true, showArtBooks = true, stickyTop = "top-0" }: Props) {
  const update = (patch: Partial<FilterState>) => setState({ ...state, ...patch });

  // ★索引未到着 = 全facetが0になる(69,236件の索引は idle 遅延ロード)。
  //   「絞り込んで0件」と見分けが付かない廃墟になるので、ここで確定させて表示を分ける。
  const isLoading = loading ?? data.manga.length === 0;

  // ★件数だけ1フレーム遅らせる(2026-09-05)。チップの押下表示は state を直接見るので即座に、
  //   重い集計(69,236件×7パス=実測100ms、モバイルは3〜5倍)は低優先で追いつく。
  //   一覧側の絞り込み+ソートは22msなので、タップ後の待ちはほぼこの集計が作っていた。
  //   計算量は減らない=「先に色が変わる」ための並べ替え。
  const deferredState = useDeferredValue(state);
  const countsStale = deferredState !== state;

  // ★動的件数(2026-06-13): 各facetの値ごとに「その値を選んだら何件」を表示。
  //   faceted-search の定石 = 当該facetだけ解除した state で絞り、 残った作品を値で集計。
  //   静的(R2)のままブラウザJSで計算 = サーバ化しない([[hosting_worker_r2_architecture]])。
  const counts = useMemo(() => {
    // ★同じ解除条件の絞り込みは1回だけ走らせる(2026-08-01)。
    //   ジャンルと要素はどちらも解除なし(={})で、本番67k件に対する applyFilters を
    //   まったく同じ引数で2回やっていた。7パス→6パスに減る。
    // ★並べ替えなしの filterItems を使う(2026-09-05)。数えるだけなのに applyFilters を
    //   通すと末尾で必ず sortItems(既定=人気順) が走り、69,236件の配列コピー+ソートを
    //   1タップにつき6回払っていた(件数は順序に依らない=結果は完全に同じ)。
    const rowsCache = new Map<string, MangaListItem[]>();
    const rowsFor = (clear: Partial<FilterState>) => {
      const k = JSON.stringify(clear);
      let rows = rowsCache.get(k);
      if (!rows) {
        rows = filterItems(data.manga, { ...deferredState, ...clear }, matchedSlugs ?? null);
        rowsCache.set(k, rows);
      }
      return rows;
    };
    const tally = (clear: Partial<FilterState>, values: (m: MangaListItem) => string[]) => {
      const base = rowsFor(clear);
      const map = new Map<string, number>();
      for (const m of base) for (const v of values(m)) map.set(v, (map.get(v) ?? 0) + 1);
      return map;
    };
    return {
      status: tally({ statuses: [] }, (m) => [m.status]),
      demographic: tally({ demographics: [] }, (m) => (m.demographic ? [m.demographic] : [])),
      // ★ジャンル/要素はAND仕様(2026-07-22): 自facet解除をやめ「現在の絞り込み全体との交差数」を出す。
      //   旧(OR時代の定石=自facet解除)だと「お色気3」と見えて押すと0件になる不一致が起きる
      //   (3=少年∩お色気であって、選択中の冒険との交差ではないため)。ANDでは
      //   未選択チップの数字=「押したらこの件数になる」と完全一致する。
      genre: tally({}, (m) => m.genres ?? []),
      theme: tally({}, (m) => m.themes ?? []),
      publisher: tally({ publishers: [] }, (m) =>
        m.publishers?.length ? m.publishers : m.publisher ? [m.publisher] : [],
      ),
      magazine: tally({ magazines: [] }, (m) => (m.magazine ? [m.magazine] : [])),
      // ★巻数バケツ(2026-09-05): 基準は max_edition_volumes = カードの「全N巻」と同じ数
      volume: tally({ volumes: [] }, (m) => {
        const b = volumeBucket(m);
        return b ? [b] : [];
      }),
      // ★創刊ドリルダウン(Q3-A): 各作品から[年代,年,年-月]の3階層キーをemit
      launch: tally({ launch: null }, (m) => {
        const fvd = m.first_volume_date || (m.year_started ? String(m.year_started) : "");
        if (!fvd || fvd.length < 4) return [];
        const y = fvd.slice(0, 4);
        const keys = [`${Math.floor(Number(y) / 10) * 10}s`, y];
        if (fvd.length >= 7) keys.push(fvd.slice(0, 7));
        return keys;
      }),
      // 現在の絞り込み全体でのヒット数(=0件の説明に使う。rowsCache に相乗り)
      total: rowsFor({}).length,
    };
  }, [data.manga, deferredState, matchedSlugs]);
  // ★出版社/連載誌リストの並び(2026-08-10 ユーザ要望): 絞り込み中は 0件の行を隠し、
  //   現在の交差件数の多い順に並べ替える(件数は counts で再計算済み=それを並びにも使う)。
  //   選択中の行は 0件でも先頭に残す(=外せなくなるのを防ぐ)。
  //   ★読み込み中は 0件落としをしない(2026-09-05): 索引が届く前に全行を消すと
  //   「出版社が1社も無い」という嘘の廃墟になる(件数バッジも出さない)。
  const facetList = <T extends { key: string; name: string }>(
    items: T[],
    cnt: Map<string, number>,
    selected: string[],
  ) =>
    items
      .map((it) => ({ ...it, n: cnt.get(it.key) ?? 0, on: selected.includes(it.key) }))
      .filter((it) => isLoading || it.on || it.n > 0)
      .sort((a, b) => Number(b.on) - Number(a.on) || b.n - a.n || a.name.localeCompare(b.name, "ja"));
  const publisherList = useMemo(
    () => facetList(data.publishers, counts.publisher, state.publishers),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [data.publishers, counts.publisher, state.publishers, isLoading],
  );
  const magazineList = useMemo(
    () => facetList(data.magazines, counts.magazine, state.magazines),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [data.magazines, counts.magazine, state.magazines, isLoading],
  );
  // 要素タグの一覧 = 出現する全タグを件数降順(同数は名前順)で。 master が無いのでデータから導出。
  const themeList = useMemo(
    () =>
      [...counts.theme.entries()]
        .filter(([, n]) => n > 0)
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "ja")),
    [counts.theme],
  );
  // ★画集の件数(2026-09-05): 旧 data.artBooks.length は定数161だった。画集モードは漫画用の
  //   絞り込みを受けないが、検索語と年は applyArtBookFilters が効かせるので、検索中は
  //   「161」と出ているのに押すと数件、という不一致になっていた。161件なので毎回数えても無料。
  const artBookCount = useMemo(
    () => applyArtBookFilters(data.artBooks, state).length,
    [data.artBooks, state],
  );
  // 件数バッジ(0は淡色)。 ★読み込み中は数字を出さない(全部0=嘘になるため)
  const Cnt = ({ n }: { n: number }) =>
    isLoading ? null : (
      <span className={`ml-1 tabular-nums text-[10px] ${n ? "text-ink/60" : "text-ink/30"}`}>
        {n.toLocaleString()}
      </span>
    );

  const STATUS_LABELS: Record<StatusT, string> = {
    completed: "完結",
    ongoing: "連載中",
    hiatus: "休載",
  };
  const SORT_OPTIONS: { key: SortKey; label: string }[] = [
    { key: "default", label: "標準" },
    { key: "year-desc", label: "年代 (新しい順)" },
    { key: "year-asc", label: "年代 (古い順)" },
    { key: "title", label: "タイトル (五十音順)" },
    { key: "volumes", label: "巻数 (多い順)" },
  ];

  // ★適用中チップ(2026-08-10 ユーザ裁定・案A): カテゴリカードとフィルターが同じ状態を見る
  //   「2つの窓」であることを可視化。個別×で解除できる。
  //   ★2026-09-05: 要素/出版社/連載誌/画集/検索語/並び順 が入っておらず、
  //   「出版社で0件にしたのに画面に痕跡が無く解除もできない」穴になっていたので全条件を列挙する。
  const DEMO_JA: Record<string, string> = { shounen: "少年", shoujo: "少女", seinen: "青年", josei: "女性", kodomo: "児童" };
  const active: { id: string; label: string; clear: Partial<FilterState> }[] = [];
  if (state.query.trim()) active.push({ id: "q", label: `「${state.query.trim()}」`, clear: { query: "" } });
  if (state.anime) active.push({ id: "anime", label: "アニメ化", clear: { anime: false } });
  if (state.hasAwards) active.push({ id: "awards", label: "受賞", clear: { hasAwards: false } });
  for (const st of state.statuses) active.push({ id: `st:${st}`, label: STATUS_LABELS[st] ?? st, clear: { statuses: state.statuses.filter((x) => x !== st) } });
  for (const v of state.volumes) active.push({ id: `vo:${v}`, label: VOLUME_BUCKETS.find((b) => b.key === v)?.label ?? v, clear: { volumes: state.volumes.filter((x) => x !== v) } });
  for (const d of state.demographics) active.push({ id: `de:${d}`, label: DEMO_JA[d] ?? d, clear: { demographics: state.demographics.filter((x) => x !== d) } });
  for (const g of state.genres) active.push({ id: `ge:${g}`, label: data.genres.find((x) => x.key === g)?.name ?? g, clear: { genres: state.genres.filter((x) => x !== g) } });
  for (const t of state.themes) active.push({ id: `th:${t}`, label: t, clear: { themes: state.themes.filter((x) => x !== t) } });
  if (state.launch) active.push({ id: "launch", label: String(state.launch).replace("s", "年代"), clear: { launch: null } });
  for (const p of state.publishers) active.push({ id: `pu:${p}`, label: p === "(unknown)" ? "出版社未設定" : data.publishers.find((x) => x.key === p)?.name ?? p, clear: { publishers: state.publishers.filter((x) => x !== p) } });
  for (const mg of state.magazines) active.push({ id: `ma:${mg}`, label: data.magazines.find((x) => x.key === mg)?.name ?? mg, clear: { magazines: state.magazines.filter((x) => x !== mg) } });
  for (const a of state.authors) active.push({ id: `au:${a}`, label: a, clear: { authors: state.authors.filter((x) => x !== a) } });
  if (showArtBooks && state.artBooks) active.push({ id: "art", label: "🎨 画集", clear: { artBooks: false } });
  if (showSort && state.sort !== "default") active.push({ id: "sort", label: `並び: ${SORT_OPTIONS.find((o) => o.key === state.sort)?.label ?? state.sort}`, clear: { sort: "default" } });

  // ★アコーディオン(2026-09-05): 上位4つ(種類/連載状態/分野/ジャンル)は開いたまま、
  //   下の重い5つ(創刊/要素/出版社/連載誌/著者)だけ開閉。選択が入っている節は自動で開く
  //   (=閉じた節の中に条件が隠れない)。 明示的に開閉したらその値が勝つ。
  const [openMap, setOpenMap] = useState<Record<string, boolean>>({});
  const isOpen = (key: string, hasSel: boolean) => openMap[key] ?? hasSel;
  const toggleSection = (key: string, hasSel: boolean) =>
    setOpenMap((m) => ({ ...m, [key]: !(m[key] ?? hasSel) }));

  return (
    <aside className="space-y-6 text-sm">
      {active.length > 0 && (
        <div className={`sticky ${stickyTop} z-10 -mx-1 rounded-xl border border-[var(--color-accent)]/40 bg-[var(--color-surface)] p-2.5 shadow-[0_4px_10px_rgba(0,0,0,0.28)]`}>
          <div className="flex items-baseline justify-between gap-2">
            <div className="text-[11px] font-bold text-ink/70">適用中の絞り込み</div>
            {/* ★0件になった時にリセットが最下部で遠い問題(2026-09-05): ここでも解除できる。
                挙動は最下部の「条件をリセット」と同一(検索語は残す=検索語チップの×で消す) */}
            <button
              type="button"
              onClick={() => setState({ ...emptyFilterState(), query: state.query })}
              className="shrink-0 rounded-full border border-[var(--color-line)] px-2 py-0.5 text-[10px] font-semibold text-ink/70"
            >
              条件をリセット
            </button>
          </div>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {active.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => update(c.clear)}
                className="inline-flex items-center gap-1 rounded-full border border-[var(--color-accent)] bg-[var(--color-surface)] px-2.5 py-0.5 text-[12px] font-semibold text-[var(--color-accent)]"
              >
                {c.label}
                <span aria-hidden="true">×</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ★読み込み中/0件の区別(2026-09-05): 全facetが0の廃墟には3つの原因があるのに
          UIが区別していなかった(①索引未到着 ②検索0ヒット ③ANDの絞りすぎ)。 */}
      {isLoading ? (
        <p className="flex items-center gap-2 rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)]/60 px-3 py-2.5 text-[12px] text-ink/70">
          <span className="animate-pulse" aria-hidden="true">⏳</span>
          作品データを読み込み中… 件数は届き次第出ます
        </p>
      ) : counts.total === 0 && !countsStale ? (
        <div className="rounded-xl border border-[var(--color-accent)]/50 bg-[var(--color-surface)] px-3 py-2.5 text-[12px]">
          {matchedSlugs && matchedSlugs.size === 0 ? (
            <>
              <p className="text-ink/75">「{state.query.trim()}」に一致する作品がありません。</p>
              <button
                type="button"
                onClick={() => update({ query: "" })}
                className="mt-2 rounded-full border border-[var(--color-accent)] px-3 py-1 text-[11px] font-bold text-[var(--color-accent)]"
              >
                検索語を消す
              </button>
            </>
          ) : (
            <>
              <p className="text-ink/75">この条件に当てはまる作品はありません(条件の絞りすぎ)。</p>
              <button
                type="button"
                onClick={() => setState({ ...emptyFilterState(), query: state.query })}
                className="mt-2 rounded-full border border-[var(--color-accent)] px-3 py-1 text-[11px] font-bold text-[var(--color-accent)]"
              >
                条件をリセット
              </button>
            </>
          )}
        </div>
      ) : null}

      <Section title="種類">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={state.anime}
            onChange={() => update({ anime: !state.anime })}
          />
          <span>アニメ化作品のみ</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer mt-1">
          <input
            type="checkbox"
            checked={state.hasAwards}
            onChange={() => update({ hasAwards: !state.hasAwards })}
          />
          <span>受賞作品のみ</span>
        </label>
      </Section>

      <Section title="連載状態">
        <div className="flex flex-wrap gap-1.5">
          {(Object.keys(STATUS_LABELS) as StatusT[]).map((s) => (
            <ChipButton
              key={s}
              active={state.statuses.includes(s)}
              onClick={() =>
                update({ statuses: toggle(state.statuses, s) as StatusT[] })
              }
            >
              {STATUS_LABELS[s]}<Cnt n={counts.status.get(s) ?? 0} />
            </ChipButton>
          ))}
        </div>
      </Section>

      {/* ★巻数(2026-09-05 ユーザ裁定): 基準は max_edition_volumes = 一番巻数の多い版1本
          (= カードの「全N巻」と同じ数)。total_volumes(全版合算)では文庫版/完全版が足されて
          SLAM DUNK が75巻になる。区切りは 1のみ/2-5/6-10/11-15/16-20/21+ (単巻が38%あるので
          「1巻のみ」を独立させている)。選択は OR。 */}
      <Section title="巻数">
        <div className="flex flex-wrap gap-1.5">
          {VOLUME_BUCKETS.map((b) => (
            <ChipButton
              key={b.key}
              active={state.volumes.includes(b.key)}
              onClick={() => update({ volumes: toggle(state.volumes, b.key) })}
            >
              {b.label}<Cnt n={counts.volume.get(b.key) ?? 0} />
            </ChipButton>
          ))}
        </div>
      </Section>

      <Section title="分野">
        <div className="flex flex-wrap gap-1.5">
          {data.demographics.map((d) => (
            <ChipButton
              key={d.key}
              active={state.demographics.includes(d.key)}
              onClick={() => update({ demographics: toggle(state.demographics, d.key) })}
            >
              {d.name}<Cnt n={counts.demographic.get(d.key) ?? 0} />
            </ChipButton>
          ))}
        </div>
      </Section>

      {/* ★AND固定(2026-07-22 ユーザ裁定: ORは不要=絞り込み用途に交差のみ)。トグル撤去 */}
      <Section title="ジャンル">
        <div className="flex flex-wrap gap-1.5">
          {data.genres.map((g) => (
            <ChipButton
              key={g.key}
              active={state.genres.includes(g.key)}
              onClick={() => update({ genres: toggle(state.genres, g.key) })}
              className={!state.genres.includes(g.key) && !isLoading && (counts.genre.get(g.key) ?? 0) === 0 ? "opacity-40" : ""}
            >
              {g.name}<Cnt n={counts.genre.get(g.key) ?? 0} />
            </ChipButton>
          ))}
          {/* ★画集 = ジャンルでなく別カテゴリだが、 ここで選ぶと一覧を全画集に切替。
              ★/list では出さない(showArtBooks=false): あちらは漫画専用の表で切替を受けない。 */}
          {showArtBooks && (
            <ChipButton
              active={state.artBooks}
              onClick={() => update({ artBooks: !state.artBooks })}
            >
              🎨 画集（{artBookCount.toLocaleString()}）
            </ChipButton>
          )}
        </div>
      </Section>

      <Section
        title="創刊(1巻発売)"
        collapsible
        open={isOpen("launch", !!state.launch)}
        onToggle={() => toggleSection("launch", !!state.launch)}
        badge={state.launch ? 1 : 0}
      >
        {/* ★年代→年→月ドリルダウン(2026-07-07 Q3-A裁定)。件数付きチップ・タップで展開 */}
        <div className="space-y-1.5">
          <div className="flex flex-wrap gap-1.5">
            {Array.from({ length: 11 }, (_, i) => `${1920 + i * 10}s`)
              .filter((dec) => isLoading || (counts.launch.get(dec) ?? 0) > 0)
              .map((dec) => {
                const on = state.launch === dec || (state.launch ?? "").startsWith(dec.slice(0, 3));
                return (
                  <button
                    key={dec}
                    type="button"
                    onClick={() => update({ launch: state.launch === dec ? null : dec })}
                    className={`rounded-full border px-2 py-0.5 text-[11px] ${on ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)] font-bold" : "border-[var(--color-line)] text-ink/70"}`}
                  >
                    {dec.slice(0, 4)}年代<Cnt n={counts.launch.get(dec) ?? 0} />
                  </button>
                );
              })}
          </div>
          {state.launch && (
            <div className="flex flex-wrap gap-1.5 rounded-lg bg-[var(--color-surface-2)]/50 p-1.5">
              {(() => {
                const dec = Number((state.launch.endsWith("s") ? state.launch : state.launch).slice(0, 3) + "0");
                return Array.from({ length: 10 }, (_, i) => String(dec + i))
                  .filter((y) => (counts.launch.get(y) ?? 0) > 0)
                  .map((y) => {
                    const on = state.launch === y || (state.launch ?? "").startsWith(y);
                    return (
                      <button
                        key={y}
                        type="button"
                        onClick={() => update({ launch: state.launch === y ? `${dec}s` : y })}
                        className={`rounded-full border px-2 py-0.5 text-[11px] ${on && !state.launch!.endsWith("s") ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)] font-bold" : "border-[var(--color-line)] text-ink/60"}`}
                      >
                        {y}<Cnt n={counts.launch.get(y) ?? 0} />
                      </button>
                    );
                  });
              })()}
            </div>
          )}
          {state.launch && !state.launch.endsWith("s") && (
            <div className="flex flex-wrap gap-1.5 rounded-lg bg-[var(--color-surface-2)]/30 p-1.5">
              {(() => {
                const y = state.launch.slice(0, 4);
                return Array.from({ length: 12 }, (_, i) => `${y}-${String(i + 1).padStart(2, "0")}`)
                  .filter((ym) => (counts.launch.get(ym) ?? 0) > 0)
                  .map((ym) => (
                    <button
                      key={ym}
                      type="button"
                      onClick={() => update({ launch: state.launch === ym ? y : ym })}
                      className={`rounded-full border px-2 py-0.5 text-[11px] ${state.launch === ym ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)] font-bold" : "border-[var(--color-line)] text-ink/60"}`}
                    >
                      {Number(ym.slice(5, 7))}月<Cnt n={counts.launch.get(ym) ?? 0} />
                    </button>
                  ));
              })()}
            </div>
          )}
        </div>
      </Section>

      {themeList.length > 0 && (
        <Section
          title="要素"
          collapsible
          open={isOpen("themes", state.themes.length > 0)}
          onToggle={() => toggleSection("themes", state.themes.length > 0)}
          badge={state.themes.length}
          total={themeList.length}
        >
          {/* ★内部スクロール(旧 max-h-60)は廃止(2026-09-05): 全画面モーダルのスクロールと
              競合し「親が動くか子が動くか指で分からない」= 縦の長さより悪い。展開=全高。 */}
          <div className="flex flex-wrap gap-1.5">
            {themeList.map(([name, n]) => (
              <ChipButton
                key={name}
                active={state.themes.includes(name)}
                onClick={() => update({ themes: toggle(state.themes, name) })}
              >
                {name}<Cnt n={n} />
              </ChipButton>
            ))}
          </div>
        </Section>
      )}

      <Section
        title="出版社"
        collapsible
        open={isOpen("publishers", state.publishers.length > 0)}
        onToggle={() => toggleSection("publishers", state.publishers.length > 0)}
        badge={state.publishers.length}
        total={publisherList.length}
      >
        {/* ★内部スクロール(旧 max-h-48)は廃止(2026-09-05。上の「要素」と同じ理由) */}
        <div className="space-y-1">
          {/* ★出版社未設定(=要補完)を絞り込む QAボタン。 (unknown)キーで applyFilters の
              フォールバック(publishers空→[publisher])に乗る */}
          {(state.publishers.includes("(unknown)") || (counts.publisher.get("(unknown)") ?? 0) > 0) && (
            <label className="flex items-center gap-2 cursor-pointer rounded bg-amber-50 px-1 -mx-1">
              <input
                type="checkbox"
                checked={state.publishers.includes("(unknown)")}
                onChange={() => update({ publishers: toggle(state.publishers, "(unknown)") })}
              />
              <span className="text-amber-700">⚠ 出版社未設定</span>
              <Cnt n={counts.publisher.get("(unknown)") ?? 0} />
            </label>
          )}
          {publisherList.map((p) => (
            <label key={p.key} className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={p.on}
                onChange={() => update({ publishers: toggle(state.publishers, p.key) })}
              />
              <span>{p.name}</span><Cnt n={p.n} />
            </label>
          ))}
        </div>
      </Section>

      <Section
        title="連載誌"
        collapsible
        open={isOpen("magazines", state.magazines.length > 0)}
        onToggle={() => toggleSection("magazines", state.magazines.length > 0)}
        badge={state.magazines.length}
        total={magazineList.length}
      >
        {/* ★内部スクロール(旧 max-h-48)は廃止(2026-09-05。上の「要素」と同じ理由) */}
        <div className="space-y-1">
          {magazineList.map((m) => (
            <label key={m.key} className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={m.on}
                onChange={() => update({ magazines: toggle(state.magazines, m.key) })}
              />
              <span>{m.name}</span><Cnt n={m.n} />
            </label>
          ))}
        </div>
      </Section>

      <Section
        title="著者(五十音)"
        collapsible
        open={isOpen("authors", state.authors.length > 0)}
        onToggle={() => toggleSection("authors", state.authors.length > 0)}
        badge={state.authors.length}
      >
        <AuthorKanaIndex
          authors={authorEntries}
          selected={state.authors}
          onToggle={(name) => update({ authors: toggle(state.authors, name) })}
        />
      </Section>

      {/* ★並び順は絞り込みではないので最下部へ(2026-09-05): 旧は3番目に居て、
          ジャンルに着くまで5セクション分スクロールさせていた。
          ★/list では出さない(showSort=false): あちらは上部チップが本物で、ここは効かない。 */}
      {showSort && (
      <Section title="並び順">
        <select
          value={state.sort}
          onChange={(e) => update({ sort: e.target.value as SortKey })}
          className="w-full rounded-card border border-[var(--color-line)] px-2.5 py-1.5 transition focus:outline-none focus:border-[var(--color-accent)]"
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.key} value={o.key}>
              {o.label}
            </option>
          ))}
        </select>
      </Section>
      )}

      <button
        type="button"
        onClick={() => setState({ ...emptyFilterState(), query: state.query })}
        className="w-full text-xs px-3 py-2 rounded-card tactile-chip"
      >
        条件をリセット
      </button>
    </aside>
  );
}

function Section({
  title,
  right,
  children,
  collapsible = false,
  open = true,
  onToggle,
  badge = 0,
  total,
}: {
  title: string;
  right?: React.ReactNode;
  children: React.ReactNode;
  /** 折りたたみ可能(下の重いセクション)。 false = 常時展開(上位4つ) */
  collapsible?: boolean;
  open?: boolean;
  onToggle?: () => void;
  /** 選択中の件数(見出しに出す = 閉じていても条件が入っていることが分かる) */
  badge?: number;
  /** 選択肢の総数(閉じている時のヒント = 何が入っているか分かる) */
  total?: number;
}) {
  // ★見出しは text-ink(テーマ変数)で(2026-09-05): 旧 text-black/60 はベタ書きで
  //   ダークテーマ(theme-d3=黒地)に黒文字となり、見出しが全部沈んでいた。
  const heading = (
    <h3 className="font-semibold text-xs tracking-wider uppercase text-ink/70">{title}</h3>
  );
  if (!collapsible) {
    return (
      <section>
        <header className="flex items-center justify-between mb-2">
          {heading}
          {right}
        </header>
        {children}
      </section>
    );
  }
  return (
    <section>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="mb-2 flex w-full items-center gap-2 rounded-card border border-[var(--color-line)] bg-[var(--color-surface)]/50 px-2.5 py-2 text-left"
      >
        <span className="text-[10px] text-ink/60" aria-hidden="true">{open ? "▼" : "▶"}</span>
        {heading}
        {badge > 0 && (
          <span className="rounded-full bg-[var(--color-accent)] px-1.5 text-[10px] font-bold text-[var(--color-on-accent)]">
            {badge}
          </span>
        )}
        {badge === 0 && total !== undefined && (
          <span className="tabular-nums text-[10px] text-ink/45">{total.toLocaleString()}</span>
        )}
      </button>
      {open && children}
    </section>
  );
}

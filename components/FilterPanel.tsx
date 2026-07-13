"use client";

import { useMemo } from "react";
import { applyFilters, emptyFilterState, type FilterState, type SortKey } from "@/lib/filters";
import type { ListBundle, MangaListItem, StatusT } from "@/lib/schema";
import { ChipButton } from "@/components/ui/Chip";
import AuthorKanaIndex from "@/components/AuthorKanaIndex";

type Props = {
  data: ListBundle;
  state: FilterState;
  setState: (next: FilterState) => void;
  yearBounds: [number, number];
  authorEntries: { name: string; kana: string }[];
};

function toggle<T>(arr: T[], v: T): T[] {
  return arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v];
}

export default function FilterPanel({
  data,
  state,
  setState,
  yearBounds,
  authorEntries,
}: Props) {
  const update = (patch: Partial<FilterState>) => setState({ ...state, ...patch });

  // ★動的件数(2026-06-13): 各facetの値ごとに「その値を選んだら何件」を表示。
  //   faceted-search の定石 = 当該facetだけ解除した state で絞り、 残った作品を値で集計。
  //   静的(R2)のままブラウザJSで計算 = サーバ化しない([[hosting_worker_r2_architecture]])。
  const counts = useMemo(() => {
    const tally = (clear: Partial<FilterState>, values: (m: MangaListItem) => string[]) => {
      const base = applyFilters(data.manga, { ...state, ...clear });
      const map = new Map<string, number>();
      for (const m of base) for (const v of values(m)) map.set(v, (map.get(v) ?? 0) + 1);
      return map;
    };
    return {
      status: tally({ statuses: [] }, (m) => [m.status]),
      demographic: tally({ demographics: [] }, (m) => (m.demographic ? [m.demographic] : [])),
      genre: tally({ genres: [] }, (m) => m.genres ?? []),
      theme: tally({ themes: [] }, (m) => m.themes ?? []),
      publisher: tally({ publishers: [] }, (m) =>
        m.publishers?.length ? m.publishers : m.publisher ? [m.publisher] : [],
      ),
      magazine: tally({ magazines: [] }, (m) => (m.magazine ? [m.magazine] : [])),
      // ★創刊ドリルダウン(Q3-A): 各作品から[年代,年,年-月]の3階層キーをemit
      launch: tally({ launch: null }, (m) => {
        const fvd = m.first_volume_date || (m.year_started ? String(m.year_started) : "");
        if (!fvd || fvd.length < 4) return [];
        const y = fvd.slice(0, 4);
        const keys = [`${Math.floor(Number(y) / 10) * 10}s`, y];
        if (fvd.length >= 7) keys.push(fvd.slice(0, 7));
        return keys;
      }),
    };
  }, [data.manga, state]);
  // 要素タグの一覧 = 出現する全タグを件数降順(同数は名前順)で。 master が無いのでデータから導出。
  const themeList = useMemo(
    () =>
      [...counts.theme.entries()]
        .filter(([, n]) => n > 0)
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "ja")),
    [counts.theme],
  );
  // 件数バッジ(0は淡色)
  const Cnt = ({ n }: { n: number }) => (
    <span className={`ml-1 tabular-nums text-[10px] ${n ? "text-ink/40" : "text-ink/20"}`}>
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

  return (
    <aside className="space-y-6 text-sm">
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

      <Section title="創刊(1巻発売)">
        {/* ★年代→年→月ドリルダウン(2026-07-07 Q3-A裁定)。件数付きチップ・タップで展開 */}
        <div className="space-y-1.5">
          <div className="flex flex-wrap gap-1.5">
            {Array.from({ length: 11 }, (_, i) => `${1920 + i * 10}s`)
              .filter((dec) => (counts.launch.get(dec) ?? 0) > 0)
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

      <Section
        title="ジャンル"
        right={
          <button
            type="button"
            className="text-xs text-ink/50 hover:text-ink"
            onClick={() =>
              update({ genreMode: state.genreMode === "and" ? "or" : "and" })
            }
            title="AND/OR を切り替え"
          >
            条件: {state.genreMode.toUpperCase()}
          </button>
        }
      >
        <div className="flex flex-wrap gap-1.5">
          {data.genres.map((g) => (
            <ChipButton
              key={g.key}
              active={state.genres.includes(g.key)}
              onClick={() => update({ genres: toggle(state.genres, g.key) })}
            >
              {g.name}<Cnt n={counts.genre.get(g.key) ?? 0} />
            </ChipButton>
          ))}
          {/* ★画集 = ジャンルでなく別カテゴリだが、 ここで選ぶと一覧を全画集に切替 */}
          <ChipButton
            active={state.artBooks}
            onClick={() => update({ artBooks: !state.artBooks })}
          >
            🎨 画集（{data.artBooks.length}）
          </ChipButton>
        </div>
      </Section>

      {themeList.length > 0 && (
        <Section
          title="要素"
          right={
            <button
              type="button"
              className="text-xs text-ink/50 hover:text-ink"
              onClick={() =>
                update({ themeMode: state.themeMode === "and" ? "or" : "and" })
              }
              title="AND/OR を切り替え"
            >
              条件: {state.themeMode.toUpperCase()}
            </button>
          }
        >
          <div className="flex flex-wrap gap-1.5 max-h-60 overflow-y-auto">
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

      <Section title="出版社">
        {/* ★連載誌と同じ縦圧縮(2026-07-06 ユーザ要望): 長リストはスクロール */}
        <div className="space-y-1 max-h-48 overflow-y-auto">
          {/* ★出版社未設定(=要補完)を絞り込む QAボタン。 (unknown)キーで applyFilters の
              フォールバック(publishers空→[publisher])に乗る */}
          <label className="flex items-center gap-2 cursor-pointer rounded bg-amber-50 px-1 -mx-1">
            <input
              type="checkbox"
              checked={state.publishers.includes("(unknown)")}
              onChange={() => update({ publishers: toggle(state.publishers, "(unknown)") })}
            />
            <span className="text-amber-700">⚠ 出版社未設定</span>
            <Cnt n={counts.publisher.get("(unknown)") ?? 0} />
          </label>
          {data.publishers.map((p) => (
            <label key={p.key} className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={state.publishers.includes(p.key)}
                onChange={() => update({ publishers: toggle(state.publishers, p.key) })}
              />
              <span>{p.name}</span><Cnt n={counts.publisher.get(p.key) ?? 0} />
            </label>
          ))}
        </div>
      </Section>

      <Section title="連載誌">
        <div className="space-y-1 max-h-48 overflow-y-auto">
          {data.magazines.map((m) => (
            <label key={m.key} className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={state.magazines.includes(m.key)}
                onChange={() => update({ magazines: toggle(state.magazines, m.key) })}
              />
              <span>{m.name}</span><Cnt n={counts.magazine.get(m.key) ?? 0} />
            </label>
          ))}
        </div>
      </Section>

      <Section title="著者(五十音)">
        <AuthorKanaIndex
          authors={authorEntries}
          selected={state.authors}
          onToggle={(name) => update({ authors: toggle(state.authors, name) })}
        />
      </Section>

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
}: {
  title: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section>
      <header className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-xs tracking-wider uppercase text-black/60">
          {title}
        </h3>
        {right}
      </header>
      {children}
    </section>
  );
}


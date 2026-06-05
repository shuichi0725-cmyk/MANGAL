"use client";

import { emptyFilterState, type FilterState, type SortKey } from "@/lib/filters";
import type { DataBundle, StatusT } from "@/lib/schema";
import { ChipButton } from "@/components/ui/Chip";

type Props = {
  data: DataBundle;
  state: FilterState;
  setState: (next: FilterState) => void;
  yearBounds: [number, number];
  authorOptions: string[];
};

function toggle<T>(arr: T[], v: T): T[] {
  return arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v];
}

export default function FilterPanel({
  data,
  state,
  setState,
  yearBounds,
  authorOptions,
}: Props) {
  const update = (patch: Partial<FilterState>) => setState({ ...state, ...patch });

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
              {STATUS_LABELS[s]}
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

      <Section title="出版年">
        <div className="flex items-center gap-2">
          <input
            type="number"
            inputMode="numeric"
            min={yearBounds[0]}
            max={yearBounds[1]}
            value={state.yearMin ?? ""}
            placeholder={String(yearBounds[0])}
            onChange={(e) =>
              update({ yearMin: e.target.value ? Number(e.target.value) : null })
            }
            className="w-20 rounded-card border border-[var(--color-line)] px-2 py-1 transition focus:outline-none focus:border-[var(--color-accent)]"
          />
          <span className="text-ink/50">〜</span>
          <input
            type="number"
            inputMode="numeric"
            min={yearBounds[0]}
            max={yearBounds[1]}
            value={state.yearMax ?? ""}
            placeholder={String(yearBounds[1])}
            onChange={(e) =>
              update({ yearMax: e.target.value ? Number(e.target.value) : null })
            }
            className="w-20 rounded-card border border-[var(--color-line)] px-2 py-1 transition focus:outline-none focus:border-[var(--color-accent)]"
          />
        </div>
        <input
          type="range"
          min={yearBounds[0]}
          max={yearBounds[1]}
          value={state.yearMin ?? yearBounds[0]}
          onChange={(e) => update({ yearMin: Number(e.target.value) })}
          className="w-full mt-2"
        />
        <input
          type="range"
          min={yearBounds[0]}
          max={yearBounds[1]}
          value={state.yearMax ?? yearBounds[1]}
          onChange={(e) => update({ yearMax: Number(e.target.value) })}
          className="w-full"
        />
      </Section>

      <Section title="分野">
        <div className="flex flex-wrap gap-1.5">
          {data.demographics.map((d) => (
            <ChipButton
              key={d.key}
              active={state.demographics.includes(d.key)}
              onClick={() => update({ demographics: toggle(state.demographics, d.key) })}
            >
              {d.name}
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
              {g.name}
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

      <Section title="出版社">
        <div className="space-y-1">
          {data.publishers.map((p) => (
            <label key={p.key} className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={state.publishers.includes(p.key)}
                onChange={() => update({ publishers: toggle(state.publishers, p.key) })}
              />
              <span>{p.name}</span>
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
              <span>{m.name}</span>
            </label>
          ))}
        </div>
      </Section>

      <Section title="著者">
        <select
          multiple
          value={state.authors}
          onChange={(e) =>
            update({
              authors: Array.from(e.target.selectedOptions, (o) => o.value),
            })
          }
          className="w-full rounded-card border border-[var(--color-line)] px-2.5 py-1.5 h-32 transition focus:outline-none focus:border-[var(--color-accent)]"
        >
          {authorOptions.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <p className="text-[11px] text-ink/45 mt-1">Ctrl/⌘ クリックで複数選択</p>
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


"use client";

import { useSearchParams } from "next/navigation";
import Card from "@/components/ui/Card";
import type { ListBundle, MangaListItem } from "@/lib/schema";

type Props = { data: ListBundle; filtered?: MangaListItem[] };

type Category = {
  params: Record<string, string>;
  label: string;
  count: number;
  icon: string;
};

/**
 * ホーム top の カテゴリエントリ grid。 mobile 2 列 / desktop 4-6 列で scale。
 * カウント 0 のカテゴリは非表示 (= データ無いのに見せても無意味)。
 *
 * ★2026-07-12 改修(ユーザ要望):
 *  - 人気順を左上へ(既定ソート=人気順の状態表示+解除を兼ねる)
 *  - 件数は「現在の絞り込み後」の交差件数(filtered を貰って再計算。無ければ全体)
 *  - タップ=現在のURLパラメータへマージ(置き換えない)。選択中タイルの再タップ=そのパラメータだけ解除
 */
export default function CategoryHub({ data, filtered }: Props) {
  const searchParams = useSearchParams();
  const base = filtered ?? data.manga;
  const total = base.length;

  const isActive = (params: Record<string, string>) => {
    for (const [k, v] of Object.entries(params)) {
      if (searchParams.get(k) !== v) return false;
    }
    return true;
  };
  const hrefFor = (params: Record<string, string>, active: boolean) => {
    const p = new URLSearchParams(searchParams.toString());
    for (const [k, v] of Object.entries(params)) {
      if (active) p.delete(k);
      else p.set(k, v);
    }
    p.delete("page");
    const qs = p.toString();
    return qs ? `/browse?${qs}` : "/browse";
  };

  const count = (pred: (m: MangaListItem) => boolean) => base.filter(pred).length;

  const P = (o: Record<string, string>) => o;
  const categories: Category[] = [
    // 並び順(全件対象なので count = 現在の表示件数)
    { params: P({ sort: "popularity" }), label: "人気順", count: total, icon: "🔥" },
    // フィルタ系(交差件数)
    { params: P({ anime: "true" }), label: "アニメ化作品", count: count((m) => !!m.anime_adapted), icon: "🎞️" },
    { params: P({ hasAwards: "true" }), label: "受賞作品", count: count((m) => !!(m.awards && m.awards.length > 0)), icon: "🏆" },
    { params: P({ status: "completed" }), label: "完結作品", count: count((m) => m.status === "completed"), icon: "✅" },
    { params: P({ status: "ongoing" }), label: "連載中", count: count((m) => m.status === "ongoing"), icon: "📖" },
    { params: P({ demographic: "shounen" }), label: "少年", count: count((m) => m.demographic === "shounen"), icon: "👦" },
    { params: P({ demographic: "seinen" }), label: "青年", count: count((m) => m.demographic === "seinen"), icon: "👨" },
    { params: P({ demographic: "shoujo" }), label: "少女", count: count((m) => m.demographic === "shoujo"), icon: "👧" },
    { params: P({ demographic: "josei" }), label: "女性", count: count((m) => m.demographic === "josei"), icon: "👩" },
    { params: P({ sort: "year-desc" }), label: "新しい順", count: total, icon: "🆕" },
    { params: P({ sort: "year-asc" }), label: "古い順", count: total, icon: "📜" },
    { params: P({ sort: "volumes" }), label: "巻数順", count: total, icon: "📚" },
    { params: P({ sort: "title" }), label: "五十音順", count: total, icon: "🅰️" },
  ].filter((c) => c.count > 0);

  if (categories.length === 0) return null;

  return (
    <section className="mb-7">
      <h2 className="text-[11px] font-semibold tracking-[0.18em] uppercase text-ink/50 mb-3">
        カテゴリで探す
      </h2>
      <ul className="grid grid-cols-4 sm:grid-cols-5 lg:grid-cols-6 gap-2">
        {categories.map((c) => {
          const active = isActive(c.params);
          return (
            <li key={c.label}>
              <Card
                href={hrefFor(c.params, active)}
                className={`h-full px-1 py-2.5 text-center ${
                  active ? "!bg-[var(--color-accent)] !text-white ring-2 ring-[var(--color-accent)]" : ""
                }`}
              >
                <span className="flex flex-col items-center justify-center gap-1">
                  <span className="text-base leading-none" aria-hidden="true">
                    {c.icon}
                  </span>
                  <span className="text-[11px] font-semibold leading-tight">
                    {active ? "✓ " : ""}{c.label}
                  </span>
                  <span className={`text-[10px] font-medium leading-none tabular-nums ${active ? "text-white/75" : "text-ink/40"}`}>
                    {c.count.toLocaleString()}
                  </span>
                </span>
              </Card>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

"use client";

import { useSearchParams } from "next/navigation";
import Card from "@/components/ui/Card";
import type { IndexSummary, ListBundle, MangaListItem } from "@/lib/schema";

type Props = { data: ListBundle; filtered?: MangaListItem[]; summary?: IndexSummary | null };

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
export default function CategoryHub({ data, filtered, summary }: Props) {
  const searchParams = useSearchParams();
  const base = filtered ?? data.manga;
  // ★summary が来ている間(=フル索引未到着かつ絞り込み無し)は、head 100件だけを
  //   数えた嘘の件数でなく、ビルド時に全件を集計した値を使う。2026-08-01
  const S = summary ?? null;
  const total = S ? S.total : base.length;

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

  const count = (pred: (m: MangaListItem) => boolean, fromSummary?: (s: IndexSummary) => number) =>
    S && fromSummary ? fromSummary(S) : base.filter(pred).length;

  const P = (o: Record<string, string>) => o;
  // ★8枚構成(2026-08-10 ユーザ裁定・案A): ソート系カードは撤去=フィルターの並び順に一本化。
  //   受賞もフィルターへ委譲。1行目=アニメ化/完結/連載中/児童(右上)、2行目=分野4はそのまま。
  //   ※BrowseShell(SSRフォールバック側)と同一構成を維持すること。
  const categories: Category[] = [
    { params: P({ anime: "true" }), label: "アニメ化作品", count: count((m) => !!m.anime_adapted, (s) => s.anime), icon: "🎞️" },
    { params: P({ status: "completed" }), label: "完結作品", count: count((m) => m.status === "completed", (s) => s.completed), icon: "✅" },
    { params: P({ status: "ongoing" }), label: "連載中", count: count((m) => m.status === "ongoing", (s) => s.ongoing), icon: "📖" },
    { params: P({ demographic: "kodomo" }), label: "児童", count: count((m) => m.demographic === "kodomo", (s) => s.kodomo), icon: "🧒" },
    { params: P({ demographic: "shounen" }), label: "少年", count: count((m) => m.demographic === "shounen", (s) => s.shounen), icon: "👦" },
    { params: P({ demographic: "seinen" }), label: "青年", count: count((m) => m.demographic === "seinen", (s) => s.seinen), icon: "👨" },
    { params: P({ demographic: "shoujo" }), label: "少女", count: count((m) => m.demographic === "shoujo", (s) => s.shoujo), icon: "👧" },
    { params: P({ demographic: "josei" }), label: "女性", count: count((m) => m.demographic === "josei", (s) => s.josei), icon: "👩" },
  ].filter((c) => c.count > 0);

  if (categories.length === 0) return null;

  return (
    <section className="mb-7">
      <h2 className="text-[11px] font-semibold tracking-[0.18em] uppercase text-ink/50 mb-3">
        カテゴリで探す
      </h2>
      <ul className="grid grid-cols-4 gap-2">
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

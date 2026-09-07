"use client";

import { useSearchParams } from "next/navigation";
import Link from "next/link";
import CatPict, { catKeyOf } from "@/components/CatPict";
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
      {/* ★見出しもホームと同型(2026-09-07 ユーザ「ホームの感じで」) */}
      <div className="mb-2.5 flex items-baseline gap-2.5">
        <h2 className="dot-heading text-[18px] font-black">カテゴリ</h2>
        <span className="text-[9px] font-extrabold tracking-[0.26em] text-ink/45">BROWSE BY</span>
      </div>
      {/* ★ホームと同じ「太枠1本の帯」(2026-09-07)。lg は flex で等分 = 0件落としで
          枚数が可変でも隙間が空かない。モバイルは4列グリッドのまま。 */}
      <ul className="grid grid-cols-4 border-[3px] border-[var(--color-ink)] bg-[var(--color-surface)] lg:flex">
        {categories.map((c, i) => {
          const active = isActive(c.params);
          const last = i === categories.length - 1;
          const lastRowStart = Math.floor((categories.length - 1) / 4) * 4;
          const div = [
            i % 4 !== 3 && !last ? "border-r-2 border-[#333]" : "",
            i % 4 === 3 && !last ? "lg:border-r-2 lg:border-[#333]" : "",
            i < lastRowStart ? "border-b-2 border-[#333] lg:border-b-0" : "",
          ].filter(Boolean).join(" ");
          return (
            <li key={c.label} className="lg:min-w-0 lg:flex-1">
              <Link
                href={hrefFor(c.params, active)}
                className={`spring-press block h-full px-1 py-3 text-center lg:py-2 ${div} ${
                  active ? "bg-[var(--color-accent)] text-[var(--color-on-accent)]" : ""
                }`}
              >
                <span className="cat-emoji text-base leading-none" aria-hidden="true">
                  {c.icon}
                </span>
                {catKeyOf(c.label) && <CatPict k={catKeyOf(c.label)!} />}
                <div className="mt-1 text-[11px] font-black leading-tight">
                  {active ? "✓ " : ""}{c.label}
                </div>
                <div className={`cat-count mt-0.5 text-[9.5px] font-bold leading-none tabular-nums ${active ? "text-white/75" : "text-[var(--color-accent)]"}`}>
                  {c.count.toLocaleString()}
                </div>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

import Link from "next/link";
import { loadTitlesPages } from "@/lib/loadData";
import { DesignNav } from "@/lib/homeDesign";

/** 題名50音索引トップ(2026-08-31 SEO)。全作品への静的クロール導線ハブ。
 *  /authors(著者50音索引)と対の存在。頁割りは data/titles-pages.json(Python生成)が単一ソース。 */

export const metadata = {
  title: "題名索引(50音順)",
  description:
    "掲載中の全漫画作品を題名の50音順で一覧。あ行〜わ行・英数字の各ページから作品詳細(全巻一覧・発売日・ISBN)へ。",
  alternates: { canonical: "https://mangal-db.com/titles" },
};

export default function TitlesIndexPage() {
  const tp = loadTitlesPages();
  const total = tp.gyo.reduce((s, g) => s + g.count, 0);
  return (
    <div>
      <DesignNav />
      <div className="mx-auto max-w-4xl px-4 py-8">
        <nav className="text-[12px] text-ink/55">
          <Link href="/" className="hover:text-ink">ホーム</Link> › 題名索引
        </nav>
        <h1 className="mt-2 text-2xl font-extrabold">題名索引</h1>
        <p className="mt-1 text-[12.5px] text-ink/60">
          {total.toLocaleString()}作品を題名の50音順で掲載。各ページから作品詳細へ。
        </p>
        {tp.gyo.filter((g) => g.count > 0).map((g) => (
          <section key={g.key} className="mt-6">
            <h2 className="text-base font-extrabold">
              {g.label}
              <span className="ml-2 text-[11px] font-semibold text-ink/45">
                {g.count.toLocaleString()}作品
              </span>
            </h2>
            <nav className="mt-2 flex flex-wrap gap-1.5">
              {Array.from({ length: g.pages }, (_, i) => (
                <Link
                  key={i}
                  href={`/titles/${g.key}-${i + 1}`}
                  className="rounded border border-[var(--color-line)] bg-[var(--color-surface)] px-2.5 py-1 text-[13px] font-bold hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
                >
                  {i + 1}
                </Link>
              ))}
            </nav>
          </section>
        ))}
        {total === 0 && (
          <p className="mt-8 text-sm text-ink/50">データ準備中です。</p>
        )}
      </div>
    </div>
  );
}

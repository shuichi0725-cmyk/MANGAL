import Link from "next/link";
import { DesignNav } from "@/lib/homeDesign";
import { decadeOf, hubDefs, hubHref, type HubDef } from "@/lib/hubs";

/** 連載開始年別 索引(2026-09-04 SEO ハブ面の入口)。 年代ごとに年を並べ、各年の作品一覧へ。 */

const SITE = "https://mangal-db.com";

export const metadata = {
  title: "連載開始年別 漫画一覧（年代から探す）",
  description:
    "連載・刊行が始まった年ごとの漫画作品一覧。1960年代から最新年まで、年代・年を選んでその年に始まった作品を人気順に一覧できます。",
  alternates: { canonical: `${SITE}/year` },
};

export default function YearIndexPage() {
  const defs = hubDefs("year");
  const groups = new Map<number, HubDef[]>();
  for (const d of defs) {
    const dec = decadeOf(Number(d.key));
    let g = groups.get(dec);
    if (!g) groups.set(dec, (g = []));
    g.push(d);
  }
  const ordered = [...groups.entries()].sort((a, b) => b[0] - a[0]);
  const total = defs.reduce((s, d) => s + d.count, 0);
  return (
    <div>
      <DesignNav />
      <div className="mx-auto max-w-4xl px-4 py-8">
        <nav className="text-[12px] text-ink/55">
          <Link href="/" className="hover:text-ink">ホーム</Link> › 連載開始年別
        </nav>
        <h1 className="mt-2 text-2xl font-extrabold">連載開始年別 漫画一覧</h1>
        <p className="mt-1 text-[13px] text-ink/70">
          {defs.length}年分・{total.toLocaleString()}作品。 連載・刊行が始まった年ごとに人気順で掲載しています。
        </p>
        {ordered.map(([dec, list]) => (
          <section key={dec} className="mt-6">
            <h2 className="text-[15px] font-bold">{dec}年代</h2>
            <ul className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-3">
              {list.map((d) => (
                <li key={d.key} className="flex items-baseline justify-between border-b border-[var(--color-line)] py-1.5">
                  <Link href={hubHref("year", d.key)} className="text-[13.5px] font-semibold hover:text-[var(--color-accent)]">
                    {d.name}
                  </Link>
                  <span className="text-[11px] tabular-nums text-ink/45">{d.count.toLocaleString()}作</span>
                </li>
              ))}
            </ul>
          </section>
        ))}
        <p className="mt-8 text-[12px] text-ink/55">
          <Link href="/magazine" className="text-[var(--color-accent)] hover:underline">雑誌別</Link> ・{" "}
          <Link href="/publisher" className="text-[var(--color-accent)] hover:underline">出版社別</Link> ・{" "}
          <Link href="/shinkan" className="text-[var(--color-accent)] hover:underline">今月の新刊</Link> ・{" "}
          <Link href="/titles" className="text-[var(--color-accent)] hover:underline">題名索引</Link>
        </p>
      </div>
    </div>
  );
}

import Link from "next/link";
import { DesignNav } from "@/lib/homeDesign";
import { hubDefs, hubHref } from "@/lib/hubs";

/** 出版社別 索引(2026-09-04 SEO ハブ面の入口)。 作品数順に出版社を並べ、各社の作品一覧へ。 */

const SITE = "https://mangal-db.com";

export const metadata = {
  title: "出版社別 漫画一覧（出版社から探す）",
  description:
    "講談社・小学館・集英社・KADOKAWA・秋田書店など、出版社ごとの漫画作品一覧。各社が刊行した作品を人気順に掲載。",
  alternates: { canonical: `${SITE}/publisher` },
};

export default function PublisherIndexPage() {
  const defs = hubDefs("publisher");
  const mags = hubDefs("magazine");
  const total = defs.reduce((s, d) => s + d.count, 0);
  return (
    <div>
      <DesignNav />
      <div className="mx-auto max-w-4xl px-4 py-8">
        <nav className="text-[12px] text-ink/55">
          <Link href="/" className="hover:text-ink">ホーム</Link> › 出版社別
        </nav>
        <h1 className="mt-2 text-2xl font-extrabold">出版社別 漫画一覧</h1>
        <p className="mt-1 text-[13px] text-ink/70">
          {defs.length}社・{total.toLocaleString()}作品。 各社の作品を人気順に掲載しています（掲載は50作品以上の出版社）。
        </p>
        <ul className="mt-4">
          {defs.map((d) => {
            const m = mags.filter((x) => x.publisher === d.key);
            return (
              <li key={d.key} className="border-b border-[var(--color-line)] py-2">
                <div className="flex items-baseline justify-between">
                  <Link href={hubHref("publisher", d.key)} className="text-[14px] font-bold hover:text-[var(--color-accent)]">
                    {d.name}
                  </Link>
                  <span className="text-[11px] tabular-nums text-ink/45">{d.count.toLocaleString()}作</span>
                </div>
                {m.length > 0 && (
                  <p className="mt-0.5 text-[11.5px] text-ink/55">
                    {m.map((x, i) => (
                      <span key={x.key}>
                        {i > 0 && " / "}
                        <Link href={hubHref("magazine", x.key)} className="hover:text-ink">{x.name}</Link>
                      </span>
                    ))}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
        <p className="mt-8 text-[12px] text-ink/55">
          <Link href="/magazine" className="text-[var(--color-accent)] hover:underline">雑誌別</Link> ・{" "}
          <Link href="/year" className="text-[var(--color-accent)] hover:underline">連載開始年別</Link> ・{" "}
          <Link href="/titles" className="text-[var(--color-accent)] hover:underline">題名索引</Link> ・{" "}
          <Link href="/authors" className="text-[var(--color-accent)] hover:underline">著者一覧</Link>
        </p>
      </div>
    </div>
  );
}

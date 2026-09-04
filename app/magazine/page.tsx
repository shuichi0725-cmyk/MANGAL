import Link from "next/link";
import { DesignNav } from "@/lib/homeDesign";
import { hubDefs, hubHref, hubHrefIfExists, publisherName, type HubDef } from "@/lib/hubs";

/** 雑誌別 索引(2026-09-04 SEO ハブ面の入口)。 出版社ごとに雑誌を並べ、各雑誌の連載作品一覧へ。 */

const SITE = "https://mangal-db.com";

export const metadata = {
  title: "雑誌別 漫画一覧（連載誌から探す）",
  description:
    "週刊少年ジャンプ・週刊少年マガジン・りぼん・ビッグコミックなど、連載誌ごとの漫画作品一覧。各誌の連載作品を連載開始年順に掲載。",
  alternates: { canonical: `${SITE}/magazine` },
};

export default function MagazineIndexPage() {
  const defs = hubDefs("magazine");
  const groups = new Map<string, HubDef[]>();
  for (const d of defs) {
    const k = d.publisher ?? "";
    let g = groups.get(k);
    if (!g) groups.set(k, (g = []));
    g.push(d);
  }
  const ordered = [...groups.entries()].sort(
    (a, b) => b[1].reduce((s, d) => s + d.count, 0) - a[1].reduce((s, d) => s + d.count, 0),
  );
  const total = defs.reduce((s, d) => s + d.count, 0);
  return (
    <div>
      <DesignNav />
      <div className="mx-auto max-w-4xl px-4 py-8">
        <nav className="text-[12px] text-ink/55">
          <Link href="/" className="hover:text-ink">ホーム</Link> › 雑誌別
        </nav>
        <h1 className="mt-2 text-2xl font-extrabold">雑誌別 漫画一覧</h1>
        <p className="mt-1 text-[13px] text-ink/70">
          連載誌 {defs.length}誌・{total.toLocaleString()}作品。 各誌の連載作品を連載開始年順に掲載しています。
        </p>
        {ordered.map(([pubKey, list]) => {
          const pub = publisherName(pubKey);
          const pubHref = hubHrefIfExists("publisher", pubKey);
          return (
            <section key={pubKey || "_"} className="mt-6">
              <h2 className="text-[15px] font-bold">
                {pubHref ? (
                  <Link href={pubHref} className="hover:text-[var(--color-accent)]">{pub ?? pubKey}</Link>
                ) : (
                  pub ?? pubKey
                )}
              </h2>
              <ul className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
                {list.map((d) => (
                  <li key={d.key} className="flex items-baseline justify-between border-b border-[var(--color-line)] py-1.5">
                    <Link href={hubHref("magazine", d.key)} className="text-[13.5px] font-semibold hover:text-[var(--color-accent)]">
                      {d.name}
                    </Link>
                    <span className="text-[11px] tabular-nums text-ink/45">{d.count.toLocaleString()}作</span>
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
        <p className="mt-8 text-[12px] text-ink/55">
          <Link href="/publisher" className="text-[var(--color-accent)] hover:underline">出版社別</Link> ・{" "}
          <Link href="/year" className="text-[var(--color-accent)] hover:underline">連載開始年別</Link> ・{" "}
          <Link href="/titles" className="text-[var(--color-accent)] hover:underline">題名索引</Link> ・{" "}
          <Link href="/authors" className="text-[var(--color-accent)] hover:underline">著者一覧</Link>
        </p>
      </div>
    </div>
  );
}

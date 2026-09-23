import Link from "next/link";
import { authorsPages } from "@/lib/authors";

/** 著者50音索引トップ(2026-08-10 新設 → 2026-09-23 分割)。著者静的ページへのクロール導線+回遊ハブ。
 *  ★旧版は20,220人を1枚に並べて HTML 8.6MB(GSC の登録リクエストが失敗)。
 *  いまは行ごとの目次だけを置き、名前は /authors/<行>-<n>(1頁300人)へ。頁割り = lib/authorsIndex.ts。 */

export function generateMetadata() {
  const total = authorsPages().gyo.reduce((s, g) => s + g.count, 0);
  return {
    title: "著者一覧(50音順)",
    description:
      `掲載中の漫画家・原作者${total ? ` ${total.toLocaleString()}名` : ""}を50音順で一覧。` +
      "あ行〜わ行・英数字の各ページから、著者ごとの全作品(全巻一覧・発売日)へ。",
    alternates: { canonical: "https://mangal-db.com/authors" },
  };
}

export default function AuthorsIndexPage() {
  const ap = authorsPages();
  const total = ap.gyo.reduce((s, g) => s + g.count, 0);
  return (
    <div>
      <div className="mx-auto max-w-4xl px-4 py-8 lg:max-w-none">
        <nav className="text-[12px] text-ink/55">
          <Link href="/" className="hover:text-ink">ホーム</Link> › 著者一覧
        </nav>
        <h1 className="mt-2 text-2xl font-extrabold">著者一覧</h1>
        <p className="mt-1 text-[12.5px] text-ink/60">
          {total.toLocaleString()}名を50音順で掲載。名前から全作品の一覧へ。
          作品名から探すなら<Link href="/titles" className="text-[var(--color-accent)] hover:underline">題名索引</Link>へ。
        </p>
        {ap.gyo.filter((g) => g.count > 0).map((g) => (
          <section key={g.key} className="mt-6">
            <h2 className="text-base font-extrabold">
              {g.label}
              <span className="ml-2 text-[11px] font-semibold text-ink/45">{g.count.toLocaleString()}名</span>
            </h2>
            <nav className="mt-2 flex flex-wrap gap-1.5">
              {Array.from({ length: g.pages }, (_, i) => {
                const rows = ap.parts[`${g.key}-${i + 1}`] ?? [];
                const first = rows[0]?.name ?? "";
                const last = rows[rows.length - 1]?.name ?? "";
                return (
                  <Link
                    key={i}
                    href={`/authors/${g.key}-${i + 1}`}
                    className="rounded border border-[var(--color-line)] bg-[var(--color-surface)] px-2.5 py-1 text-[12.5px] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
                  >
                    <b>{i + 1}</b>
                    <span className="ml-1.5 text-[11px] text-ink/55">
                      {first.slice(0, 8)}〜{last.slice(0, 8)}
                    </span>
                  </Link>
                );
              })}
            </nav>
          </section>
        ))}
        {total === 0 && <p className="mt-8 text-sm text-ink/50">データ準備中です。</p>}
      </div>
    </div>
  );
}

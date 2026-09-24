import Link from "next/link";
import { loadListBundle } from "@/lib/loadData";
import { genreItems, pop, repTitle } from "@/lib/hubs";

/** ジャンル別 索引(2026-09-24 新設)。
 *  /magazine /publisher /year には目次頁があるのに /genre だけ 404 だった
 *  (ホームの「ジャンルから」は /browse 行きで、32のジャンル面へはホームから1本もリンクが無かった)。
 *  32ジャンル(data/genres.yml の master)を件数順に並べ、各ジャンル面(/genre/<key>)へ。
 *  件数・代表作はジャンル面と同じ集計(lib/hubs の genreItems=人気順)を使う=数字が食い違わない。 */

const SITE = "https://mangal-db.com";

export const metadata = {
  title: "ジャンル別 漫画一覧（ジャンルから探す）",
  description:
    "アクション・ファンタジー・恋愛・ラブコメ・ミステリー・スポーツなど、ジャンルごとの漫画作品一覧。各ジャンルの作品を人気順に掲載し、完結済み・年代別にも絞り込めます。",
  alternates: { canonical: `${SITE}/genre` },
};

export default function GenreIndexPage() {
  const data = loadListBundle();
  const rows = data.genres
    .map((g) => {
      const items = genreItems(g.key);
      return {
        key: g.key,
        name: g.name,
        count: items.length,
        completed: items.filter((m) => m.status === "completed").length,
        top: items.filter((m) => pop(m) > 0).slice(0, 2).map((m) => repTitle(m.title, 16)),
      };
    })
    .filter((r) => r.count > 0)
    .sort((a, b) => b.count - a.count);

  return (
    <div>
      <div className="mx-auto max-w-4xl px-4 py-8 lg:max-w-none">
        <nav className="text-[12px] text-ink/55">
          <Link href="/" className="hover:text-ink">ホーム</Link> › ジャンル別
        </nav>
        <h1 className="mt-2 text-2xl font-extrabold">ジャンル別 漫画一覧</h1>
        <p className="mt-1 text-[13px] text-ink/70">
          {rows.length}ジャンル。 1作品に複数のジャンルが付くことがあります。 各ジャンルの作品を人気順に掲載しています。
        </p>
        <ul className="mt-5 grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
          {rows.map((r) => (
            <li key={r.key} className="border-b border-[var(--color-line)] py-2">
              <div className="flex items-baseline justify-between gap-2">
                <Link href={`/genre/${r.key}`} className="text-[14px] font-semibold hover:text-[var(--color-accent)]">
                  {r.name}
                </Link>
                <span className="shrink-0 text-[11px] tabular-nums text-ink/45">
                  {r.count.toLocaleString()}作（完結 {r.completed.toLocaleString()}）
                </span>
              </div>
              {r.top.length > 0 && (
                <p className="mt-0.5 truncate text-[11px] text-ink/50">『{r.top.join("』『")}』など</p>
              )}
            </li>
          ))}
        </ul>
        <p className="mt-8 text-[12px] text-ink/55">
          <Link href="/magazine" className="text-[var(--color-accent)] hover:underline">雑誌別</Link> ・{" "}
          <Link href="/publisher" className="text-[var(--color-accent)] hover:underline">出版社別</Link> ・{" "}
          <Link href="/year" className="text-[var(--color-accent)] hover:underline">連載開始年別</Link> ・{" "}
          <Link href="/titles" className="text-[var(--color-accent)] hover:underline">題名索引</Link> ・{" "}
          <Link href="/authors" className="text-[var(--color-accent)] hover:underline">著者一覧</Link>
        </p>
      </div>
    </div>
  );
}

import Link from "next/link";
import { notFound } from "next/navigation";
import GenreGrid from "@/components/GenreGrid";
import { loadListBundle } from "@/lib/loadData";
import { DesignNav } from "@/lib/homeDesign";
import { genreSubItems, genreSubStaticParams, genreSubs, hasGenreSub, pop, subLabel } from "@/lib/hubs";

/** ジャンル下位面(2026-09-04 SEO): /genre/<key>/completed(完結済み) と /genre/<key>/<yyyy>s(年代)。
 *  「完結済み ファンタジー漫画」「1990年代 少女漫画」型の長尾の着地面。 閾値(GENRE_SUB_MIN)以上の組だけ生成。
 *  一覧は人気順の上位120(書影グリッド)。 全作品への静的リンクは年別ハブ(/year)が担う。 */

const SITE = "https://mangal-db.com";

export const dynamicParams = false;

export function generateStaticParams() {
  return genreSubStaticParams();
}

type P = { params: Promise<{ key: string; sub: string }> };

function resolve(key: string, sub: string) {
  const data = loadListBundle();
  const genre = data.genres.find((g) => g.key === key);
  const label = subLabel(sub);
  if (!genre || !label || !hasGenreSub(key, sub)) return null;
  const items = genreSubItems(key, sub) ?? [];
  return { data, genre, label, items };
}

function headingOf(label: string, genreName: string): string {
  const base = genreName.endsWith("漫画") ? genreName : `${genreName}漫画`;
  return `${label}の${base}`;
}

export async function generateMetadata({ params }: P) {
  const { key, sub } = await params;
  const r = resolve(key, sub);
  if (!r) return {};
  const n = r.items.length.toLocaleString();
  const top = r.items.filter((m) => pop(m) > 0).slice(0, 3).map((m) => m.title.slice(0, 20));
  const title = `${headingOf(r.label, r.genre.name)} おすすめ一覧（人気順・${n}作品）`;
  const what = sub === "completed" ? "完結済みの" : `${r.label}に始まった`;
  const description =
    `${what}${r.genre.name}ジャンルの漫画${n}作品を人気順に掲載。` +
    (top.length > 0 ? `『${top.join("』『")}』など。` : "") +
    "各作品の全巻一覧・発売日・ISBN・購入リンクつき。";
  const url = `${SITE}/genre/${key}/${sub}`;
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: { title, description, url, type: "website", siteName: "MANGAL" },
  };
}

export default async function GenreSubPage({ params }: P) {
  const { key, sub } = await params;
  const r = resolve(key, sub);
  if (!r) notFound();
  const { data, genre, label, items } = r!;
  const siblings = genreSubs(key).filter((s) => s.sub !== sub);
  // 同じ条件(完結済み/同年代)を持つ他ジャンル = 下位面同士の横リンク網
  const others = data.genres.filter((g) => g.key !== key && hasGenreSub(g.key, sub));
  const breadcrumbLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "ホーム", item: `${SITE}/` },
      { "@type": "ListItem", position: 2, name: genre.name, item: `${SITE}/genre/${key}` },
      { "@type": "ListItem", position: 3, name: label, item: `${SITE}/genre/${key}/${sub}` },
    ],
  };
  return (
    <>
      <DesignNav />
      <div className="min-h-screen bg-[var(--color-bg)] px-4 py-6 pb-16">
        <div className="mx-auto max-w-3xl">
          <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd) }} />
          <nav className="text-[12px] text-ink/55">
            <Link href="/" className="hover:text-ink">ホーム</Link> ›{" "}
            <Link href={`/genre/${key}`} className="hover:text-ink">「{genre.name}」の漫画</Link> › {label}
          </nav>
          <h1 className="mt-2 text-[22px] font-black">{headingOf(label, genre.name)}</h1>
          <p className="mt-1 text-[11px] text-ink/45">
            全 <b className="tabular-nums">{items.length.toLocaleString()}</b> 作品・人気順
          </p>
          {siblings.length > 0 && (
            <p className="mt-3 flex flex-wrap gap-1.5 text-[11.5px]">
              <Link href={`/genre/${key}`} className="rounded-full border border-[var(--color-line)] px-2.5 py-0.5 hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]">
                すべて
              </Link>
              {siblings.map((s) => (
                <Link
                  key={s.sub}
                  href={`/genre/${key}/${s.sub}`}
                  className="rounded-full border border-[var(--color-line)] px-2.5 py-0.5 hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
                >
                  {s.label}
                  <span className="ml-1 tabular-nums text-ink/45">{s.count.toLocaleString()}</span>
                </Link>
              ))}
            </p>
          )}
          <GenreGrid items={items} />
          {items.length > 120 && (
            <p className="mt-6 text-center text-[12px] text-ink/50">上位120作を表示中（全{items.length.toLocaleString()}作）。</p>
          )}
          {others.length > 0 && (
            <section className="mt-8">
              <h2 className="text-[13px] font-bold text-ink/75">{label}の他のジャンル</h2>
              <p className="mt-2 flex flex-wrap gap-1.5 text-[11.5px]">
                {others.map((g) => (
                  <Link
                    key={g.key}
                    href={`/genre/${g.key}/${sub}`}
                    className="rounded-full border border-[var(--color-line)] px-2.5 py-0.5 hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
                  >
                    {g.name}
                  </Link>
                ))}
              </p>
            </section>
          )}
        </div>
      </div>
    </>
  );
}

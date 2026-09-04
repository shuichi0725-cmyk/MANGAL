import Link from "next/link";
import { notFound } from "next/navigation";
import GenreGrid from "@/components/GenreGrid";
import { loadListBundle, loadGenreIntros } from "@/lib/loadData";
import { DesignNav } from "@/lib/homeDesign";
import { genreItems, genreMagazines, genreSubs, hubHref, pop } from "@/lib/hubs";

const SITE = "https://mangal-db.com";

/** ★SEO(2026-09-04): ジャンル面32頁が全て既定title「MANGAL — 日本の漫画データベース」で
 *  Googleに同一頁に見えていた穴を塞ぐ。 title/description を頁ごとに焼く(件数・完結数・代表作)。
 *  ★「| 漫画・コミックのMANGAL」は layout の template が付けるのでここでは書かない。 */
export async function generateMetadata({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const data = loadListBundle();
  const genre = data.genres.find((g) => g.key === key);
  if (!genre) return { alternates: { canonical: `${SITE}/genre/${key}` } };
  const items = genreItems(key);
  const n = items.length.toLocaleString();
  const completed = items.filter((m) => m.status === "completed").length.toLocaleString();
  const top = items.filter((m) => pop(m) > 0).slice(0, 3).map((m) => m.title.slice(0, 20));
  // 「4コマ漫画」「エッセイ漫画」は名前自体が「漫画」で終わる = 二重にしない
  const label = genre.name.endsWith("漫画") ? genre.name : `${genre.name}漫画`;
  const title = `${label} おすすめ一覧（人気順・${n}作品）`;
  const description =
    `${genre.name}ジャンルの漫画${n}作品を人気順に掲載（完結${completed}作）。` +
    (top.length > 0 ? `『${top.join("』『")}』など。` : "") +
    "各作品の全巻一覧・発売日・ISBN・購入リンクつき。";
  return {
    title,
    description,
    alternates: { canonical: `${SITE}/genre/${key}` },
    openGraph: { title, description, url: `${SITE}/genre/${key}`, type: "website", siteName: "MANGAL" },
  };
}

/** ジャンル別ランディング = 「自動生成まとめ記事」の土台(discovery + SEO + アフィの集約)。
 *  全作品をジャンルで絞り、 ★AniList人気順(コミュニティ不要)で並べる。
 *  AI解説スロット(intro)は将来 per-genre のキュレーション文を差し込む(今はデータ駆動の暫定)。
 *  [[genre_quality_improvement]] [[anilist_link_quality]] / 設計 manba参考(まとめ記事の網羅・データ駆動版)。
 *  ★2026-09-04 SEO: 下位面(完結済み/年代=/genre/<key>/<sub>)・掲載誌ハブ・他ジャンルへの横リンク・
 *    著者頁リンク(GenreGrid)を追加 = ジャンル面が「120作へのリンクだけ」の行き止まりだった穴を塞ぐ。 */
export function generateStaticParams() {
  const keys = loadListBundle().genres.map((g) => ({ key: g.key }));
  return keys.length > 0 ? keys : [{ key: "_empty" }];
}

const chip =
  "rounded-full border border-[var(--color-line)] px-2.5 py-0.5 hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]";

export default async function GenrePage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const data = loadListBundle();
  const genre = data.genres.find((g) => g.key === key);
  if (!genre) notFound();

  const items = genreItems(key);
  const completed = items.filter((m) => m.status === "completed").length;
  const top = items.filter((m) => pop(m) > 0).slice(0, 3);
  const intro = loadGenreIntros()[key]; // ★AIキュレーション文(無ければデータ駆動暫定)
  const subs = genreSubs(key);
  const mags = genreMagazines(key);
  const others = data.genres.filter((g) => g.key !== key);

  return (
    <>
      <DesignNav />
      <div className="min-h-screen bg-[var(--color-bg)] px-4 py-6 pb-16">
      <div className="mx-auto max-w-3xl">
        <Link href="/" className="spring-press text-[12px] text-[var(--color-accent)]">← ホーム</Link>
        <h1 className="mt-2 text-[22px] font-black">「{genre!.name}」の漫画</h1>
        {/* ★AIキュレーション文(genre-intros.yml)。 無ければデータ駆動の暫定文 */}
        {intro ? (
          <p className="mt-2 text-[13.5px] leading-relaxed text-ink/80">{intro}</p>
        ) : (
          <p className="mt-2 text-[13px] leading-relaxed text-ink/70">
            {genre!.name}ジャンルの漫画。人気順で並んでいます。
            {top.length > 0 && <>注目は『{top.map((m) => m.title).join("』『")}』など。</>}
          </p>
        )}
        <p className="mt-1 text-[11px] text-ink/45">
          全 <b className="tabular-nums">{items.length.toLocaleString()}</b> 作品（完結 {completed.toLocaleString()}）・人気順
        </p>

        {/* 下位面: 完結済み / 年代別(閾値以上の組だけ頁が在る) */}
        {subs.length > 0 && (
          <p className="mt-3 flex flex-wrap gap-1.5 text-[11.5px]">
            {subs.map((s) => (
              <Link key={s.sub} href={`/genre/${key}/${s.sub}`} className={chip}>
                {s.label}
                <span className="ml-1 tabular-nums text-ink/45">{s.count.toLocaleString()}</span>
              </Link>
            ))}
          </p>
        )}

        <GenreGrid items={items} />
        {items.length > 120 && (
          <p className="mt-6 text-center text-[12px] text-ink/50">
            上位120作を表示中（全{items.length.toLocaleString()}作）。
            <Link href={`/list?genre=${key}`} className="ml-1 text-[var(--color-accent)] underline">一覧表で全作品を見る →</Link>
          </p>
        )}

        {/* 掲載誌から探す = ジャンル面⇄雑誌ハブの横リンク */}
        {mags.length > 0 && (
          <section className="mt-8">
            <h2 className="text-[13px] font-bold text-ink/75">{genre!.name}漫画の主な連載誌</h2>
            <p className="mt-2 flex flex-wrap gap-1.5 text-[11.5px]">
              {mags.map(({ def, count }) => (
                <Link key={def.key} href={hubHref("magazine", def.key)} className={chip}>
                  {def.name}
                  <span className="ml-1 tabular-nums text-ink/45">{count.toLocaleString()}</span>
                </Link>
              ))}
            </p>
          </section>
        )}

        {/* 他のジャンル = 32面の相互リンク網 */}
        <section className="mt-8">
          <h2 className="text-[13px] font-bold text-ink/75">他のジャンルから探す</h2>
          <p className="mt-2 flex flex-wrap gap-1.5 text-[11.5px]">
            {others.map((g) => (
              <Link key={g.key} href={`/genre/${g.key}`} className={chip}>
                {g.name}
              </Link>
            ))}
          </p>
        </section>
      </div>
      </div>
    </>
  );
}

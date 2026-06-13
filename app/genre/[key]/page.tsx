import Link from "next/link";
import { notFound } from "next/navigation";
import CoverImage from "@/components/CoverImage";
import MarqueeTitle from "@/components/MarqueeTitle";
import { loadAllManga, loadGenreIntros } from "@/lib/loadData";
import { primaryVolume, type Manga } from "@/lib/schema";

/** ジャンル別ランディング = 「自動生成まとめ記事」の土台(discovery + SEO + アフィの集約)。
 *  全作品をジャンルで絞り、 ★AniList人気順(コミュニティ不要)で並べる。
 *  AI解説スロット(intro)は将来 per-genre のキュレーション文を差し込む(今はデータ駆動の暫定)。
 *  [[genre_quality_improvement]] [[anilist_link_quality]] / 設計 manba参考(まとめ記事の網羅・データ駆動版)。 */
export function generateStaticParams() {
  const keys = loadAllManga().genres.map((g) => ({ key: g.key }));
  return keys.length > 0 ? keys : [{ key: "_empty" }];
}

function pop(m: Manga) {
  return m.popularity ?? 0;
}

export default async function GenrePage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const data = loadAllManga();
  const genre = data.genres.find((g) => g.key === key);
  if (!genre) notFound();

  const items = data.manga
    .filter((m) => (m.genres || []).includes(key))
    .sort((a, b) => pop(b) - pop(a) || (b.score ?? 0) - (a.score ?? 0));
  const completed = items.filter((m) => m.status === "completed").length;
  const top = items.filter((m) => pop(m) > 0).slice(0, 3);
  const intro = loadGenreIntros()[key]; // ★AIキュレーション文(無ければデータ駆動暫定)

  return (
    <div className="min-h-screen bg-[var(--color-bg)] px-4 py-6 pb-16">
      <div className="mx-auto max-w-3xl">
        <Link href="/" className="spring-press text-[12px] text-[var(--color-accent)]">← ホーム</Link>
        <h1 className="mt-2 text-[22px] font-black">「{genre.name}」の漫画</h1>
        {/* ★AIキュレーション文(genre-intros.yml)。 無ければデータ駆動の暫定文 */}
        {intro ? (
          <p className="mt-2 text-[13.5px] leading-relaxed text-ink/80">{intro}</p>
        ) : (
          <p className="mt-2 text-[13px] leading-relaxed text-ink/70">
            {genre.name}ジャンルの漫画。人気順で並んでいます。
            {top.length > 0 && <>注目は『{top.map((m) => m.title).join("』『")}』など。</>}
          </p>
        )}
        <p className="mt-1 text-[11px] text-ink/45">
          全 <b className="tabular-nums">{items.length.toLocaleString()}</b> 作品（完結 {completed.toLocaleString()}）・人気順
        </p>

        <ul className="mt-5 grid grid-cols-3 gap-x-3 gap-y-5 sm:grid-cols-4">
          {items.slice(0, 120).map((m) => {
            const c = primaryVolume(m)?.cover_url ?? null;
            return (
              <li key={m.slug}>
                <Link href={`/manga/${m.slug}`} className="block group spring-press">
                  <div className="relative aspect-[2/3] w-full overflow-hidden rounded bg-[var(--color-surface-2)] border border-[var(--color-line)]">
                    {c ? (
                      <CoverImage src={c} alt={m.title} sizes="120px" size="card" />
                    ) : (
                      <div className="absolute inset-0 flex items-center justify-center p-2 text-center text-[11px] leading-tight text-ink/45">
                        {m.title.slice(0, 28)}
                      </div>
                    )}
                    {typeof m.score === "number" && m.score >= 70 && (
                      <span className="absolute right-1 top-1 rounded bg-ink/80 px-1 py-0.5 text-[9px] font-bold text-white tabular-nums">
                        ★{(m.score / 10).toFixed(1)}
                      </span>
                    )}
                  </div>
                  <MarqueeTitle text={m.title} className="mt-1 text-[12px] leading-snug text-ink/85 group-hover:text-[var(--color-accent)]" />
                  <p className="truncate text-[10px] text-ink/50">{m.authors.map((a) => a.name).join("・")}</p>
                </Link>
              </li>
            );
          })}
        </ul>
        {items.length > 120 && (
          <p className="mt-6 text-center text-[12px] text-ink/50">
            上位120作を表示中（全{items.length.toLocaleString()}作）。
            <Link href={`/list?genre=${key}`} className="ml-1 text-[var(--color-accent)] underline">一覧表で全作品を見る →</Link>
          </p>
        )}
      </div>
    </div>
  );
}

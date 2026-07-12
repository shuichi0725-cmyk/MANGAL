import Link from "next/link";
import { notFound } from "next/navigation";
import CoverImage from "@/components/CoverImage";
import MarqueeTitle from "@/components/MarqueeTitle";
import view from "@/data/anime-seasons-view.json";
import {
  adjacentSeasons,
  seasonLabel,
  sourceLabel,
  type AnimeSeasonsView,
} from "@/lib/animeSeason";

const V = view as unknown as AnimeSeasonsView;
const SITE = "https://mangal-db.com";

export function generateStaticParams() {
  return V.order.map((season) => ({ season }));
}

export async function generateMetadata({ params }: { params: Promise<{ season: string }> }) {
  const { season } = await params;
  if (!V.seasons[season]) return {};
  const label = seasonLabel(season);
  return {
    title: `${label}アニメの原作漫画一覧 - MANGAL`,
    description: `${label}放送アニメの原作漫画・コミカライズ ${V.seasons[season].length}作品。巻一覧・発売日つき。`,
    alternates: { canonical: `${SITE}/anime/${season}` },
  };
}

export default async function AnimeSeasonPage({ params }: { params: Promise<{ season: string }> }) {
  const { season } = await params;
  const entries = V.seasons[season];
  if (!entries) notFound();
  const { prev, next } = adjacentSeasons(V.order, season);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <Link href="/anime" className="text-sm text-ink/60 hover:text-ink">
        ← 季節一覧へ
      </Link>

      <h1 className="mt-4 text-2xl font-bold">📺 {seasonLabel(season)}アニメの原作漫画</h1>
      <p className="mt-1 text-xs text-ink/55">
        この季に放送・配信が始まったアニメの原作漫画/コミカライズ {entries.length} 作品(人気順)
      </p>

      {/* 季ナビ */}
      <div className="mt-4 flex items-center justify-between text-sm">
        {prev ? (
          <Link href={`/anime/${prev}`} className="text-[var(--color-accent)] font-semibold">
            ← {seasonLabel(prev)}
          </Link>
        ) : (
          <span />
        )}
        {next ? (
          <Link href={`/anime/${next}`} className="text-[var(--color-accent)] font-semibold">
            {seasonLabel(next)} →
          </Link>
        ) : (
          <span />
        )}
      </div>

      <ul className="mt-5 grid grid-cols-3 gap-x-3 gap-y-5 sm:grid-cols-4 md:grid-cols-5">
        {entries.map((e) => (
          <li key={e.slug}>
            <Link href={`/manga/${e.slug}`} className="block group spring-press">
              <div
                className="relative overflow-hidden rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)]"
                style={{ aspectRatio: "2 / 3" }}
              >
                {e.cover ? (
                  <CoverImage src={e.cover} alt={e.title} sizes="120px" />
                ) : (
                  <span className="flex h-full w-full items-center justify-center text-[10px] text-ink/40">
                    no image
                  </span>
                )}
                <span className="absolute left-1 top-1 rounded bg-black/60 px-1 py-0.5 text-[9px] font-semibold text-white">
                  {sourceLabel(e.source)}
                </span>
              </div>
              <MarqueeTitle
                text={e.title}
                className="mt-1 text-[12px] leading-snug text-ink/85 group-hover:text-[var(--color-accent)]"
              />
              {e.anime_title && e.anime_title !== e.title && (
                <p className="truncate text-[10px] text-ink/45">アニメ: {e.anime_title}</p>
              )}
            </Link>
          </li>
        ))}
      </ul>

      <div className="mt-8 flex items-center justify-between text-sm">
        {prev ? (
          <Link href={`/anime/${prev}`} className="text-[var(--color-accent)] font-semibold">
            ← {seasonLabel(prev)}
          </Link>
        ) : (
          <span />
        )}
        {next ? (
          <Link href={`/anime/${next}`} className="text-[var(--color-accent)] font-semibold">
            {seasonLabel(next)} →
          </Link>
        ) : (
          <span />
        )}
      </div>

      <p className="mt-8 text-[10px] leading-relaxed text-ink/40">
        放送季・原作情報は AniList のデータを基にしています。原作が漫画以外(小説・ゲーム等)の作品は、
        コミカライズ版の漫画ページへリンクしています。
      </p>
    </div>
  );
}

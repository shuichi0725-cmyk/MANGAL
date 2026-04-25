import Image from "next/image";
import Link from "next/link";
import { openBdCoverUrl } from "@/lib/amazon";
import type { DemographicLabel, Genre, Manga, Publisher } from "@/lib/schema";
import AffiliateLink from "./AffiliateLink";

type Props = {
  manga: Manga;
  publishers: Publisher[];
  genres: Genre[];
  demographics: DemographicLabel[];
};

export default function MangaCard({ manga, publishers, genres, demographics }: Props) {
  const cover =
    manga.volume_1?.cover_url ||
    openBdCoverUrl(manga.volume_1?.isbn13 ?? null);

  const publisherName =
    publishers.find((p) => p.key === manga.publisher)?.name ?? manga.publisher;
  const demographicName =
    demographics.find((d) => d.key === manga.demographic)?.name ?? manga.demographic;
  const genreNames = manga.genres.map(
    (g) => genres.find((x) => x.key === g)?.name ?? g,
  );

  const yearLabel = manga.year_ended
    ? `${manga.year_started}–${manga.year_ended}`
    : `${manga.year_started}–`;

  return (
    <article className="group rounded-lg border border-black/10 bg-white overflow-hidden flex flex-col hover:shadow-md transition-shadow">
      <Link href={`/manga/${manga.slug}`} className="block">
        <div className="relative aspect-[2/3] bg-black/5">
          {cover ? (
            <Image
              src={cover}
              alt={`${manga.title} 1巻 表紙`}
              fill
              sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 200px"
              className="object-cover"
            />
          ) : (
            <div className="absolute inset-0 grid place-items-center text-black/40 text-xs">
              表紙なし
            </div>
          )}
        </div>
      </Link>
      <div className="p-3 flex-1 flex flex-col gap-1.5">
        <Link href={`/manga/${manga.slug}`} className="font-bold leading-tight line-clamp-2 hover:text-[var(--color-accent)]">
          {manga.title}
        </Link>
        <p className="text-xs text-black/60 line-clamp-1">
          {manga.authors.map((a) => a.name).join(" / ")}
          {manga.original_authors.length
            ? `（原作: ${manga.original_authors.map((a) => a.name).join(" / ")}）`
            : ""}
        </p>
        <p className="text-xs text-black/50">
          {yearLabel}・{publisherName}・{demographicName}
        </p>
        <p className="text-xs text-black/60 line-clamp-1">
          {genreNames.slice(0, 4).join(" / ")}
        </p>
        <div className="mt-auto pt-2">
          <AffiliateLink
            manga={manga}
            className="inline-block text-xs px-3 py-1.5 rounded bg-[var(--color-accent)] text-white hover:opacity-90"
          >
            Amazonで見る
          </AffiliateLink>
        </div>
      </div>
    </article>
  );
}

import Link from "next/link";
import { openBdCoverUrl } from "@/lib/amazon";
import { formatReleaseDate, yearStatusLabel } from "@/lib/format";
import {
  allVolumes,
  primaryEdition,
  primaryVolume,
  type DemographicLabel,
  type Genre,
  type Manga,
  type Publisher,
} from "@/lib/schema";
import AffiliateLink from "./AffiliateLink";
import CoverImage from "./CoverImage";

type Props = {
  manga: Manga;
  publishers: Publisher[];
  genres: Genre[];
  demographics: DemographicLabel[];
};

export default function MangaCard({ manga, publishers, genres, demographics }: Props) {
  const v1 = primaryVolume(manga);
  const cover = v1?.cover_url || openBdCoverUrl(v1?.isbn13 ?? null);
  const cardVolumes = primaryEdition(manga).volumes;

  const publisherName =
    publishers.find((p) => p.key === manga.publisher)?.name ?? manga.publisher;
  const demographicName =
    demographics.find((d) => d.key === manga.demographic)?.name ?? manga.demographic;
  const genreNames = manga.genres.map(
    (g) => genres.find((x) => x.key === g)?.name ?? g,
  );

  const hasAnyDate = allVolumes(manga).some((v) => v.release_date);

  return (
    <article className="group rounded-lg border border-black/10 bg-white overflow-hidden flex flex-col hover:shadow-md transition-shadow">
      <Link href={`/manga/${manga.slug}`} className="block">
        <div className="relative aspect-[2/3] bg-black/5">
          <CoverImage
            src={cover}
            alt={`${manga.title} 1巻 表紙`}
            sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 200px"
          />
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
          {yearStatusLabel(manga)}・{publisherName}・{demographicName}
        </p>
        {hasAnyDate && (
          <ul className="text-[11px] text-black/55 max-h-24 overflow-y-auto pr-1 space-y-0.5">
            {cardVolumes.map((v) => (
              <li key={v.number} className="flex items-baseline justify-between gap-2">
                <span className="shrink-0">第{v.number}巻</span>
                <span className="text-black/45 truncate">
                  {formatReleaseDate(v.release_date) || "—"}
                </span>
              </li>
            ))}
          </ul>
        )}
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

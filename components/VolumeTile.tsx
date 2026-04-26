import { openBdCoverUrl } from "@/lib/amazon";
import { formatReleaseDate, volumeLabel } from "@/lib/format";
import type { Manga, Volume } from "@/lib/schema";
import AffiliateLink from "./AffiliateLink";
import CoverImage from "./CoverImage";

type Props = {
  manga: Manga;
  volume: Volume;
};

export default function VolumeTile({ manga, volume }: Props) {
  const cover = volume.cover_url || openBdCoverUrl(volume.isbn13 ?? null);
  const date = formatReleaseDate(volume.release_date);
  const label = volumeLabel(volume);

  return (
    <AffiliateLink
      manga={manga}
      volume={volume}
      ariaLabel={`${manga.title} ${label} を Amazon で見る`}
      className="block group"
    >
      <div className="relative aspect-[2/3] bg-black/5 rounded overflow-hidden">
        <CoverImage
          src={cover}
          alt={`${manga.title} ${label} 表紙`}
          sizes="110px"
        />
      </div>
      <p className="mt-1 text-xs font-medium leading-tight">{label}</p>
      <p className="text-[11px] text-black/50 leading-tight">
        {date || "発売日未取得"}
      </p>
    </AffiliateLink>
  );
}

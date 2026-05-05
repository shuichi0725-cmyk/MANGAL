import { formatReleaseDate, volumeLabel } from "@/lib/format";
import type { Edition, Manga, Volume } from "@/lib/schema";
import AffiliateLink from "./AffiliateLink";
import CoverImage from "./CoverImage";

type Props = {
  manga: Manga;
  volume: Volume;
  edition?: Edition;
};

export default function VolumeTile({ manga, volume, edition }: Props) {
  // 表紙は volume.cover_url のみ。openBD/NDL fallback は将来 risk なので不採用。
  const cover = volume.cover_url ?? null;
  const date = formatReleaseDate(volume.release_date);
  const label = volumeLabel(volume);
  const editionLabel = edition ? `${edition.label} ` : "";

  return (
    <AffiliateLink
      manga={manga}
      volume={volume}
      ariaLabel={`${manga.title} ${editionLabel}${label} を Amazon で見る`}
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

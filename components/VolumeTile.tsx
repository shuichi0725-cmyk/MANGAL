import { formatReleaseDate, volumeLabel } from "@/lib/format";
import type { Edition, Manga, Volume } from "@/lib/schema";
import AffiliateLink from "./AffiliateLink";
import CoverImage from "./CoverImage";

type Props = {
  manga: Manga;
  volume: Volume;
  edition?: Edition;
};

/**
 * 単一巻の表示。 cover / Amazon ボタン / 巻説明 はそれぞれ「データがあれば描画、
 * 無ければ skip」 の方針。 tile 全体を Amazon リンクで wrap していた旧構造は
 * 廃止し、 明示的なボタンに統一 (= 大半の巻で ASIN 未取得な現状で誤誘導しない)。
 */
export default function VolumeTile({ manga, volume, edition }: Props) {
  const cover = volume.cover_url ?? null;
  const date = formatReleaseDate(volume.release_date);
  const label = volumeLabel(volume);
  const editionLabel = edition ? `${edition.label} ` : "";

  return (
    <div className="block">
      {cover && (
        <div className="relative aspect-[2/3] bg-black/5 rounded overflow-hidden">
          <CoverImage
            src={cover}
            alt={`${manga.title} ${label} 表紙`}
            sizes="110px"
          />
        </div>
      )}
      <p className="mt-1 text-xs font-medium leading-tight">{label}</p>
      <p className="text-[11px] text-black/50 leading-tight">
        {date || "発売日未取得"}
      </p>
      {volume.asin && (
        <AffiliateLink
          manga={manga}
          volume={volume}
          ariaLabel={`${manga.title} ${editionLabel}${label} を Amazon で見る`}
          className="inline-block mt-1.5 text-[11px] px-2.5 py-1 rounded bg-[var(--color-accent)] text-white hover:opacity-90"
        >
          アマゾン
        </AffiliateLink>
      )}
      {volume.description && (
        <p className="mt-1.5 text-[11px] text-black/65 leading-relaxed">
          {volume.description}
        </p>
      )}
    </div>
  );
}

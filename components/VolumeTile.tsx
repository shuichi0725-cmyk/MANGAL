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
 * 単一巻を 1 行として表示する layout (横並び)。 cover は左に小さく、 残りの
 * メタ (巻ラベル / 発売日 / Amazon ボタン / 巻説明) を右に縦積み。
 *
 * cover / asin / description は **データがあれば描画、 無ければ skip** の方針。
 * tile 全体を Amazon リンクで wrap していた旧構造は廃止し、 明示的なボタン
 * のみで Amazon に遷移する。
 */
export default function VolumeTile({ manga, volume, edition }: Props) {
  const cover = volume.cover_url ?? null;
  const date = formatReleaseDate(volume.release_date);
  const label = volumeLabel(volume);
  const editionLabel = edition ? `${edition.label} ` : "";

  return (
    <div className="flex gap-3">
      {/* 書影スロット = 常に枠表示。 cover_url があれば実画像、 無ければプレースホルダ */}
      <div className="relative w-16 aspect-[2/3] bg-[var(--color-surface-2)] rounded-md overflow-hidden shrink-0">
        {cover ? (
          <CoverImage src={cover} alt={`${manga.title} ${label} 表紙`} sizes="64px" />
        ) : (
          <span className="flex h-full flex-col items-center justify-center gap-0.5 text-ink/25">
            <span className="text-base leading-none" aria-hidden="true">
              📖
            </span>
            <span className="text-[9px] font-medium leading-none">{label}</span>
          </span>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold leading-tight">{label}</p>
        <p className="text-xs text-ink/50 mt-0.5 leading-tight">
          {date || "発売日未取得"}
        </p>
        {volume.asin && (
          <AffiliateLink
            manga={manga}
            volume={volume}
            ariaLabel={`${manga.title} ${editionLabel}${label} を Amazon で見る`}
            className="inline-block mt-2 text-xs px-3 py-1.5 rounded-chip font-medium bg-[var(--color-accent)] text-white hover:opacity-90"
          >
            アマゾン
          </AffiliateLink>
        )}
        {volume.description && (
          <p className="mt-2 text-xs text-ink/70 leading-relaxed whitespace-pre-line">
            {volume.description}
          </p>
        )}
      </div>
    </div>
  );
}

import Card from "./ui/Card";
import { buildAmazonUrlForArtBook } from "@/lib/amazon";
import type { ArtBook } from "@/lib/schema";

type Props = { artBook: ArtBook };

/**
 * 画集カタログの 1 枚。 MangaCard と同型 (左 cover プレースホルダ + 右メタ)。
 * 漫画と区別するため cover プレースホルダは 🎨。 作品ページでなく Amazon へ誘導。
 */
export default function ArtBookCard({ artBook }: Props) {
  const tag = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG ?? "";
  const locale = process.env.NEXT_PUBLIC_AMAZON_LOCALE ?? "jp";
  const href = buildAmazonUrlForArtBook(artBook, { associateTag: tag, locale });
  const cover = artBook.volumes[0]?.cover_url ?? null;

  return (
    <Card className="flex gap-3 p-3">
      <div className="relative w-16 aspect-[2/3] rounded-md overflow-hidden shrink-0 bg-[var(--color-surface-2)]">
        {cover ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={cover} alt={`${artBook.title} 表紙`} className="h-full w-full object-cover" />
        ) : (
          <span className="flex h-full items-center justify-center text-xl text-ink/20" aria-hidden="true">
            🎨
          </span>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-bold text-base leading-tight">{artBook.title}</p>
        <p className="text-xs text-ink/65 mt-1.5 line-clamp-1">{artBook.artist}</p>
        {artBook.publisher && (
          <p className="text-xs text-ink/55 mt-0.5 line-clamp-1">{artBook.publisher}</p>
        )}
        {artBook.year && <p className="text-xs text-ink/45 mt-0.5">{artBook.year}年</p>}
        <a
          href={href}
          target="_blank"
          rel="nofollow sponsored noopener"
          className="inline-block mt-2 text-xs font-semibold text-[var(--color-accent)]"
        >
          Amazonで見る →
        </a>
      </div>
    </Card>
  );
}

import Card from "./ui/Card";
import Badge from "./ui/Badge";
import type { ArtBook } from "@/lib/schema";

type Props = { artBook: ArtBook };

/**
 * 画集カタログの 1 枚。 MangaCard と同型 (左 cover プレースホルダ + 右メタ)。
 * ★漫画と同じく「カード → 作品ページ(/art-books/[slug])」へ遷移する (Amazon直リンクでない)。
 * 漫画と区別するため cover プレースホルダは 🎨 / カテゴリ Badge「画集」。
 */
export default function ArtBookCard({ artBook }: Props) {
  const cover = artBook.volumes[0]?.cover_url ?? null;

  return (
    <Card href={`/art-books/${artBook.slug}`} className="flex gap-3 p-3">
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
        <div className="flex items-start gap-2">
          <p className="font-bold text-base leading-tight flex-1 min-w-0">{artBook.title}</p>
          <Badge tone="accent" className="shrink-0 mt-0.5">
            画集
          </Badge>
        </div>
        <p className="text-xs text-ink/65 mt-1.5 line-clamp-1">{artBook.artist}</p>
        {artBook.publisher && (
          <p className="text-xs text-ink/55 mt-0.5 line-clamp-1">{artBook.publisher}</p>
        )}
        {artBook.year && <p className="text-xs text-ink/45 mt-0.5">{artBook.year}年</p>}
      </div>
    </Card>
  );
}

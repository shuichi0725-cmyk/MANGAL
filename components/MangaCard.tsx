import Link from "next/link";
import { yearStatusLabel } from "@/lib/format";
import {
  primaryVolume,
  type DemographicLabel,
  type Genre,
  type Manga,
  type Publisher,
} from "@/lib/schema";
import CoverImage from "./CoverImage";

type Props = {
  manga: Manga;
  publishers: Publisher[];
  genres: Genre[];
  demographics: DemographicLabel[];
};

/**
 * 一覧ページの 1 行 (= 1 作品)。 horizontal flex で左に cover (将来用)、
 * 右に 4 行のメタ (タイトル・著者・出版社・年代) を縦 stack。
 *
 * 現状 cover_url は全部 null なので左のサムネイルは描画されず、 右の 4 行
 * のみが表示される (= 全行同じ高さ)。 将来 PA-API 等で cover_url が入った
 * 時、 左に 64px 幅のサムネイルが自動で出る。
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export default function MangaCard({ manga, publishers, genres, demographics }: Props) {
  const v1 = primaryVolume(manga);
  const cover = v1?.cover_url ?? null;

  const publisherName =
    publishers.find((p) => p.key === manga.publisher)?.name ?? manga.publisher;

  const authorLine =
    manga.authors.map((a) => a.name).join(" / ") +
    (manga.original_authors.length
      ? `（原作: ${manga.original_authors.map((a) => a.name).join(" / ")}）`
      : "");

  return (
    <Link
      href={`/manga/${manga.slug}`}
      className="flex gap-3 px-4 py-3 hover:bg-black/[0.02] transition-colors"
    >
      {cover && (
        <div className="relative w-16 aspect-[2/3] bg-black/5 rounded overflow-hidden shrink-0">
          <CoverImage src={cover} alt={`${manga.title} 1巻 表紙`} sizes="64px" />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <p className="font-bold text-base leading-tight">{manga.title}</p>
        {manga.subtitle && (
          <p className="text-xs text-black/55 mt-0.5 line-clamp-1">{manga.subtitle}</p>
        )}
        <p className="text-xs text-black/65 mt-1.5 line-clamp-1">{authorLine}</p>
        <p className="text-xs text-black/55 mt-0.5 line-clamp-1">{publisherName}</p>
        <p className="text-xs text-black/45 mt-0.5">{yearStatusLabel(manga)}</p>
      </div>
    </Link>
  );
}

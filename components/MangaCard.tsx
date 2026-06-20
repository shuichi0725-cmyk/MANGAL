import { yearStatusLabel } from "@/lib/format";
import {
  type DemographicLabel,
  type Genre,
  type MangaListItem,
  type Publisher,
} from "@/lib/schema";
import Card from "./ui/Card";
import Badge from "./ui/Badge";
import CoverImage from "./CoverImage";

const STATUS_TONE: Record<string, "neutral" | "accent" | "warm"> = {
  ongoing: "warm",
  completed: "neutral",
  hiatus: "neutral",
};
const STATUS_LABEL: Record<string, string> = {
  ongoing: "連載中",
  completed: "完結",
  hiatus: "休載",
};

type Props = {
  manga: MangaListItem;
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
  const cover = manga.cover;

  const publisherName =
    publishers.find((p) => p.key === manga.publisher)?.name ?? manga.publisher;

  const authorLine =
    manga.authors.map((a) => a.name).join(" / ") +
    (manga.original_authors.length
      ? `（原作: ${manga.original_authors.map((a) => a.name).join(" / ")}）`
      : "");

  return (
    <Card href={`/manga/${manga.slug}`} className="flex gap-3 p-3">
      <div className="relative w-16 aspect-[2/3] rounded-md overflow-hidden shrink-0 bg-[var(--color-surface-2)]">
        {cover ? (
          <CoverImage src={cover} alt={`${manga.title} 1巻 表紙`} sizes="64px" />
        ) : (
          <span className="flex h-full items-center justify-center text-xl text-ink/20" aria-hidden="true">
            📖
          </span>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start gap-2">
          <p className="font-bold text-base leading-tight flex-1 min-w-0">{manga.title}</p>
          <Badge tone={STATUS_TONE[manga.status] ?? "neutral"} className="shrink-0 mt-0.5">
            {STATUS_LABEL[manga.status] ?? manga.status}
          </Badge>
        </div>
        {manga.subtitle && (
          <p className="text-xs text-ink/55 mt-0.5 line-clamp-1">{manga.subtitle}</p>
        )}
        <p className="text-xs text-ink/65 mt-1 line-clamp-1">
          {authorLine}
          <span className="text-ink/45">　{yearStatusLabel(manga)}</span>
        </p>
        {manga.catch ? (
          <p className="text-xs text-ink/75 font-medium leading-snug mt-1 line-clamp-3 border-l-2 border-[var(--color-accent)] bg-[color-mix(in_srgb,var(--color-accent)_8%,transparent)] rounded-r-md px-2 py-1">
            {manga.catch}
          </p>
        ) : (
          <p className="text-xs text-ink/55 mt-0.5 line-clamp-1">{publisherName}</p>
        )}
      </div>
    </Card>
  );
}

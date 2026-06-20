import type { DemographicLabel, Genre, MangaListItem, Publisher } from "@/lib/schema";
import MangaCard from "./MangaCard";

type Props = {
  items: MangaListItem[];
  publishers: Publisher[];
  genres: Genre[];
  demographics: DemographicLabel[];
};

export default function MangaGrid({ items, publishers, genres, demographics }: Props) {
  if (items.length === 0) {
    return (
      <div className="tactile rounded-card py-16 text-center">
        <p className="text-2xl" aria-hidden="true">📭</p>
        <p className="mt-2 text-sm text-ink/55">条件に一致する作品がありません。</p>
        <p className="mt-1 text-xs text-ink/40">検索語や絞り込みを変えてみてください。</p>
      </div>
    );
  }
  return (
    <ul className="space-y-2">
      {items.map((m) => (
        <li key={m.slug}>
          <MangaCard
            manga={m}
            publishers={publishers}
            genres={genres}
            demographics={demographics}
          />
        </li>
      ))}
    </ul>
  );
}

import type { DemographicLabel, Genre, Manga, Publisher } from "@/lib/schema";
import MangaCard from "./MangaCard";

type Props = {
  items: Manga[];
  publishers: Publisher[];
  genres: Genre[];
  demographics: DemographicLabel[];
};

export default function MangaGrid({ items, publishers, genres, demographics }: Props) {
  if (items.length === 0) {
    return (
      <div className="py-20 text-center text-black/50">
        条件に一致する作品がありません。
      </div>
    );
  }
  return (
    <ul className="divide-y divide-black/10 border-y border-black/10">
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

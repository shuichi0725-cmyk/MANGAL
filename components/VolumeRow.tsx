import type { Manga } from "@/lib/schema";
import VolumeTile from "./VolumeTile";

type Props = { manga: Manga };

export default function VolumeRow({ manga }: Props) {
  if (manga.volumes.length === 0) return null;

  return (
    <section className="mt-8">
      <h2 className="text-sm font-semibold text-black/70 mb-3">
        全 {manga.volumes.length} 巻
      </h2>
      <ul className="grid grid-cols-4 gap-3">
        {manga.volumes.map((v) => (
          <li key={v.number}>
            <VolumeTile manga={manga} volume={v} />
          </li>
        ))}
      </ul>
    </section>
  );
}

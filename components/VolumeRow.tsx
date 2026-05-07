import type { Manga } from "@/lib/schema";
import VolumeTile from "./VolumeTile";

type Props = { manga: Manga };

export default function VolumeRow({ manga }: Props) {
  if (manga.editions.length === 0) return null;

  return (
    <div className="mt-8 space-y-8">
      {manga.editions.map((ed) => (
        <section key={`${ed.type}-${ed.label}`}>
          <h2 className="text-sm font-semibold text-black/70 mb-3">
            {ed.label}
            <span className="ml-2 text-black/40 font-normal">
              全 {ed.volumes.length} 巻
            </span>
          </h2>
          <ul className="space-y-4">
            {ed.volumes.map((v) => (
              <li
                key={`${ed.type}-${v.number}`}
                className="border-b border-black/5 pb-4 last:border-b-0"
              >
                <VolumeTile manga={manga} volume={v} edition={ed} />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

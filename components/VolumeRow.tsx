import type { Manga } from "@/lib/schema";
import VolumeTile from "./VolumeTile";
import Card from "./ui/Card";
import Badge from "./ui/Badge";

type Props = { manga: Manga };

export default function VolumeRow({ manga }: Props) {
  if (manga.editions.length === 0) return null;

  return (
    <div className="mt-8">
      {manga.editions.map((ed, idx) => (
        <section
          key={`${ed.type}-${ed.label}`}
          // 2つ目以降の版は中程度の区切り線で明確に分ける(太すぎず細すぎず)
          className={idx > 0 ? "mt-8 border-t-2 border-ink/15 pt-8" : ""}
        >
          <h2 className="mb-3 flex items-center gap-2">
            <span className="text-base font-bold">{ed.label}</span>
            <Badge>全 {ed.volumes.length} 巻</Badge>
          </h2>
          <ul className="space-y-2">
            {ed.volumes.map((v) => (
              <li key={`${ed.type}-${v.number}`}>
                <Card className="p-3">
                  <VolumeTile manga={manga} volume={v} edition={ed} />
                </Card>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

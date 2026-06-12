import type { Manga } from "@/lib/schema";
import EditionVolumes from "./EditionVolumes";

type Props = { manga: Manga };

export default function VolumeRow({ manga }: Props) {
  if (manga.editions.length === 0) return null;

  return (
    <div className="mt-8">
      {manga.editions.map((ed, idx) => (
        <section
          key={`${ed.type}-${ed.label}`}
          // ★2つ目以降の版は畳み表示(見出しバーのみ・タップで展開 = うる星型でも縦に伸びない)
          className={idx > 0 ? "mt-3" : ""}
        >
          {/* 版本体 (= 複数刷がある場合は EditionVolumes 内で古い順タブ切替) */}
          <EditionVolumes manga={manga} edition={ed} defaultCollapsed={idx > 0} />
        </section>
      ))}
    </div>
  );
}

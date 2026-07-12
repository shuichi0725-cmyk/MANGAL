import type { Edition, Manga } from "@/lib/schema";
import EditionVolumes from "./EditionVolumes";

type Props = { manga: Manga };

/** 表示ブロック構成(2026-07-12 ユーザ裁定・うる星パイロット):
 *  ① 刷(versions)のISBN集合が互いに素 = 別ISBNの新装版等 → 別ブロックに分離(タブをやめる)。
 *     ISBNが重なる刷(同一ISBNのカバー違い)は従来どおりタブ維持(分離すると同ISBNが二重になる)。
 *  ② 並び = 「書影あり×最大巻数(=初版と同巻割りの代表)」を先頭 → 残りは新しい順 →
 *     書影なし(旧初版等)は最後。データは温存、表示順のみ変更。 */
function displayBlocks(editions: Edition[]): Edition[] {
  const blocks: Edition[] = [];
  for (const ed of editions) {
    const vers = ed.versions;
    if (vers && vers.length > 1) {
      const sets = vers.map(
        (v) => new Set(v.volumes.map((x) => x.isbn13).filter(Boolean)),
      );
      const disjoint = sets.every((s, i) =>
        sets.every((t, j) => i === j || ![...s].some((x) => t.has(x))),
      );
      if (disjoint) {
        for (const v of vers) {
          blocks.push({
            ...ed,
            label: `${ed.label} ${v.label}`,
            year_started: v.year_started ?? ed.year_started,
            volumes: v.volumes,
            versions: undefined,
          });
        }
        continue;
      }
    }
    blocks.push(ed);
  }
  const maxVols = Math.max(...blocks.map((b) => b.volumes.length));
  const covered = (b: Edition) => b.volumes.some((v) => v.cover_url);
  const year = (b: Edition) => {
    if (b.year_started) return b.year_started;
    const d = b.volumes[0]?.release_date;
    const y = d ? parseInt(String(d).slice(0, 4), 10) : 0;
    return Number.isFinite(y) ? y : 0;
  };
  return blocks.slice().sort((a, b) => {
    const ca = covered(a) ? 1 : 0;
    const cb = covered(b) ? 1 : 0;
    if (ca !== cb) return cb - ca;
    const fa = ca && a.volumes.length === maxVols ? 1 : 0;
    const fb = cb && b.volumes.length === maxVols ? 1 : 0;
    if (fa !== fb) return fb - fa;
    return year(b) - year(a);
  });
}

export default function VolumeRow({ manga }: Props) {
  if (manga.editions.length === 0) return null;
  const blocks = displayBlocks(manga.editions);

  return (
    <div className="mt-8">
      {blocks.map((ed, idx) => (
        <section
          key={`${ed.type}-${ed.label}`}
          // ★2つ目以降の版は上に太線(版の境界を明示=ユーザ裁定 2026-06-13)
          className={idx > 0 ? "mt-5 border-t-2 border-ink/20 pt-4" : ""}
        >
          {/* 版本体 (= ISBNが重なる刷のみ EditionVolumes 内でタブ切替)。
              ★コーフロー化で省スペースになったので全版を開いて表示。 */}
          <EditionVolumes manga={manga} edition={ed} defaultCollapsed={false} />
        </section>
      ))}
    </div>
  );
}

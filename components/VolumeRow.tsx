import type { Edition, Manga } from "@/lib/schema";
import EditionVolumes from "./EditionVolumes";
import { getTameshiyomi } from "@/lib/tameshiyomi";

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
  // ★代表版(=その作品の基本巻割りを持つ版)。書影は「本物の版」の代理指標として使っているが、
  //   ISBN普及前(概ね1980年以前)の作品は初版に書影が付きようがなく、代理指標が逆に働いて
  //   初版が最下段へ沈む(2026-08-29 ユーザ報告 すすめ!!パイレーツ: ジャンプ・コミックス全11巻が
  //   1巻だけの廉価版より下に出ていた)。そこで最大巻数を満たす版は type==="standard"(=初版)
  //   でも代表として扱う。書影ありの版が最大巻数に満たない時だけ順位が入れ替わる。
  const rep = (b: Edition) =>
    b.volumes.length === maxVols && (covered(b) || b.type === "standard");
  return blocks.slice().sort((a, b) => {
    const ra = rep(a) ? 1 : 0;
    const rb = rep(b) ? 1 : 0;
    if (ra !== rb) return rb - ra;
    const ca = covered(a) ? 1 : 0;
    const cb = covered(b) ? 1 : 0;
    if (ca !== cb) return cb - ca;
    // ★代表が複数ある時は最古=初版を先頭に(2026-08-17 AKIRA型:
    //   通常版1984と新装版2003が両方full+coveredで新装が先頭に出ていた。裁定の意図は
    //   「初版と同巻割りの代表」なので代表群内は古い順)。残り(非代表)は従来どおり新しい順。
    if (ra && rb) return year(a) - year(b);
    return year(b) - year(a);
  });
}

export default function VolumeRow({ manga }: Props) {
  if (manga.editions.length === 0) return null;
  const blocks = displayBlocks(manga.editions);

  // ★試し読みは巻構成が合う版だけに出す(2026-08-10 ユーザ報告=あしたのジョー型):
  //   BookLiveのcidは「title_id+巻番号」なので、冊数の違う版(完全復刻16巻/文庫12巻等)に
  //   同じ番号で付けると別内容の試し読みになる。最大巻番号が bl.max と一致する版のみ対象。
  //   一致版が無い場合(連載中で電子が先行/遅行して±数巻ズレる型)は最大巻数の版だけに出す
  //   (=電子化の底本は原則その作品の基本巻割り。番号は揃っており cur.number<=bl.max ガードも効く)。
  const bl = getTameshiyomi(manga.slug);
  const maxNum = (b: Edition) => Math.max(0, ...b.volumes.map((v) => v.number ?? 0));
  const blBlocks = new Set<Edition>();
  if (bl) {
    const exact = blocks.filter((b) => maxNum(b) === bl.max);
    if (exact.length) exact.forEach((b) => blBlocks.add(b));
    else {
      const top = Math.max(...blocks.map(maxNum));
      blocks.filter((b) => maxNum(b) === top).forEach((b) => blBlocks.add(b));
    }
  }

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
          <EditionVolumes manga={manga} edition={ed} defaultCollapsed={false} bl={blBlocks.has(ed) ? bl : null} />
        </section>
      ))}
    </div>
  );
}

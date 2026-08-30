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
  // ★並び順 (2026-08-30 ユーザ裁定で全面差し替え):
  //   ①**全巻に書影がある版**を上へ ②その中では**1巻の発売日が古い順**。
  //   それまでは「書影があるか」+「最大巻数か」で代表を決めていたが、
  //   書影が1枚も無いタブが先頭に居座る頁が残っていた(ブラック・エンジェルズ=
  //   ジャンプ・コミックス全20巻が書影0/20で先頭、書影12/12の文庫版が2番目)。
  //   読者が最初に見るタブは「絵が揃っている版」であるべき、という裁定。
  //   ★書影の充足で3段(全部 / 一部 / ゼロ)に分け、各段の中は1巻が古い順に並べる。
  const coverTier = (b: Edition) => {
    const n = b.volumes.length;
    if (!n) return 0;
    const c = b.volumes.filter((v) => v.cover_url).length;
    return c === n ? 2 : c > 0 ? 1 : 0;
  };
  // 「1巻」= その版の最小巻番号の巻。 日付が無ければ版の中で最も古い日付を使う。
  const firstDate = (b: Edition) => {
    const vs = b.volumes;
    if (!vs.length) return "9999";
    const head = vs.reduce((m, v) => ((v.number ?? 9999) < (m.number ?? 9999) ? v : m), vs[0]);
    if (head.release_date) return String(head.release_date);
    const ds = vs.map((v) => String(v.release_date || "")).filter(Boolean).sort();
    return ds[0] || "9999";
  };
  return blocks.slice().sort((a, b) => {
    const ta = coverTier(a);
    const tb = coverTier(b);
    if (ta !== tb) return tb - ta;
    const da = firstDate(a);
    const db = firstDate(b);
    if (da !== db) return da < db ? -1 : 1;
    return b.volumes.length - a.volumes.length;   // 同着は巻数が多い方を上に
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

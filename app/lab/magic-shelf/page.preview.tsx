import type { Metadata } from "next";
import { loadMangaListIndex, loadRailMasters } from "@/lib/loadData";
import MagicShelf from "./MagicShelf";
import type { Sample } from "./spell";
import sample from "./sample-books.json";
import "./magic-shelf.css";

// ★プレビュー専用の実験頁。拡張子 .preview.tsx = next.config.ts の pageExtensions が
//   MANGAL_DATA_DIR=.preview-data の時だけ頁として認める(本番ビルドでは頁もJSも作られない)。
// 非索引(sitemap にも載らない: scripts/_gen-sitemap.py は lab/ を拾わない)。
export const metadata: Metadata = {
  title: "魔法の書架(実験)",
  description: "条件を唱えると漫画が一瞬で並び替わり・集まり・沈む、画面ならではの探し方の実験頁。",
  robots: { index: false, follow: false },
};

/** 魔法の書架(/lab/magic-shelf): 現実の本屋を真似ない探し方の雛型。
 *  データ = 見本 sample-books.json(一覧索引から書影のある人気上位を抜いた小さなJSON。
 *  作り直し = python scripts/_gen-magic-shelf-sample.py)。既存の索引ファイルは読まない・変えない。 */
export default function MagicShelfPage() {
  const genres = loadRailMasters().genres.map((g) => ({ key: g.key, name: g.name }));
  // この環境(プレビュー)に作品頁がある本だけ内部リンクにする
  const local = loadMangaListIndex().map((m) => m.slug);
  const data = sample as unknown as Sample;
  return (
    <div className="ms-root">
      <header className="ms-intro">
        <p className="ms-kicker">LAB ── 実験頁(プレビュー専用)</p>
        <h1 className="ms-h1">魔法の書架</h1>
        <p className="ms-lede">
          本棚の前を歩く代わりに、条件を<b>唱える</b>。合う本は手元に<b>集まり</b>、合わない本は深淵へ
          <b>沈む</b>。下のチップを押すか、コンソールに「ファンタジー 90年代 完結」のように打ち込んでください。
          並ぶのは書影のある人気上位 {data.n.toLocaleString()} 作の見本です。
        </p>
      </header>
      <MagicShelf genres={genres} sample={data} local={local} />
    </div>
  );
}

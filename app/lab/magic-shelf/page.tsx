import type { Metadata } from "next";
import { loadRailMasters } from "@/lib/loadData";
import { preloadListIndex } from "@/lib/preloadIndex";
import MagicShelf from "./MagicShelf";
import "./magic-shelf.css";

// 実験頁 = 非索引(sitemap にも載らない: scripts/_gen-sitemap.py は lab/ を拾わない)
export const metadata: Metadata = {
  title: "魔法の書架(実験)",
  description: "条件を唱えると漫画が一瞬で並び替わり・集まり・沈む、画面ならではの探し方の実験頁。",
  robots: { index: false, follow: false },
};

/** 魔法の書架(/lab/magic-shelf): 現実の本屋を真似ない探し方の雛型。
 *  データ = 一覧索引(書影・題名・ジャンル・年・巻数・完結)をクライアントで読む(lib/useMangaIndex)。
 *  既存の頁・データには触れない独立ルート。 */
export default function MagicShelfPage() {
  preloadListIndex(); // 索引そのものが本文の面 = /list・/browse と同じく HTML の段階で通信を始める
  const genres = loadRailMasters().genres.map((g) => ({ key: g.key, name: g.name }));
  return (
    <div className="ms-root">
      <header className="ms-intro">
        <p className="ms-kicker">LAB ── 実験頁</p>
        <h1 className="ms-h1">魔法の書架</h1>
        <p className="ms-lede">
          本棚の前を歩く代わりに、条件を<b>唱える</b>。合う本は手元に<b>集まり</b>、合わない本は深淵へ
          <b>沈む</b>。下のチップを押すか、コンソールに「ファンタジー 90年代 完結」のように打ち込んでください。
        </p>
      </header>
      <MagicShelf genres={genres} />
    </div>
  );
}

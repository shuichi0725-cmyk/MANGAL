import { Suspense } from "react";
import { loadMasters, loadArtBooks, loadIndexSummary } from "@/lib/loadData";
import { DesignNav } from "@/lib/homeDesign";
import type { ListBundle } from "@/lib/schema";
import HomeClient from "../HomeClient";
import BrowseShell from "@/components/BrowseShell";

export const metadata = {
  // ★layout の template が "%s | MANGAL" を付けるので、ここで MANGAL を書かない(二重表示になる)
  title: "漫画を探す — 題名・よみ・著者で検索",
  description:
    "日本の漫画を題名・よみがな・ローマ字・著者名で検索できます。年・出版社・雑誌・分野・ジャンル・完結/連載での絞り込みと、人気順・巻数順・五十音順などの並べ替えに対応。",
  alternates: { canonical: "/browse" },
};

/** グリッド検索(旧トップ): フィルター付き全作品一覧。 ホーム(/)は案11。
 *  ★manga は props で送らず(空配列) HomeClient がクライアントで索引を遅延 fetch。
 *  SSR payload = master + 画集のみ(軽量)。 */
export default function BrowsePage() {
  const masters = loadMasters();
  const data: ListBundle = { manga: [], artBooks: loadArtBooks(), ...masters };
  // ★総数・分類件数だけ先に渡す(フル索引到着まで「全100件」と嘘をつかないため)
  const summary = loadIndexSummary();
  return (
    <>
      {/* ★検索画面にもヘッダー下のアイコンナビを出す(他ページと統一) */}
      <DesignNav />
      {/* ★fallback を null にしない(2026-08-01): 静的書き出しではここが HTML に焼かれるので、
          null だと本文が丸ごと消える(実測: 可視テキスト357字=ヘッダとフッタのみ)。 */}
      <Suspense fallback={<BrowseShell summary={summary} />}>
        <HomeClient data={data} summary={summary} />
      </Suspense>
    </>
  );
}

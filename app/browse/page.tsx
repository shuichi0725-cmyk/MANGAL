import { Suspense } from "react";
import { loadMasters, loadArtBooks } from "@/lib/loadData";
import { DesignNav } from "@/lib/homeDesign";
import type { ListBundle } from "@/lib/schema";
import HomeClient from "../HomeClient";

export const metadata = { alternates: { canonical: "/browse" } };

/** グリッド検索(旧トップ): フィルター付き全作品一覧。 ホーム(/)は案11。
 *  ★manga は props で送らず(空配列) HomeClient がクライアントで索引を遅延 fetch。
 *  SSR payload = master + 画集のみ(軽量)。 */
export default function BrowsePage() {
  const masters = loadMasters();
  const data: ListBundle = { manga: [], artBooks: loadArtBooks(), ...masters };
  return (
    <>
      {/* ★検索画面にもヘッダー下のアイコンナビを出す(他ページと統一) */}
      <DesignNav />
      <Suspense fallback={null}>
        <HomeClient data={data} />
      </Suspense>
    </>
  );
}

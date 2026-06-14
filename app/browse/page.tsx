import { Suspense } from "react";
import { loadAllManga } from "@/lib/loadData";
import { DesignNav } from "@/lib/homeDesign";
import HomeClient from "../HomeClient";

/** グリッド検索(旧トップ): フィルター付き全作品一覧。 ホーム(/)は案11。 */
export default function BrowsePage() {
  const data = loadAllManga();
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

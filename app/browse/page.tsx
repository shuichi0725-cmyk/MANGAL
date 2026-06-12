import { Suspense } from "react";
import { loadAllManga } from "@/lib/loadData";
import HomeClient from "../HomeClient";

/** グリッド検索(旧トップ): フィルター付き全作品一覧。 ホーム(/)は案11。 */
export default function BrowsePage() {
  const data = loadAllManga();
  return (
    <Suspense fallback={null}>
      <HomeClient data={data} />
    </Suspense>
  );
}

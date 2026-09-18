import { Suspense } from "react";
import TokushuClient from "@/components/TokushuClient";
import TokushuStatic from "@/components/TokushuStatic";

export const metadata = {
  title: "日替わり特集 — 毎日変わる漫画セレクション",
  description:
    "年代×ジャンル×対象の組み合わせから毎日ひとつのお題を選び、人気順で最大100作を並べる日替わり特集。過去の号も読めます。",
  alternates: { canonical: "/tokushu" },
};

/** 日替わり特集(2026-08-03 ユーザ採用)。本文はstock JSON+索引のクライアント描画
 *  (=毎日のデータ更新にビルド不要)。useSearchParams(?d=過去号)のためSuspense必須で、
 *  fallbackは空にしない(/browse白紙事故 358e9ceaf の教訓)。
 *  ★2026-09-18: その fallback に TokushuStatic(build時の号をfsで焼く)を置いた。
 *  ハイドレート後は TokushuClient が本当の「今日」/ ?d= の号に差し替えるので体験は不変。 */
export default function TokushuPage() {
  return (
    <div className="mx-auto max-w-2xl lg:max-w-none">
      {/* ★2026-09-18: fallback を「読み込み中…」から **build時の号を焼いた実体**(TokushuStatic)へ。
          useSearchParams を使う client は静的出力では必ず fallback がHTMLになるので、ここが
          配信HTML=Googleが見る中身そのもの。旧は頁固有31字・作品リンク0本の空頁だった。 */}
      <Suspense fallback={<TokushuStatic />}>
        <TokushuClient />
      </Suspense>
    </div>
  );
}

import { Suspense } from "react";
import { DesignNav } from "@/lib/homeDesign";
import TokushuClient from "@/components/TokushuClient";

export const metadata = {
  title: "日替わり特集 — 毎日変わる漫画セレクション",
  description:
    "年代×ジャンル×対象の組み合わせから毎日ひとつのお題を選び、人気順で最大100作を並べる日替わり特集。過去の号も読めます。",
  alternates: { canonical: "/tokushu" },
};

/** 日替わり特集(2026-08-03 ユーザ採用)。本文はstock JSON+索引のクライアント描画
 *  (=毎日のデータ更新にビルド不要)。useSearchParams(?d=過去号)のためSuspense必須で、
 *  fallbackは空にしない(/browse白紙事故 358e9ceaf の教訓)。 */
export default function TokushuPage() {
  return (
    <div className="mx-auto max-w-2xl">
      <DesignNav />
      <Suspense
        fallback={
          <div className="px-4 py-10 text-center">
            <h1 className="text-xl font-black">📅 日替わり特集</h1>
            <p className="mt-2 text-sm text-ink/55">毎日ひとつのお題で最大100作。読み込み中…</p>
          </div>
        }
      >
        <TokushuClient />
      </Suspense>
    </div>
  );
}

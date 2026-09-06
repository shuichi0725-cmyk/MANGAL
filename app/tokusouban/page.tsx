import TokusoubanListClient from "./TokusoubanListClient";
import { DesignNav } from "@/lib/homeDesign";

/** 特装版・限定版の一覧(2026-09-06 新設。ホームの🎁コーナーの「全部見る」先)。
 *  データ=public/data/tokusouban-stock.json(_gen-corner-auto.py が週次再生成)。
 *  ★価格は絶対に出さない [[feedback-no-static-prices]]。 */
export const metadata = {
  alternates: { canonical: "/tokusouban" },
  title: "特装版・限定版が出ている漫画",
  description:
    "小冊子・グッズつきなど、特別仕様で刊行された漫画の特装版・限定版の一覧。作品ごとに何巻の特装版が出ているかを書影つきで一覧できます。",
};

export default function TokusoubanPage() {
  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <DesignNav />
      <div className="px-4 pb-2 pt-6">
        <h1 className="text-[19px] font-extrabold">🎁 特装版・限定版が出ている漫画</h1>
        <p className="mt-1 text-[12px] leading-relaxed text-ink/60">
          小冊子・ドラマCD・グッズつきなど、特別仕様で出た巻を集めました。書影は特装版のものです。
        </p>
      </div>
      <TokusoubanListClient />
    </div>
  );
}

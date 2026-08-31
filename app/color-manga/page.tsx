import ColorListClient from "./ColorListClient";
import { DesignNav } from "@/lib/homeDesign";

/** 電子カラー版で読める漫画の一覧(2026-07-30 柱化)。
 *  データ=public/data/color-editions.json(_color-editions-build.py 生成)。
 *  クライアントfetch方式なのでJSON差し替えだけで一覧も追随する(sansedai-archiveと同型)。 */
export const metadata = {
  alternates: { canonical: "/color-manga" },
  title: "カラー版で読める漫画",
  description: "電子書籍(楽天Kobo)でフルカラー版が配信されている漫画の一覧。巻数・ストアリンクつき。",
};

export default function ColorMangaPage() {
  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <DesignNav />
      <div className="px-4 pb-2 pt-6">
        <h1 className="text-[19px] font-extrabold">🎨 カラー版で読める漫画</h1>
        <p className="mt-1 text-[12px] leading-relaxed text-ink/60">
          電子書籍だけで配信されているフルカラー版。紙とは別の贅沢な読み心地です。
        </p>
      </div>
      <ColorListClient />
    </div>
  );
}

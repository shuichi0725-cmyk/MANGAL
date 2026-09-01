import type { Metadata } from "next";
import ShinkanClient from "./ShinkanClient";
import { DesignNav } from "@/lib/homeDesign";
import ShinkanAbout from "@/components/ShinkanAbout";
import ShinkanMonthNav from "@/components/ShinkanMonthNav";
import { listShinkanMonths } from "@/lib/shinkanData";

export const metadata: Metadata = {
  title: "漫画・コミック 新刊発売日一覧(今月)",
  description: "今月発売の漫画・コミック新刊を発売日ごとに全冊、書影つきで一覧。スクロールだけで今月の新刊発売日が全部わかる。",
  alternates: { canonical: "https://mangal-db.com/shinkan" },
};

export default function ShinkanPage() {
  return (
    <>
      <DesignNav />
      <ShinkanClient />
      {/* ★静的リンク+解説(2026-09-01 SEO): 対話面は client 描画で Google に空に見えるため、
          月別ページ(/shinkan/YYYY-MM)・今週・来月へのクロール導線と本文をここで焼く */}
      <ShinkanMonthNav months={listShinkanMonths()} />
      <ShinkanAbout />
    </>
  );
}

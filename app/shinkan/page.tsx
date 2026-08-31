import type { Metadata } from "next";
import ShinkanClient from "./ShinkanClient";
import { DesignNav } from "@/lib/homeDesign";

export const metadata: Metadata = {
  title: "漫画コミック 新刊発売日一覧",
  description: "今月発売の漫画・コミック新刊を発売日ごとに全冊、書影つきで一覧。スクロールだけで今月の新刊発売日が全部わかる。",
  alternates: { canonical: "https://mangal-db.com/shinkan" },
};

export default function ShinkanPage() {
  return (
    <>
      <DesignNav />
      <ShinkanClient />
    </>
  );
}

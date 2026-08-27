import type { Metadata } from "next";
import ShinkanClient from "./ShinkanClient";
import { DesignNav } from "@/lib/homeDesign";

export const metadata: Metadata = {
  title: "今月の新刊一覧 | MANGAL",
  description: "今月発売の漫画新刊を発売日ごとに全冊、書影つきで一覧。スクロールだけで月の新刊が全部わかる。",
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

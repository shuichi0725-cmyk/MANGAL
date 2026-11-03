import type { Metadata } from "next";
import { GUIDE_BODY } from "./body";
import "./guide.css";

// ★使い方(2026-11-03 ユーザ裁定): 検索と羅針盤の使い方を、本番画面の写真と軽いアニメで説明する静的頁。
//   入口 = /about の枠・検索(/browse)の2か所・羅針盤の「?」と左下の付箋。
export const metadata: Metadata = {
  alternates: { canonical: "/guide" },
  title: "使い方 — 検索と羅針盤",
  description:
    "MANGAL の使い方。検索ではフィルター(連載状態・巻数・分野・ジャンル・要素・出版社など)の組み合わせ方を、" +
    "羅針盤では作者・雑誌・年・ジャンル・要素の糸をたどって次の一冊を探す方法を、写真と動く図で説明します。",
};

export default function GuidePage() {
  return <div className="gd" dangerouslySetInnerHTML={{ __html: `<div class="wrap">${GUIDE_BODY}</div>` }} />;
}

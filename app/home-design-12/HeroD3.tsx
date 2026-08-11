"use client";

import { useEffect, useState } from "react";

/** D3ヒーロー(2026-08-11 トップ改装トライアル)。
 *  ★コピーはリロード毎ランダム(ユーザ裁定)。SEO対策= この巨大タイポはh1にしない(装飾p扱い)。
 *  h1相当の固定文言はページ側に置く。CLS対策=枠高さ固定+候補は全て2行×最大8字に揃える。 */

const COPIES: Array<[string, string]> = [
  ["ぜんぶ、", "載ってる。"],
  ["探せない漫画は、", "ない。"],
  ["", "収蔵。"], // 先頭要素は総数で動的生成(下で差し替え)
  ["漫画の", "全記録。"],
  ["今日も、", "増えてる。"],
  ["全巻・全版・", "全日付。"],
  ["1919年から、", "現在まで。"], // 実データ最古=漫画吾輩は猫である(1919)
  ["絶版だって、", "載ってる。"],
  ["何巻まで?に", "即答。"],
  ["漫画の", "記憶装置。"],
  ["", "整列済み。"], // 冊数は実数で動的生成(下で差し替え。52万は仮置き数字の捏造だった=2026-08-12ユーザ指摘)
  ["本棚の、", "その先へ。"],
  ["一巻から、", "最終巻まで。"],
  ["漫画史、", "全部入り。"],
  ["次の一冊、", "ここで決まる。"],
  ["昨日の新刊も、", "載ってる。"],
];

export default function HeroD3({ total, books }: { total: number; books: number }) {
  // SSR/初回は既定コピー(=hydration不一致を避ける)。マウント後に抽選で差し替え。
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    setIdx(Math.floor(Math.random() * COPIES.length));
  }, []);
  const totalStr = total.toLocaleString();
  const manStr = `${Math.floor(books / 10000)}万冊`; // 例: 263,872 → 26万冊
  let [l1, l2] = COPIES[idx];
  if (idx === 2) [l1, l2] = [`${totalStr}作品、`, "収蔵。"];
  if (l2 === "整列済み。") l1 = `${manStr}、`;
  return (
    <section className="relative overflow-hidden border-b-[3px] border-[var(--color-accent)] px-4 pb-5 pt-7">
      <div aria-hidden="true" className="pointer-events-none absolute -right-6 top-3 select-none text-[118px] font-black leading-none text-white opacity-[0.06]">
        DB
      </div>
      {/* 装飾タイポ(h1ではない=リロード毎に変えてもSEOシグナル不変) */}
      <p className="min-h-[104px] text-[40px] font-black leading-[1.06] tracking-tight">
        {l1}
        <br />
        <span
          className="text-transparent"
          style={{ WebkitTextStroke: "2px var(--color-accent)" }}
        >
          {l2}
        </span>
      </p>
      <span className="mt-3 inline-block bg-[var(--color-accent)] px-3 py-1.5 text-[11px] font-black tracking-[0.16em] text-[#0d0d0d]">
        JAPANESE MANGA DATABASE
      </span>
      {/* 素のGETフォーム=JS前でも検索できる(/browseのシェルと同じ思想) */}
      <form action="/browse" method="get" className="mt-5 flex border-[3px] border-[var(--color-accent)] bg-[var(--color-surface)] shadow-[6px_6px_0_rgba(217,248,67,0.25)]">
        <input
          type="search"
          name="q"
          placeholder="タイトル・よみがな・ローマ字…"
          aria-label="作品を検索"
          className="min-w-0 flex-1 bg-transparent px-3.5 py-3 text-[14px] font-bold text-[var(--color-ink)] outline-none"
        />
        <button type="submit" className="bg-[var(--color-accent)] px-5 text-[14px] font-black text-[#0d0d0d]">
          検索
        </button>
      </form>
    </section>
  );
}

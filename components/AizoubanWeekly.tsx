"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import CoverImage from "./CoverImage";
import { jstDayIndex } from "./SansedaiDaily";

/** 📚 今週の愛蔵版・合本(2026-09-06 ユーザ裁定で旧「特装版・限定版」コーナーを置換)。
 *  出すのは **通常版より巻数が圧縮された合本だけ**(愛蔵版/完全版/ワイド版/新装版/デラックス)。
 *  ★「冊数が通常版と同じ版は判型も値段も普通の再版=豪華本ではない」= ユーザ裁定。
 *    その選別は生成器(_gen-corner-auto.py)側で済ませてある(圧縮率0.30〜0.70+連番完備+1巻書影)。
 *  ★価格は絶対に表示しない(静的価格=規約違反+誤データ [[feedback-no-static-prices]])。
 *  データ= public/data/aizouban-stock.json(週次再生成)。並びは生成器が同一作品を
 *  窓4件に入れないよう散らし済み= 旧コーナーの「4点とも同じ作品」事故(31%の週)の再発防止。 */
type Aiz = {
  s: string; // slug
  t: string; // 題
  e: string; // 版種
  l: string; // レーベル(imprint)
  v: number; // この版の巻数
  sv: number; // 通常版の巻数
  c: string; // 1巻書影
  d: string; // 1巻発売年
};

const TYPE_JA: Record<string, string> = {
  aizoban: "愛蔵版",
  kanzenban: "完全版",
  wideban: "ワイド版",
  shinsoban: "新装版",
  deluxe: "デラックス版",
  other: "特装",
};

export default function AizoubanWeekly() {
  const [stock, setStock] = useState<Aiz[] | null>(null);
  // SSR時は週を確定させない(build時の週が焼き付くhydrationズレ回避=WeekendFeatureと同型)
  const [week, setWeek] = useState<number | null>(null);
  useEffect(() => {
    setWeek(Math.floor(jstDayIndex() / 7));
    fetch("/data/aizouban-stock.json")
      .then((r) => (r.ok ? r.json() : []))
      .then(setStock)
      .catch(() => setStock([]));
  }, []);
  if (week === null || !stock || stock.length === 0) return null;
  const N = 4;
  const start = ((week * N) % stock.length + stock.length) % stock.length;
  const picks = Array.from({ length: Math.min(N, stock.length) }, (_, i) => stock[(start + i) % stock.length]);
  return (
    <section className="mt-4 px-4">
      <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm">
        <h2 className="dot-heading text-[14px] font-extrabold">
          📚 今週の愛蔵版・合本
          <span className="ml-1.5 text-[10px] font-semibold text-ink/45">週替わり</span>
        </h2>
        <p className="pt-0.5 text-[10.5px] text-ink/55">全巻がぐっと少ない冊数にまとまった版。棚に置きやすく、読み返しやすい。</p>
        <div className="mt-2.5 grid grid-cols-4 gap-2.5">
          {picks.map((p) => (
            <Link key={`${p.s}-${p.e}-${p.v}`} href={`/manga/${p.s}`} className="spring-press block">
              <div
                className="relative overflow-hidden rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)]"
                style={{ aspectRatio: "2 / 3" }}
              >
                <CoverImage src={p.c} alt={`${p.t} ${TYPE_JA[p.e] ?? p.e}`} sizes="120px" />
                <span className="absolute left-0 top-0 rounded-br-md bg-[var(--color-accent)] px-1 py-[1px] text-[9px] font-bold text-[var(--color-on-accent)]">
                  {TYPE_JA[p.e] ?? p.e}
                </span>
              </div>
              <p className="mt-1 truncate text-[10.5px] font-semibold">{p.t}</p>
              <p className="truncate text-[9.5px] tabular-nums text-ink/50">
                全{p.sv}巻 → <b className="text-ink/70">{p.v}巻</b>
              </p>
            </Link>
          ))}
        </div>
        <p className="mt-2 text-[10px] text-ink/45">合本・大判で刊行された版だけを集めています。各作品ページの版タブから巻ごとの詳細へ。</p>
      </div>
    </section>
  );
}

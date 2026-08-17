"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import CoverImage from "@/components/CoverImage";

/** 🌈カラー版コーナー(2026-08-12 ユーザ採用: ボタン=案3「COLOR透かし」+中身=案B「書影だけの密な帯」)。
 *  設置=ホームの全集コーナー直上。
 *  ★2026-08-17 ユーザ裁定で単純化: 帯のスクロール・個別タップ(旧=Kindle直行)を廃止し、
 *    **コーナー全体がどこを押しても /color-manga へ飛ぶ1枚のリンク**に。
 *    書影は表示のたびにカラー作品からランダム抽選(クライアント側=リロード毎に変わる)。
 *  データ=public/data/color-editions.json(_color-editions-build.py)。
 *  色トークンは全部テーマ変数=ライト/D3両対応(COLOR透かしの4色グラデのみ固定色)。 */

type Entry = { v: number; u: string; c?: string | null; b?: string; t?: string };

const SHOW = 14;

export default function ColorCorner() {
  const [rows, setRows] = useState<Array<[string, Entry]> | null>(null);
  const [total, setTotal] = useState(0);
  useEffect(() => {
    fetch("/data/color-editions.json")
      .then((r) => (r.ok ? r.json() : {}))
      .then((data: Record<string, Entry>) => {
        setTotal(Object.keys(data).length);
        // ★毎回ランダム(2026-08-17): 書影ありからFisher-Yatesで抽選。マウント毎=リロード毎に変わる
        const pool = Object.entries(data).filter(([, e]) => e.c);
        for (let i = pool.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1));
          [pool[i], pool[j]] = [pool[j], pool[i]];
        }
        setRows(pool.slice(0, SHOW));
      })
      .catch(() => setRows([]));
  }, []);
  if (rows === null || rows.length === 0) return null;
  return (
    <section className="mt-4 px-4">
      {/* ★ブロック全体が1リンク=どこを押しても /color-manga(帯の書影は装飾=個別リンク無し) */}
      <Link
        href="/color-manga"
        className="spring-press block overflow-hidden rounded-xl border border-[var(--color-line)] border-b-4 border-b-[var(--color-accent)] bg-[var(--color-surface)] shadow-sm"
      >
        <div className="relative overflow-hidden px-3.5 pb-2.5 pt-3.5">
          <span
            aria-hidden="true"
            className="pointer-events-none absolute -right-1 -top-3 bg-clip-text text-[52px] font-black leading-none tracking-[-0.04em] text-transparent opacity-50"
            style={{ backgroundImage: "linear-gradient(90deg,#29b7e5,#e254a4,#f2d23c,#57c465)" }}
          >
            COLOR
          </span>
          <span className="relative inline-block border border-[var(--color-accent)] px-1.5 py-0.5 text-[9px] font-extrabold tracking-[0.22em] text-[var(--color-accent)]">
            FULL COLOR EDITION
          </span>
          <span className="relative ml-1.5 text-[8.5px] text-ink/45">[PR]</span>
          <p className="relative mt-1.5 text-[17px] font-black leading-tight">
            カラー版で読める漫画 <span className="text-[var(--color-accent)]">→</span>
          </p>
          <p className="relative mt-0.5 text-[10.5px] text-ink/55">紙は白黒でも、電子はフルカラー。</p>
        </div>
        <ul className="flex gap-1 overflow-hidden px-3 pb-3" aria-hidden="true">
          {rows.map(([slug, e]) => (
            <li
              key={slug}
              className="h-[92px] w-[62px] shrink-0 overflow-hidden border border-[var(--color-line)] bg-[var(--color-surface-2)]"
            >
              <CoverImage src={e.c!} alt="" sizes="62px" size="card" />
            </li>
          ))}
          <li className="flex h-[92px] w-[62px] shrink-0 flex-col items-center justify-center gap-0.5 border border-[var(--color-accent)]">
            <span className="text-[15px] font-black tabular-nums text-[var(--color-accent)]">{total}</span>
            <span className="text-[8.5px] text-ink/60">作品</span>
            <span className="text-[8.5px] font-black text-[var(--color-accent)]">→ 全部</span>
          </li>
        </ul>
      </Link>
    </section>
  );
}

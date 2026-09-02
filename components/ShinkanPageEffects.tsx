"use client";

import { useEffect } from "react";
import { fastScrollTo } from "@/components/ShinkanDayHeader";
import { jstDay, jstYm } from "@/lib/shinkanDates";

/** 静的化した /shinkan の互換・体験部品(描画なし。2026-09-01):
 *  ①旧URL `?m=YYYY-MM`(共有リンク・ブックマーク)→ 月別ページ /shinkan/YYYY-MM へ置換遷移
 *  ②`?go=today`(ホーム「全部見る」2026-08-27 ユーザ要望)= 今月ページで「今日(無ければ直近の前の発売日)」へ高速スクロール */
export default function ShinkanPageEffects({ ym, days }: { ym: string; days: number[] }) {
  useEffect(() => {
    let sp: URLSearchParams;
    try {
      sp = new URLSearchParams(window.location.search);
    } catch {
      return;
    }
    const m = sp.get("m");
    const goToday = sp.get("go") === "today";
    if (m && /^\d{4}-\d{2}$/.test(m) && m !== ym) {
      window.location.replace(`/shinkan/${m}${goToday ? "?go=today" : ""}`);
      return;
    }
    if (!goToday || ym !== jstYm() || !days.length) return;
    const today = jstDay();
    const target = [...days].reverse().find((n) => n <= today) ?? days[0];
    requestAnimationFrame(() => {
      const el = document.getElementById(`day-${target}`);
      if (el) fastScrollTo(el);
    });
  }, [ym, days]);
  return null;
}

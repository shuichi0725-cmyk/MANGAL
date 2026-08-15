"use client";

import { useEffect, useState } from "react";

/** E型ステータスバーの日付(2026-08-15)。静的ビルドの焼き込み日付だと週次まで古いままなので
 *  クライアントで当日を出す。SSR/初回は空(hydration不一致回避=HeroD3のランダムコピーと同じ流儀)。 */
const WD = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];

export default function StatusDate() {
  const [s, setS] = useState("");
  useEffect(() => {
    const d = new Date();
    const p = (n: number) => String(n).padStart(2, "0");
    setS(`${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${WD[d.getDay()]}`);
  }, []);
  return <span className="tabular-nums">{s}</span>;
}

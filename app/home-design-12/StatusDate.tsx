"use client";

import { useEffect, useState } from "react";

/** マーキー帯の先頭日付(2026-08-17 案D=ユーザ裁定「前のヘッダー+日付はマーキーに」)。
 *  静的ビルドの焼き込みだと週次まで古いままなのでクライアントで当日を出す。
 *  SSR/初回は空(hydration不一致回避)。形式=「8/17(月) ✺ 」(モックD準拠のコンパクト表記)。 */
const WD = ["日", "月", "火", "水", "木", "金", "土"];

export default function StatusDate() {
  const [s, setS] = useState("");
  useEffect(() => {
    const d = new Date();
    setS(`${d.getMonth() + 1}/${d.getDate()}(${WD[d.getDay()]}) ✺ `);
  }, []);
  return <span className="tabular-nums">{s}</span>;
}

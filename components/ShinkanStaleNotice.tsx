"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { jstYm, ymLabel } from "@/lib/shinkanDates";

/** 「来月の新刊」固定URLの鮮度保険: build 時の来月と閲覧時の来月がずれていたら案内を出す
 *  (データ週=面HTMLを焼き直さない週に月をまたいだ場合)。 */
export default function ShinkanStaleNotice({ builtYm, offset }: { builtYm: string; offset: number }) {
  const [nowYm, setNowYm] = useState<string | null>(null);
  useEffect(() => {
    const cur = jstYm(offset);
    if (cur !== builtYm) setNowYm(cur);
  }, [builtYm, offset]);
  if (!nowYm) return null;
  return (
    <p className="mx-4 mt-2 border border-[var(--color-accent)] px-3 py-2 text-[12px] font-bold">
      月が変わりました。最新の{offset === 1 ? "来月" : "今月"}分は{" "}
      <Link href={`/shinkan/${nowYm}`} className="underline text-[var(--color-accent)]">{ymLabel(nowYm)}の新刊一覧</Link> をご覧ください。
    </p>
  );
}

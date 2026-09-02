"use client";

import { useEffect, useState, type ReactNode } from "react";
import { ShinkanMonthList } from "@/components/ShinkanRow";
import { KNOWN_ALL, monthSignature, type ShinkanMonth } from "@/lib/shinkanDates";

/** 鮮度保険(2026-09-01 静的化に伴う): build 時に焼いた本文(children)を出しつつ、
 *  閲覧時に /shinkan/{ym}.json を1回取り、署名が違えば(=データ週にJSONだけ更新された等)
 *  その場で本文を差し替える。同じなら何もしない(children のまま=二重描画なし)。
 *  ★取り直し分の「詳細」は全作品に出す(本番は全slugが索引に居る。preview subset でも実害は404のみ)。 */
export default function ShinkanLive({ ym, sig, children }: { ym: string; sig: string; children: ReactNode }) {
  const [fresh, setFresh] = useState<ShinkanMonth | null>(null);
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await fetch(`/shinkan/${ym}.json`, { cache: "no-cache" });
        if (!r.ok) return;
        const d = (await r.json()) as ShinkanMonth;
        if (alive && monthSignature(d) !== sig) setFresh(d);
      } catch {
        /* 取れなければ build 時の内容のまま */
      }
    })();
    return () => {
      alive = false;
    };
  }, [ym, sig]);
  if (!fresh) return <>{children}</>;
  return (
    <>
      <p className="px-4 pt-2 text-[10.5px] text-ink/45">(最新のデータに更新しました)</p>
      <ShinkanMonthList ym={ym} data={fresh} known={KNOWN_ALL} />
    </>
  );
}

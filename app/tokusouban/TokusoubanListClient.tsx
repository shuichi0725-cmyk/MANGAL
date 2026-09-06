"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import CoverImage from "@/components/CoverImage";
import type { TksItem } from "@/components/EditionCorners";
import { jaCollator } from "@/lib/collator";

/** 特装版・限定版の一覧(/tokusouban)。既定は**50音順**(2026-09-06 ユーザ指示「名前の順に。
 *  フリガナを参考に」= title_kana キー)。同じ作品の特装版が隣り合う。「新しい順」に切替可。 */
type Sort = "title" | "new";

export default function TokusoubanListClient() {
  const [rows, setRows] = useState<TksItem[] | null>(null);
  const [sort, setSort] = useState<Sort>("title");
  useEffect(() => {
    fetch("/data/tokusouban-stock.json")
      .then((r) => (r.ok ? r.json() : []))
      .then(setRows)
      .catch(() => setRows([]));
  }, []);

  const list = useMemo(() => {
    const src = [...(rows ?? [])];
    // ★50音順=フリガナ(title_kana)基準。無い頁だけ題名で代替(lib/listSort の kana と同式)
    const byKana = (a: TksItem, b: TksItem) =>
      jaCollator.compare(a.k || a.t, b.k || b.t) || (a.v ?? 0) - (b.v ?? 0);
    if (sort === "new") {
      return src.sort((a, b) => (b.d ?? "").localeCompare(a.d ?? "") || byKana(a, b));
    }
    return src.sort(byKana);
  }, [rows, sort]);

  if (rows === null) return <p className="px-4 text-[13px] text-ink/60">読み込み中…</p>;
  const works = new Set(rows.map((r) => r.s)).size;

  return (
    <div className="px-4 pb-8">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <p className="text-[11px] text-ink/50">
          {rows.length}点 / {works}作品
        </p>
        <div className="flex gap-1.5">
          {([["title", "50音順"], ["new", "新しい順"]] as Array<[Sort, string]>).map(([k, label]) => (
            <button
              key={k}
              type="button"
              onClick={() => setSort(k)}
              aria-pressed={sort === k}
              className={`rounded-full border px-2.5 py-1 text-[11px] font-bold spring-press ${
                sort === k
                  ? "border-transparent bg-[var(--color-accent)] text-[var(--color-on-accent)]"
                  : "border-[var(--color-line)] bg-[var(--color-surface)] text-ink/70"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <ul className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-6">
        {list.map((e) => (
          <li key={`${e.s}-${e.v}-${e.l}`}>
            <Link href={`/manga/${e.s}`} className="spring-press block">
              <div
                className="relative overflow-hidden rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)]"
                style={{ aspectRatio: "2 / 3" }}
              >
                <CoverImage src={e.c} alt={`${e.t} ${e.l}`} sizes="(max-width: 640px) 33vw, 16vw" />
                <span className="absolute left-0 top-0 max-w-full truncate rounded-br-md bg-[var(--color-accent)] px-1 py-[1px] text-[9px] font-bold text-[var(--color-on-accent)]">
                  {e.l}
                </span>
              </div>
              <p className="mt-1 line-clamp-2 text-[11px] font-bold leading-snug">{e.t}</p>
              <p className="truncate text-[10px] text-ink/55">{e.a}</p>
              <p className="truncate text-[10px] tabular-nums text-ink/55">
                {e.v ? `${e.v}巻` : "特装"}
                {e.d ? <span className="text-ink/35"> ・{e.d}年</span> : null}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

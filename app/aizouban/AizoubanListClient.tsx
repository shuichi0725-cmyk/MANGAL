"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import CoverImage from "@/components/CoverImage";
import { TYPE_JA, type AizItem } from "@/components/EditionCorners";

/** 愛蔵版・合本の一覧(/aizouban)。版種チップで絞り込み、既定は「通常版の巻数が多い順」
 *  = 長い作品ほど合本の恩恵が大きいので上に来る。 */
const ORDER = ["aizoban", "kanzenban", "wideban", "shinsoban", "deluxe", "other"];

export default function AizoubanListClient() {
  const [rows, setRows] = useState<AizItem[] | null>(null);
  const [type, setType] = useState<string>("all");
  useEffect(() => {
    fetch("/data/aizouban-stock.json")
      .then((r) => (r.ok ? r.json() : []))
      .then(setRows)
      .catch(() => setRows([]));
  }, []);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const r of rows ?? []) c[r.e] = (c[r.e] ?? 0) + 1;
    return c;
  }, [rows]);

  const list = useMemo(() => {
    const src = (rows ?? []).filter((r) => type === "all" || r.e === type);
    return [...src].sort((a, b) => b.sv - a.sv || a.t.localeCompare(b.t, "ja"));
  }, [rows, type]);

  if (rows === null) return <p className="px-4 text-[13px] text-ink/60">読み込み中…</p>;

  const chips: Array<[string, string, number]> = [
    ["all", "すべて", rows.length],
    ...ORDER.filter((k) => counts[k]).map((k) => [k, TYPE_JA[k] ?? k, counts[k]] as [string, string, number]),
  ];

  return (
    <div className="px-4 pb-8">
      <div className="-mx-4 mb-2 flex gap-1.5 overflow-x-auto px-4 pb-1 no-scrollbar">
        {chips.map(([k, label, n]) => (
          <button
            key={k}
            type="button"
            onClick={() => setType(k)}
            aria-pressed={type === k}
            className={`shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-bold spring-press ${
              type === k
                ? "border-transparent bg-[var(--color-accent)] text-[var(--color-on-accent)]"
                : "border-[var(--color-line)] bg-[var(--color-surface)] text-ink/70"
            }`}
          >
            {label} <span className="tabular-nums opacity-70">{n}</span>
          </button>
        ))}
      </div>
      <p className="mb-2 text-[11px] text-ink/50">
        {list.length}点 <span className="text-ink/35">・通常版の巻数が多い順</span>
      </p>
      <ul className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-6">
        {list.map((e) => (
          <li key={`${e.s}-${e.e}-${e.v}`}>
            <Link href={`/manga/${e.s}`} className="spring-press block">
              <div
                className="relative overflow-hidden rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)]"
                style={{ aspectRatio: "2 / 3" }}
              >
                <CoverImage src={e.c} alt={`${e.t} ${TYPE_JA[e.e] ?? e.e}`} sizes="(max-width: 640px) 33vw, 16vw" />
                <span className="absolute left-0 top-0 rounded-br-md bg-[var(--color-accent)] px-1 py-[1px] text-[9px] font-bold text-[var(--color-on-accent)]">
                  {TYPE_JA[e.e] ?? e.e}
                </span>
              </div>
              <p className="mt-1 line-clamp-2 text-[11px] font-bold leading-snug">{e.t}</p>
              <p className="truncate text-[10px] text-ink/55">{e.a}</p>
              <p className="truncate text-[10px] tabular-nums text-ink/55">
                全{e.sv}巻 → <b className="text-ink/75">{e.v}巻</b>
                {e.d ? <span className="text-ink/35"> ・{e.d}年</span> : null}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

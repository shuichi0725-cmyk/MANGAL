"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

export type ListRow = {
  slug: string;
  title: string;
  kana: string;
  authors: string;
  vols: number;
  year: number | null;
  status: string;
  latest: string;
};

type SortKey = "title" | "authors" | "vols" | "year" | "status" | "latest";

/** 一覧表(案6の正式実装): 列タップでソート・検索・状態絞り込み。 全てクライアント内で完結。 */
export default function ListTableClient({ rows }: { rows: ListRow[] }) {
  const [q, setQ] = useState("");
  const [st, setSt] = useState<"" | "ongoing" | "completed">("");
  const [key, setKey] = useState<SortKey>("title");
  const [dir, setDir] = useState<1 | -1>(1);
  const [limit, setLimit] = useState(200);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let r = rows;
    if (st) r = r.filter((x) => (st === "completed" ? x.status === "completed" : x.status !== "completed"));
    if (needle) {
      r = r.filter(
        (x) =>
          x.title.toLowerCase().includes(needle) ||
          x.kana.includes(q.trim()) ||
          x.authors.toLowerCase().includes(needle),
      );
    }
    const sorted = [...r].sort((a, b) => {
      const va = a[key] ?? "";
      const vb = b[key] ?? "";
      if (key === "vols" || key === "year") return (Number(va) - Number(vb)) * dir;
      if (key === "title") return (a.kana || a.title).localeCompare(b.kana || b.title, "ja") * dir;
      return String(va).localeCompare(String(vb), "ja") * dir;
    });
    return sorted;
  }, [rows, q, st, key, dir]);

  const Th = ({ k, children, className = "" }: { k: SortKey; children: React.ReactNode; className?: string }) => (
    <th
      onClick={() => {
        if (key === k) setDir((d) => (d === 1 ? -1 : 1));
        else {
          setKey(k);
          setDir(1);
        }
      }}
      className={`spring-press cursor-pointer select-none border-b border-[var(--color-line)] px-2 py-2 ${className}`}
    >
      {children}
      <span className="ml-0.5 text-ink/35">{key === k ? (dir === 1 ? "▲" : "▼") : ""}</span>
    </th>
  );

  return (
    <div>
      <div className="flex items-center gap-2 px-3 py-2.5">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="題名・よみ・著者で絞り込み…"
          className="min-w-0 flex-1 rounded-full border border-[var(--color-line)] bg-white px-3.5 py-1.5 text-[13px] outline-none focus:border-[var(--color-accent)]"
        />
        {([["", "全て"], ["ongoing", "連載中"], ["completed", "完結"]] as const).map(([v, label]) => (
          <button
            key={v}
            onClick={() => setSt(v)}
            className={`spring-press shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${
              st === v ? "bg-[var(--color-accent)] text-white" : "border border-[var(--color-line)] bg-[var(--color-surface)] text-ink/65"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <p className="px-3 pb-1 text-[11px] text-ink/50">{filtered.length.toLocaleString()} 件</p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] border-collapse text-[12px]">
          <thead className="sticky top-0 bg-[var(--color-surface-2)] text-left text-[11px] text-ink/65">
            <tr>
              <Th k="title">題名</Th>
              <Th k="authors">著者</Th>
              <Th k="vols" className="w-12 text-right">巻</Th>
              <Th k="year" className="w-14 text-right">開始</Th>
              <Th k="status" className="w-12">状態</Th>
              <Th k="latest" className="w-20 text-right">最新刊</Th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, limit).map((m, i) => (
              <tr key={m.slug} className={i % 2 ? "bg-[var(--color-surface)]/60" : ""}>
                <td className="max-w-[200px] border-b border-[var(--color-line)]/60 px-2 py-1.5">
                  <Link href={`/manga/${m.slug}`} className="spring-press block truncate font-medium text-[#1f4e79] active:underline">
                    {m.title}
                  </Link>
                </td>
                <td className="max-w-[120px] truncate border-b border-[var(--color-line)]/60 px-2 py-1.5 text-ink/75">{m.authors}</td>
                <td className="border-b border-[var(--color-line)]/60 px-2 py-1.5 text-right tabular-nums">{m.vols}</td>
                <td className="border-b border-[var(--color-line)]/60 px-2 py-1.5 text-right tabular-nums text-ink/70">{m.year ?? "—"}</td>
                <td className="border-b border-[var(--color-line)]/60 px-2 py-1.5">
                  {m.status === "completed" ? <span className="text-ink/60">完結</span> : <span className="font-semibold text-emerald-700">連載</span>}
                </td>
                <td className="border-b border-[var(--color-line)]/60 px-2 py-1.5 text-right tabular-nums text-ink/60">{m.latest || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filtered.length > limit && (
        <div className="py-3 text-center">
          <button onClick={() => setLimit((l) => l + 300)} className="spring-press rounded-full border border-[var(--color-line)] bg-[var(--color-surface)] px-4 py-1.5 text-[12px] font-semibold text-ink/70">
            さらに表示({(filtered.length - limit).toLocaleString()}件)
          </button>
        </div>
      )}
    </div>
  );
}

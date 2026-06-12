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
  genres: string[];
};

type SortKey = "title" | "authors" | "vols" | "year" | "status" | "latest";

/** 一覧表(案6の正式実装): 列タップでソート・検索・状態絞り込み。 全てクライアント内で完結。 */
// 並び順プリセット(★絞り込みとは独立=AND合成。「完結×開始が古い順」等が成立)
const SORTS: Array<{ id: string; label: string; key: SortKey; dir: 1 | -1 }> = [
  { id: "kana", label: "50音順", key: "title", dir: 1 },
  { id: "year-asc", label: "開始が古い", key: "year", dir: 1 },
  { id: "year-desc", label: "開始が新しい", key: "year", dir: -1 },
  { id: "vols-desc", label: "巻数が多い", key: "vols", dir: -1 },
  { id: "latest-desc", label: "最新刊が新しい", key: "latest", dir: -1 },
];

export default function ListTableClient({ rows }: { rows: ListRow[] }) {
  const [q, setQ] = useState("");
  const [st, setSt] = useState<"" | "ongoing" | "completed">("");
  const [genre, setGenre] = useState("");
  const [key, setKey] = useState<SortKey>("title");
  const [dir, setDir] = useState<1 | -1>(1);
  const [limit, setLimit] = useState(200);

  const genreOptions = useMemo(() => {
    const s = new Set<string>();
    for (const r of rows) for (const g of r.genres) s.add(g);
    return [...s].sort((a, b) => a.localeCompare(b, "ja"));
  }, [rows]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let r = rows;
    // ── 絞り込み層(AND): 状態 × ジャンル × 検索語 ──
    if (st) r = r.filter((x) => (st === "completed" ? x.status === "completed" : x.status !== "completed"));
    if (genre) r = r.filter((x) => x.genres.includes(genre));
    if (needle) {
      r = r.filter(
        (x) =>
          x.title.toLowerCase().includes(needle) ||
          x.kana.includes(q.trim()) ||
          x.authors.toLowerCase().includes(needle),
      );
    }
    // ── 並び順層(絞り込み結果に適用) ──
    const sorted = [...r].sort((a, b) => {
      const va = a[key] ?? "";
      const vb = b[key] ?? "";
      if (key === "vols" || key === "year") return (Number(va) - Number(vb)) * dir;
      if (key === "title") return (a.kana || a.title).localeCompare(b.kana || b.title, "ja") * dir;
      return String(va).localeCompare(String(vb), "ja") * dir;
    });
    return sorted;
  }, [rows, q, st, genre, key, dir]);

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
      {/* ── 絞り込み(フィルター)層 ── */}
      <div className="px-3 pt-2.5">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="題名・よみ・著者で検索…"
          className="w-full rounded-full border border-[var(--color-line)] bg-white px-3.5 py-1.5 text-[13px] outline-none focus:border-[var(--color-accent)]"
        />
        <div className="mt-2 flex items-center gap-1.5 overflow-x-auto pb-0.5">
          <span className="shrink-0 text-[10px] font-bold text-ink/45">絞り込み</span>
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
          <select
            value={genre}
            onChange={(e) => setGenre(e.target.value)}
            className={`spring-press shrink-0 rounded-full border px-2 py-1 text-[11px] font-semibold outline-none ${
              genre ? "border-[var(--color-accent)] bg-[var(--color-accent)] text-white" : "border-[var(--color-line)] bg-[var(--color-surface)] text-ink/65"
            }`}
          >
            <option value="">ジャンル: 全て</option>
            {genreOptions.map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
        </div>
        {/* ── 並び順層(絞り込みとは独立にAND合成) ── */}
        <div className="mt-1.5 flex items-center gap-1.5 overflow-x-auto pb-1">
          <span className="shrink-0 text-[10px] font-bold text-ink/45">並び順　</span>
          {SORTS.map((s) => {
            const active = key === s.key && dir === s.dir;
            return (
              <button
                key={s.id}
                onClick={() => {
                  setKey(s.key);
                  setDir(s.dir);
                }}
                className={`spring-press shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                  active ? "bg-ink text-white" : "border border-[var(--color-line)] bg-[var(--color-surface)] text-ink/65"
                }`}
              >
                {s.label}
              </button>
            );
          })}
        </div>
      </div>
      <p className="px-3 pb-1 text-[11px] text-ink/50">
        {filtered.length.toLocaleString()} 件
        {st || genre ? <span className="text-ink/40">(絞り込み中)</span> : null}
      </p>
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

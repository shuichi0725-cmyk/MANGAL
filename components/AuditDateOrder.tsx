"use client";

import { useEffect, useMemo, useState } from "react";

type Seq = { num: number; date: string; label: string; back: boolean };
type Item = { title: string; edition: string; imprint: string; n: number; inv: number; seq: Seq[] };
type Data = { note: string; count: number; items: Item[] };

/** [調査用] 発売日逆行(番号順に並べて日付が前巻より古い巻=⚠)を一覧。フィルムコミック混入/再版日混在のパターン確認用。 */
export default function AuditDateOrder() {
  const [data, setData] = useState<Data | null>(null);
  const [limit, setLimit] = useState(120);
  const [q, setQ] = useState("");

  useEffect(() => {
    fetch("/audit/date-order.json").then((r) => r.json()).then(setData).catch(() => setData({ note: "load失敗", count: 0, items: [] }));
  }, []);

  const items = useMemo(() => {
    if (!data) return [];
    const nq = q.trim();
    return nq ? data.items.filter((i) => i.title.includes(nq)) : data.items;
  }, [data, q]);

  if (!data) return <p className="px-5 pt-8 text-sm text-ink/60">読み込み中…</p>;

  return (
    <div className="mx-auto max-w-2xl px-4 pt-6">
      <h1 className="text-lg font-extrabold">🔎 発売日逆行 監査(巻数≤6・逆行≥2年)</h1>
      <p className="mt-1 text-[12px] text-ink/60">{data.note}</p>
      <p className="mt-1 text-[12px] text-ink/50">
        全 {data.count} 件 ・ ⚠=前巻より日付が古い巻(=フィルムコミック混入/再版日混在/誤マージの疑い)
      </p>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="作品名で絞り込み"
        className="mt-3 w-full rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] px-4 py-2.5 text-sm outline-none"
      />
      <p className="mt-2 text-[11px] text-ink/45">表示 {Math.min(limit, items.length)} / {items.length} 件</p>

      <ul className="mt-2 space-y-2">
        {items.slice(0, limit).map((it, idx) => (
          <li key={idx} className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3">
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
              <span className="text-sm font-bold">{it.title}</span>
              <span className="rounded bg-[var(--color-surface-2)] px-1.5 py-0.5 text-[10px] text-ink/60">{it.edition}{it.imprint ? ` / ${it.imprint}` : ""}</span>
              <span className="text-[11px] text-ink/45">全{it.n}巻</span>
              <span className="ml-auto rounded-full bg-[color-mix(in_srgb,var(--color-accent)_15%,transparent)] px-2 py-0.5 text-[11px] font-bold text-[var(--color-accent)]">逆行 {it.inv}年</span>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {it.seq.map((v, i) => (
                <span
                  key={i}
                  className={`rounded px-1.5 py-0.5 text-[11px] tabular-nums ${v.back ? "bg-red-100 font-bold text-red-700" : "bg-[var(--color-surface-2)] text-ink/65"}`}
                  title={v.label}
                >
                  {v.back ? "⚠" : ""}#{v.num}・{v.date || "—"}
                </span>
              ))}
            </div>
          </li>
        ))}
      </ul>
      {limit < items.length && (
        <div className="mt-4 text-center">
          <button onClick={() => setLimit((l) => l + 200)} className="spring-press rounded-full bg-[var(--color-surface-2)] px-5 py-2 text-[13px] font-semibold">
            もっと表示(+200)
          </button>
        </div>
      )}
    </div>
  );
}

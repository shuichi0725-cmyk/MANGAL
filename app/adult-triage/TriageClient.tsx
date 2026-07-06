"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

type Target = {
  slug: string;
  title: string;
  authors: string;
  cover: string | null;
  genres: string[];
  demographic?: string | null;
};
type Verdict = "safe" | "adult_jp" | "adult_us" | "unknown";
const LS_KEY = "mangal-adult-triage";
const LABELS: Array<[Verdict, string, string]> = [
  ["safe", "非成年", "bg-emerald-600"],
  ["adult_us", "米のみ成年", "bg-amber-600"],
  ["adult_jp", "成年(JP)", "bg-rose-700"],
  ["unknown", "不明", "bg-gray-500"],
];

/** 4状態レビュー: 判定はlocalStorageに即保存。上部の進捗+コピー(JSON)+未判定へジャンプ。 */
export default function TriageClient({ targets }: { targets: Target[] }) {
  const [judg, setJudg] = useState<Record<string, Verdict>>({});
  const [onlyPending, setOnlyPending] = useState(true);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (raw) setJudg(JSON.parse(raw));
    } catch {}
  }, []);
  const save = (slug: string, v: Verdict) => {
    const next = { ...judg, [slug]: v };
    setJudg(next);
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(next));
    } catch {}
  };
  const done = Object.keys(judg).length;
  const list = useMemo(
    () => (onlyPending ? targets.filter((t) => !judg[t.slug]) : targets),
    [targets, judg, onlyPending],
  );
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(judg, null, 1));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };
  return (
    <div className="mx-auto max-w-[720px] px-4">
      <h1 className="mt-4 text-[16px] font-extrabold">🔞 成年3分けレビュー <span className="text-[11px] font-semibold text-ink/45">テスト専用</span></h1>
      <p className="mt-1 text-[11px] text-ink/55">
        adult_us(米のみ成年)フラグ付き {targets.length}作を確定します。判定はこの端末に自動保存。
        終わったら「コピー」でJSONを取り出してClaudeに貼ればseed化されます。
      </p>
      <div className="sticky top-0 z-10 mt-2 flex items-center gap-2 rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)]/95 p-2 text-[12px] backdrop-blur">
        <b className="tabular-nums">{done}/{targets.length}</b> 判定済
        <label className="ml-2 flex items-center gap-1">
          <input type="checkbox" checked={onlyPending} onChange={(e) => setOnlyPending(e.target.checked)} />
          未判定のみ
        </label>
        <button onClick={copy} className="spring-press ml-auto rounded-full bg-[var(--color-accent)] px-3 py-1 font-bold text-white">
          {copied ? "コピーしました" : `コピー(${done})`}
        </button>
      </div>
      <ul className="mt-3 space-y-3">
        {list.slice(0, 200).map((t) => (
          <li key={t.slug} className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3 shadow-sm">
            <div className="flex gap-3">
              <div className="relative w-[72px] shrink-0 overflow-hidden rounded border border-[var(--color-line)] bg-[var(--color-surface-2)]" style={{ aspectRatio: "2/3" }}>
                {t.cover ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={t.cover} alt="" className="h-full w-full object-cover" loading="lazy" />
                ) : (
                  <span className="flex h-full items-center justify-center text-[9px] text-ink/40">no image</span>
                )}
              </div>
              <div className="min-w-0 flex-1">
                <Link href={`/manga/${t.slug}`} className="text-[13px] font-bold text-[#1f4e79] active:underline">{t.title}</Link>
                <p className="text-[11px] text-ink/55">{t.authors} / {t.demographic ?? "—"} / {t.genres.join("・") || "genreなし"}</p>
                <div className="mt-2 grid grid-cols-4 gap-1.5">
                  {LABELS.map(([v, label, color]) => (
                    <button
                      key={v}
                      onClick={() => save(t.slug, v)}
                      className={`spring-press rounded-full py-1.5 text-[11px] font-bold text-white ${color} ${judg[t.slug] === v ? "ring-2 ring-offset-1 ring-[var(--color-accent)]" : "opacity-80"}`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </li>
        ))}
      </ul>
      {list.length > 200 && <p className="py-3 text-center text-[11px] text-ink/45">(未判定が200件を切るとさらに表示)</p>}
      {list.length === 0 && <p className="py-8 text-center text-[13px] font-bold text-emerald-700">🎉 全件判定済み。上の「コピー」でJSONを取り出してください。</p>}
    </div>
  );
}

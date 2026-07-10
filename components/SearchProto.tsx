"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

type Entry = { slug: string; t: string; k: string; r: string; a: string };

/** 検索語・索引フィールドの正規化(NFKC・カタカナ→ひらがな・小文字・空白記号除去)。
 *  これで「べるせるく / ベルセルク / berserk」が同じに当たる。 */
function norm(s: string): string {
  return (s || "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[ァ-ヶ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60))
    .replace(/[\s　・,.。、!?！？「」『』()()\-―_/]/g, "");
}

/**
 * 索引プロトタイプ(仕様v2 S1)。 検索ボックスに触れた時だけ /idx/search.json を遅延ロードし、
 * クライアントで部分一致検索。 ★全DBをpropsで受け取らない=ページ本体は極小。
 */
export default function SearchProto() {
  const [q, setQ] = useState("");
  const [loaded, setLoaded] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [sizeKB, setSizeKB] = useState(0);
  const [ms, setMs] = useState(0);
  const data = useRef<Entry[] | null>(null);
  const haystack = useRef<string[]>([]);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const scrollRestored = useRef(false);
  const hadInitialQ = useRef(false);

  async function ensureLoaded() {
    if (data.current || loaded === "loading") return;
    setLoaded("loading");
    try {
      const t0 = performance.now();
      const res = await fetch("/idx/search.json");
      const buf = await res.arrayBuffer();
      setSizeKB(Math.round(buf.byteLength / 1024));
      const arr: Entry[] = JSON.parse(new TextDecoder().decode(buf));
      data.current = arr;
      haystack.current = arr.map((e) => norm(`${e.t} ${e.k} ${e.r} ${e.a}`));
      setMs(Math.round(performance.now() - t0));
      setLoaded("ready");
    } catch {
      setLoaded("error");
    }
  }

  // ★戻る対応(2026-07-10 ユーザ相談): 詳細→OS戻るで検索状態が消えないよう、
  //   ①マウント時に URL ?q= から復元(即ロード) ②q変更をURLへ replaceState(履歴を汚さない)。
  useEffect(() => {
    const uq = new URLSearchParams(window.location.search).get("q");
    if (uq) {
      hadInitialQ.current = true;
      setQ(uq);
      void ensureLoaded();
    } else {
      // 新規に開いた時だけキーボードを出す(復元時はautoFocusしない=モバイルで鬱陶しい)
      inputRef.current?.focus();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    const url = new URL(window.location.href);
    if (q) url.searchParams.set("q", q);
    else url.searchParams.delete("q");
    window.history.replaceState(null, "", url.toString());
  }, [q]);
  // ★スクロール復元: 結果は索引ロード後に非同期描画されるため、ready後に一度だけ戻す
  useEffect(() => {
    if (loaded !== "ready" || scrollRestored.current) return;
    scrollRestored.current = true;
    if (!hadInitialQ.current) return;
    const y = sessionStorage.getItem("mangal-search-scroll");
    if (y) {
      sessionStorage.removeItem("mangal-search-scroll");
      requestAnimationFrame(() => window.scrollTo(0, parseInt(y, 10) || 0));
    }
  }, [loaded]);

  // 初回アイドル時に先読み(触る前に裏で用意)
  useEffect(() => {
    const id = window.setTimeout(ensureLoaded, 800);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const nq = norm(q);
  let results: Entry[] = [];
  let searchMs = 0;
  if (nq && data.current) {
    const t0 = performance.now();
    const hs = haystack.current;
    const out: Entry[] = [];
    for (let i = 0; i < hs.length && out.length < 60; i++) {
      if (hs[i].includes(nq)) out.push(data.current[i]);
    }
    results = out;
    searchMs = Math.round((performance.now() - t0) * 100) / 100;
  }

  return (
    <div className="mx-auto max-w-xl px-5 pt-6">
      <h1 className="text-lg font-extrabold">🔍 検索(索引プロトタイプ)</h1>
      <p className="mt-1 text-[11px] text-ink/55">
        S1検索索引(/idx/search.json)を<b>遅延ロード</b>してクライアント検索。全DBはページに同梱しない。
        べるせるく / ベルセルク / berserk いずれでもヒット。
      </p>

      <input
        ref={inputRef}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={ensureLoaded}
        placeholder="作品名・かな・ローマ字・著者で検索"
        className="mt-3 w-full rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] px-4 py-3 text-sm outline-none focus:border-[var(--color-accent)]"
      />

      <div className="mt-2 text-[11px] text-ink/50">
        {loaded === "idle" && "索引: 未ロード(入力で取得)"}
        {loaded === "loading" && "索引: ロード中…"}
        {loaded === "ready" && `索引: ${data.current?.length ?? 0}件 / ${sizeKB}KB / 読込${ms}ms`}
        {loaded === "error" && "索引: 読み込み失敗"}
        {nq && loaded === "ready" && ` ・ ヒット${results.length}件 / 検索${searchMs}ms`}
      </div>

      <ul className="mt-3 divide-y divide-[var(--color-line)] rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)]">
        {results.map((e) => (
          <li key={e.slug}>
            <Link
              href={`/manga/${e.slug}`}
              onClick={() => sessionStorage.setItem("mangal-search-scroll", String(window.scrollY))}
              className="spring-press flex items-baseline justify-between gap-2 px-4 py-3"
            >
              <span className="min-w-0">
                <span className="text-sm font-semibold">{e.t}</span>
                {e.a && <span className="ml-2 text-[11px] text-ink/55">{e.a}</span>}
              </span>
              <span className="shrink-0 text-[10px] text-[var(--color-accent)]">→</span>
            </Link>
          </li>
        ))}
        {nq && loaded === "ready" && results.length === 0 && (
          <li className="px-4 py-4 text-[12px] text-ink/50">該当なし</li>
        )}
      </ul>
    </div>
  );
}

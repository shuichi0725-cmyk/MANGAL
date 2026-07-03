"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  value: string;
  onChange: (v: string) => void;
};

/** 検索ボックス(2026-07-03 高速化): 入力はローカル状態に即反映し、
 *  親(66k件フィルタ)へは ①IME変換中は伝えない ②入力停止300ms後に1回だけ伝える。
 *  = キーストローク毎の全件走査を根絶(入力が重い問題の恒久対策)。 */
export default function SearchBox({ value, onChange }: Props) {
  const [local, setLocal] = useState(value);
  const composing = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // 外部からのリセット(フィルタクリア等)を反映
  useEffect(() => {
    setLocal(value);
  }, [value]);

  const schedule = (v: string, immediate = false) => {
    clearTimeout(timer.current);
    if (composing.current && !immediate) return; // 変換確定まで検索しない
    if (immediate || v === "") {
      onChange(v);
      return;
    }
    timer.current = setTimeout(() => onChange(v), 300);
  };

  return (
    <div className="relative">
      <span
        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink/35"
        aria-hidden="true"
      >
        🔍
      </span>
      <input
        type="search"
        placeholder="タイトル・よみがな・ローマ字で検索"
        value={local}
        onChange={(e) => {
          setLocal(e.target.value);
          schedule(e.target.value);
        }}
        onCompositionStart={() => {
          composing.current = true;
        }}
        onCompositionEnd={(e) => {
          composing.current = false;
          schedule((e.target as HTMLInputElement).value);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") schedule((e.target as HTMLInputElement).value, true);
        }}
        className="w-full rounded-card border border-[var(--color-line)] bg-[var(--color-surface)] shadow-[var(--shadow-soft)] pl-9 pr-10 py-2.5 text-sm transition focus:outline-none focus:border-[var(--color-accent)] focus:shadow-[var(--shadow-lift)]"
      />
      {local && (
        <button
          type="button"
          onClick={() => {
            setLocal("");
            schedule("", true);
          }}
          className="absolute right-2 top-1/2 -translate-y-1/2 flex h-6 w-6 items-center justify-center rounded-full text-ink/40 hover:bg-[var(--color-surface-2)] hover:text-ink transition-colors"
          aria-label="検索をクリア"
        >
          ×
        </button>
      )}
    </div>
  );
}

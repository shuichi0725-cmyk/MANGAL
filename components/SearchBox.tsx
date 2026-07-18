"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  value: string;
  onChange: (v: string) => void;
};

/** 検索ボックス(2026-07-11 ユーザ仕様=ボタン確定型 / 2026-07-19 改訂):
 *  入力はローカル状態のみ。親(66k件フィルタ)へは「検索」ボタン or Enter で確定した時だけ伝える。
 *  ★空も確定制(2026-07-19 ユーザ要望): 文字を全部消しただけでは全件再読込を走らせない
 *  (旧「全消しは即解除」は次の検索語を打つ途中で重い全件描画が挟まる操作性悪化)。
 *  解除は ×ボタン / 空でEnter / 空で検索ボタン の明示操作のみ。IME変換中のEnterは確定しない。 */
export default function SearchBox({ value, onChange }: Props) {
  const [local, setLocal] = useState(value);
  const composing = useRef(false);

  // 外部からのリセット(フィルタクリア/URL復元等)を反映
  useEffect(() => {
    setLocal(value);
  }, [value]);

  const submit = (v: string) => {
    if (composing.current) return;
    onChange(v.trim());
  };

  return (
    <form
      className="relative flex items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        submit(local);
      }}
    >
      <div className="relative min-w-0 flex-1">
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
            setLocal(e.target.value); // 空になっても確定はしない(解除=×/Enter/検索ボタンのみ)
          }}
          onCompositionStart={() => {
            composing.current = true;
          }}
          onCompositionEnd={() => {
            composing.current = false;
          }}
          className="w-full rounded-card border border-[var(--color-line)] bg-[var(--color-surface)] shadow-[var(--shadow-soft)] pl-9 pr-10 py-2.5 text-sm transition focus:outline-none focus:border-[var(--color-accent)] focus:shadow-[var(--shadow-lift)]"
        />
        {(local || value) && (
          <button
            type="button"
            onClick={() => {
              setLocal("");
              onChange("");
            }}
            className="absolute right-2 top-1/2 -translate-y-1/2 flex h-6 w-6 items-center justify-center rounded-full text-ink/40 hover:bg-[var(--color-surface-2)] hover:text-ink transition-colors"
            aria-label="検索をクリア"
          >
            ×
          </button>
        )}
      </div>
      <button
        type="submit"
        className="shrink-0 rounded-card bg-[var(--color-accent)] px-4 py-2.5 text-sm font-bold text-white shadow-[var(--shadow-soft)] active:scale-[0.97] transition"
      >
        検索
      </button>
    </form>
  );
}

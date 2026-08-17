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
      {/* ★ターミナル式に統一(2026-08-17 ユーザ指示: ホームのE型 mangal> 検索窓と同じ見た目に)。
          ボタン確定型の仕様(2026-07-11)は不変=ボタンだけD3調(黒地+ライム枠+ライム字)に。 */}
      <div className="flex min-w-0 flex-1 items-center gap-2 border-2 border-[var(--color-accent)] bg-[#050505] px-3.5 py-2.5 shadow-[3px_3px_0_rgba(217,248,67,0.14)]">
        <span className="shrink-0 text-[12px] font-bold text-[var(--color-accent)]" aria-hidden="true">
          mangal&gt;
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
          className="d3-plain min-w-0 flex-1 text-sm font-bold text-[var(--color-ink)] outline-none"
        />
        {(local || value) && (
          <button
            type="button"
            onClick={() => {
              setLocal("");
              onChange("");
            }}
            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-ink/40 hover:bg-[var(--color-surface-2)] hover:text-ink transition-colors"
            aria-label="検索をクリア"
          >
            ×
          </button>
        )}
        <span aria-hidden="true" className="d3-blink h-[14px] w-2 shrink-0 bg-[var(--color-accent)]" />
      </div>
      <button
        type="submit"
        className="shrink-0 border-2 border-[var(--color-accent)] bg-[#050505] px-4 py-2.5 text-sm font-black text-[var(--color-accent)] active:scale-[0.97] transition"
      >
        検索
      </button>
    </form>
  );
}

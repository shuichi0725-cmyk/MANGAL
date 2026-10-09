"use client";

import { useEffect, useState } from "react";
import type { HiddenMap } from "./compass";

// ★隠し要素(2026-10-09)= 近さの点数にだけ使う、画面には出ない要素。 作品ごとの「鍵」の番号だけが入っている(語は載っていない)。
//   作る道具 = scripts/_build-compass-hidden.py → public/data/compass-hidden.v1.json(本番・テスト環境とも同じ場所)。
//   ★形を変える時はファイル名の v を上げる(古い画面が新しい形を読んで落ちないように)。 取得先はここ1か所と page.tsx の preload。
//   無い・壊れている・遅い時は「隠し要素なし」で進む = 羅針盤は今までと同じ結果で動く。
export const HIDDEN_URL = "/data/compass-hidden.v1.json";
/** これだけ待っても届かなければ、隠し要素なしで始める(周りの本を後から引き直さないため、届いた後では入れ替えない) */
const TIMEOUT_MS = 4000;

export type HiddenState = { settled: boolean; map: HiddenMap | null };
let _state: HiddenState = { settled: false, map: null };
let _started = false;
const _listeners = new Set<() => void>();

function settle(map: HiddenMap | null): void {
  if (_state.settled) return;
  _state = { settled: true, map };
  _listeners.forEach((fn) => fn());
}

/** 取得を(まだなら)始める。 冪等 */
export function startHidden(): void {
  if (_started || typeof window === "undefined") return;
  _started = true;
  const timer = setTimeout(() => settle(null), TIMEOUT_MS);
  fetch(HIDDEN_URL)
    .then((r) => (r.ok ? r.json() : null))
    .then((j: { v?: unknown; p?: unknown } | null) => {
      const ok = !!j && j.v === 1 && !!j.p && typeof j.p === "object" && !Array.isArray(j.p);
      settle(ok ? (j.p as HiddenMap) : null);
    })
    .catch(() => settle(null))
    .finally(() => clearTimeout(timer));
}

/** 隠し要素。 settled = 届いた・無かった・待ち切れなかった のどれかが決まった(それまでは羅針盤の逆引き表を作らない) */
export function useCompassHidden(): HiddenState {
  const [s, setS] = useState<HiddenState>(_state);
  useEffect(() => {
    const on = () => setS(_state);
    _listeners.add(on);
    startHidden();
    on(); // 取得が先に終わっていた時の取り返し
    return () => {
      _listeners.delete(on);
    };
  }, []);
  return s;
}

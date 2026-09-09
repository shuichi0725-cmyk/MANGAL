"use client";

import { useEffect, useState } from "react";
import type { Magazine, Publisher } from "./schema";

/**
 * 左レールの重いマスタ(出版社819社 / 連載誌65誌)を**クライアントで1回だけ**取る。
 *
 * ★経緯 (2026-09-09 ユーザ報告「クラウドフレアの容量が倍くらいに増えた」):
 *   `app/layout.tsx` が `loadMasters()` を `<FilterRail masters={...}>` に props で渡していたため、
 *   publishers+magazines(48.6KB)が**全ルートの RSC ペイロードに直列化**され、
 *   HTML内インライン + `.txt` の2箇所に書かれていた = 1ルート約103KB。
 *   実測 56.6KB(escape済) x 2 x 約92,000ルート = **約9.9GB** = out/ 19.0GB の52%。
 *   `/contact` は全体80.6KBのうち69.4KB(86%)が全出版社リストという状態だった。
 *   → 静的JSON1本(`/data/masters.json`・生成= `scripts/gen-masters-json.ts`)に集約。
 *
 * ★genres(1,199B) と demographics(166B) は **props のまま**残してある(全体の2.8%)。
 *   この2つは常時見えているチップなので、遅延にすると見た目が変わる。
 *
 * ★取得の規律(レール既存の思想に合わせる):
 *   - `enabled=false`(= lg未満 = レールが `display:none`)では**何もしない**。
 *     見えないUIに費用を払わせない([[search_perf_hotspots_2026_08]] と同じ型)。
 *   - モジュールキャッシュ + in-flight 共有で**二重取得しない**(fetchAlt と同方式)。
 *   - 失敗しても投げない = パネルは出版社/連載誌の節だけ空で動く(他の絞り込みは効く)。
 */
export type RailHeavyMasters = { publishers: Publisher[]; magazines: Magazine[] };

const EMPTY: RailHeavyMasters = { publishers: [], magazines: [] };

let _cache: RailHeavyMasters | null = null;
let _inflight: Promise<RailHeavyMasters> | null = null;

function fetchMasters(): Promise<RailHeavyMasters> {
  if (_cache) return Promise.resolve(_cache);
  if (_inflight) return _inflight;
  _inflight = fetch("/data/masters.json")
    .then((r) => (r.ok ? r.json() : EMPTY))
    .then((j: Partial<RailHeavyMasters>) => {
      _cache = { publishers: j.publishers ?? [], magazines: j.magazines ?? [] };
      return _cache;
    })
    .catch(() => {
      _inflight = null; // 一時的な失敗は次の呼び出しで再試行できるようにする
      return EMPTY;
    });
  return _inflight;
}

export function useRailMasters(enabled: boolean): RailHeavyMasters {
  const [masters, setMasters] = useState<RailHeavyMasters>(() => _cache ?? EMPTY);

  useEffect(() => {
    if (!enabled || _cache) return;
    let alive = true;
    fetchMasters().then((m) => {
      if (alive) setMasters(m);
    });
    return () => {
      alive = false;
    };
  }, [enabled]);

  return _cache ?? masters;
}

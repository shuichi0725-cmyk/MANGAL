import fs from "node:fs";
import path from "node:path";

/** 試し読みマップ(ビルド時join用・server component専用)。
 *  data/tameshiyomi-map.json = { slug: [title_id, max_verified_vol, missing?[]] }
 *  生成 = scripts/_gen-tameshiyomi-map.py(週次蒸留の事前再生成で更新)。
 *  URLは持たない: リンクはクライアントで title_id+巻番号3桁 から組む(容量最小)。 */
export type TameshiyomiInfo = { id: string; max: number; miss?: number[] };

let _map: Record<string, [string, number, number[]?]> | null = null;

function loadMap(): Record<string, [string, number, number[]?]> {
  if (_map) return _map;
  try {
    const p = path.join(process.cwd(), "data", "tameshiyomi-map.json");
    _map = JSON.parse(fs.readFileSync(p, "utf-8"));
  } catch {
    _map = {};
  }
  return _map!;
}

export function getTameshiyomi(slug: string): TameshiyomiInfo | null {
  const e = loadMap()[slug];
  if (!e) return null;
  return { id: e[0], max: e[1], ...(e[2] && e[2].length ? { miss: e[2] } : {}) };
}

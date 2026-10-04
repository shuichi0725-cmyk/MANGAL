import { fullCover } from "./coverSlim";

/**
 * 本棚の「番号タイルを押すと書影」用: 作品ごとの巻の書影(2026-10-04)。
 * 生成 = scripts/_build-vol-covers.py → /vc/NN.json(公開slugのハッシュで64本に分割)。
 * ★vcShard は生成側の fnv1a(slug) % 64 と必ず同じにする。 1本は開いた時に1回だけ読む(端末のメモリに保持)。
 */
export type VolCover = { n: number; cover: string | null; date: string | null };

const SHARDS = 64;
const _shards = new Map<number, Promise<Record<string, [number, string | null, string | null][]> | null>>();

/** FNV-1a 32bit(UTF-8)を 64 で割った余り。 */
export function vcShard(slug: string): number {
  let h = 0x811c9dc5;
  for (const b of new TextEncoder().encode(slug)) {
    h ^= b;
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h % SHARDS;
}

/** 楽天の書影を大きく(_ex=600x600)。 楽天以外はそのまま。 */
export function bigCover(c: string | null): string | null {
  if (!c) return null;
  return c.includes("thumbnail.image.rakuten.co.jp") ? c.replace(/\?_ex=\d+x\d+$/, "") + "?_ex=600x600" : c;
}

/** その作品の巻の書影(番号順)。 無い・読めない時は null。 */
export async function loadVolCovers(slug: string): Promise<VolCover[] | null> {
  const i = vcShard(slug);
  let p = _shards.get(i);
  if (!p) {
    p = fetch(`/vc/${String(i).padStart(2, "0")}.json`)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null);
    _shards.set(i, p);
  }
  const sh = await p;
  if (!sh) {
    _shards.delete(i); // 失敗は覚えない(次に開いた時に読み直す)
    return null;
  }
  const rows = sh[slug];
  return rows ? rows.map(([n, c, d]) => ({ n, cover: fullCover(c), date: d })) : null;
}

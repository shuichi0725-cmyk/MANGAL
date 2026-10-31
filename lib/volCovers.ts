import { fullCover } from "./coverSlim";

/**
 * 本棚の「番号タイルを押すと書影」用: 作品ごとの巻の書影(2026-10-04)。
 * 生成 = scripts/_build-vol-covers.py → /vc/NN.json(公開slugのハッシュで64本に分割)。
 * ★vcShard は生成側の fnv1a(slug) % 64 と必ず同じにする。 1本は開いた時に1回だけ読む(端末のメモリに保持)。
 * ★版ごと(2026-10-31 本棚 A+1): 版が2つ以上ある作品は同じ1本の "~e" に {slug: {版ラベル: 巻}} を持つ
 *   (版ラベル = 作品頁の表示ブロックの名前 = components/VolumeRow.tsx displayBlocks)。
 *   ★別名ファイルにせず同じ1本の別キーにした = 旧JS(sh[slug] だけ読む)はそのまま動く・配る所(r2-sync 等)も増やさない。
 */
export type VolCover = { n: number; cover: string | null; date: string | null };

type Row = [number, string | null, string | null];
type Shard = Record<string, Row[]> & { "~e"?: Record<string, Record<string, Row[]>> };

const SHARDS = 64;
const _shards = new Map<number, Promise<Shard | null>>();

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

async function loadShard(slug: string): Promise<Shard | null> {
  const i = vcShard(slug);
  let p = _shards.get(i);
  if (!p) {
    p = fetch(`/vc/${String(i).padStart(2, "0")}.json`)
      .then((r) => (r.ok ? (r.json() as Promise<Shard>) : null))
      .catch(() => null);
    _shards.set(i, p);
  }
  const sh = await p;
  if (!sh) _shards.delete(i); // 失敗は覚えない(次に開いた時に読み直す)
  return sh;
}

const toCovers = (rows: Row[]): VolCover[] => rows.map(([n, c, d]) => ({ n, cover: fullCover(c), date: d }));

/**
 * その作品の巻の書影(番号順)。 無い・読めない時は null。
 * edition = 版ラベル。 その版の巻があればそれ、無ければ(版が1つの作品・版の名前が変わった)作品の既定の巻。
 */
export async function loadVolCovers(slug: string, edition?: string | null): Promise<VolCover[] | null> {
  const sh = await loadShard(slug);
  if (!sh) return null;
  const ed = edition ? sh["~e"]?.[slug]?.[edition] : undefined;
  const rows = ed ?? sh[slug];
  return Array.isArray(rows) ? toCovers(rows) : null;
}

/** 版の今の巻数と1巻の書影(本棚の札用)。 その版の巻が引けない時は null(= 呼ぶ側は登録時点の値・索引の書影を使う)。 */
export async function loadEditionFacts(
  slug: string,
  edition: string,
): Promise<{ total: number; cover: string | null } | null> {
  const sh = await loadShard(slug);
  const rows = sh?.["~e"]?.[slug]?.[edition];
  if (!rows || !rows.length) return null;
  return { total: rows.length, cover: fullCover(rows[0][1]) };
}

/** 作品の版ごとの1巻の書影(作品頁の「しまう」の一覧用)。 版ラベル → 書影。 */
export async function loadEditionCovers(slug: string): Promise<Map<string, string | null>> {
  const sh = await loadShard(slug);
  const eds = sh?.["~e"]?.[slug];
  const out = new Map<string, string | null>();
  if (eds) for (const [label, rows] of Object.entries(eds)) out.set(label, rows.length ? fullCover(rows[0][1]) : null);
  return out;
}

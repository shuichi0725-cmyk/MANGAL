/**
 * 全 70k series の seed3 template entries を生成。 既存 56 entries は保持、
 * 新規分のみ {key, slug?} の最小 entry で追加。 fill は別 phase。
 *
 * key 設計: qid (= series.qid or primary author.qid) || `sid:N`
 * 衝突回避のため qid 不在時は series.id を使う。
 */
import "./_env";
import yaml from "yaml";
import { openDb } from "./_db";
import { writeSeed3, loadSeed3, type Seed3Entry, type Seed3File } from "../lib/seed3";

const db = openDb();

// 既存 entries 読み込み (= 上書き保護)
const existing = loadSeed3();
console.log(`[template] existing entries: ${existing.size}`);

// 全 series + primary author qid + vol count を取得
const rows = db.prepare(`
  SELECT s.id, s.qid AS series_qid, s.title,
         (SELECT m.qid FROM series_authors sa
          JOIN mangaka m ON m.id = sa.mangaka_id
          WHERE sa.series_id = s.id
          ORDER BY CASE sa.role
            WHEN 'writer_artist' THEN 0 WHEN 'writer' THEN 1
            WHEN 'artist' THEN 2 WHEN 'original_author' THEN 3 ELSE 4
          END, m.id
          LIMIT 1) AS author_qid,
         (SELECT COUNT(*) FROM editions e
          JOIN volumes v ON v.edition_id = e.id
          WHERE e.series_id = s.id AND v.is_extra = 0 AND v.number >= 1) AS vol_count
  FROM series s
  ORDER BY s.id
`).all() as {
  id: number;
  series_qid: string | null;
  title: string;
  author_qid: string | null;
  vol_count: number;
}[];

console.log(`[template] DB series: ${rows.length}`);

// 雛型 entries 生成 (= 既存 key は touch せず、 新規分のみ追加)
const merged = new Map<string, Seed3Entry>(existing);
let added = 0;
let kept = 0;
for (const row of rows) {
  const qid = row.series_qid ?? row.author_qid;
  // qid 不在時は series.id で 衝突回避
  const key = qid ? `${qid}|${row.title}` : `sid:${row.id}|${row.title}`;
  if (merged.has(key)) {
    kept++;
    continue;
  }
  // 雛型 = key のみ。 他 fields は fill 時に追加 (= optional)
  merged.set(key, { key });
  added++;
}

const file: Seed3File = {
  schema_version: 1,
  generated_at: new Date().toISOString(),
  generator: "claude-opus-4-7-direct-fill",
  series: [...merged.values()].sort((a, b) => a.key.localeCompare(b.key)),
};
writeSeed3(file);

console.log(`[template] kept: ${kept}, added: ${added}, total: ${merged.size}`);

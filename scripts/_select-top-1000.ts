/**
 * Phase 2: 主要 1000 series を選定。 全集約後の vol_count 降順、 ただし:
 *   - adult_score >= 3 を除外 (= 種3 fill 対象外)
 *   - 既存 56 entries (= 既に手動 curate 済) も list に含める (= overlap OK)
 *
 * 出力: .cache/top-1000.json (= ranked list of {key, sid, qid, title, author, vol})
 */
import "./_env";
import fs from "node:fs";
import { openDb } from "./_db";

const db = openDb();

// 全 series + primary author + total vol_count (= 全 edition primary 集合の概算)
const rows = db.prepare(`
  SELECT s.id, s.qid AS series_qid, s.title, s.year_started, s.year_ended,
         (SELECT m.qid FROM series_authors sa
          JOIN mangaka m ON m.id = sa.mangaka_id
          WHERE sa.series_id = s.id
          ORDER BY CASE sa.role
            WHEN 'writer_artist' THEN 0 WHEN 'writer' THEN 1
            WHEN 'artist' THEN 2 WHEN 'original_author' THEN 3 ELSE 4
          END, m.id
          LIMIT 1) AS author_qid,
         (SELECT m.name FROM series_authors sa
          JOIN mangaka m ON m.id = sa.mangaka_id
          WHERE sa.series_id = s.id
          ORDER BY CASE sa.role
            WHEN 'writer_artist' THEN 0 WHEN 'writer' THEN 1
            WHEN 'artist' THEN 2 WHEN 'original_author' THEN 3 ELSE 4
          END, m.id
          LIMIT 1) AS author_name,
         (SELECT MAX(m.has_adult_credit) FROM series_authors sa
          JOIN mangaka m ON m.id = sa.mangaka_id
          WHERE sa.series_id = s.id) AS author_adult_credit,
         COALESCE(s.adult_score, 0) AS adult_score,
         (SELECT COUNT(*) FROM editions e
          JOIN volumes v ON v.edition_id = e.id
          WHERE e.series_id = s.id AND v.is_extra = 0 AND v.number >= 1) AS vol_count_total,
         (SELECT COUNT(DISTINCT v.number) FROM editions e
          JOIN volumes v ON v.edition_id = e.id
          WHERE e.series_id = s.id AND v.is_extra = 0 AND v.number >= 1
            AND e.type = 'standard') AS std_unique_vols
  FROM series s
`).all() as {
  id: number;
  series_qid: string | null;
  title: string;
  year_started: number | null;
  year_ended: number | null;
  author_qid: string | null;
  author_name: string | null;
  author_adult_credit: number | null;
  adult_score: number;
  vol_count_total: number;
  std_unique_vols: number;
}[];

console.log(`[select] total series in DB: ${rows.length}`);

// adult 除外 + 著者あり + std_unique_vols >= 1
const candidates = rows.filter(
  (r) =>
    r.adult_score < 3 &&
    !r.author_adult_credit &&
    r.author_name &&
    r.std_unique_vols >= 1,
);
console.log(`[select] non-adult + has author + std_vols >= 1: ${candidates.length}`);

// 並び順: standard edition の unique vol count desc → year_started desc (= 新しい優先) → id asc
candidates.sort((a, b) => {
  if (a.std_unique_vols !== b.std_unique_vols) return b.std_unique_vols - a.std_unique_vols;
  const ay = a.year_started ?? 0;
  const by = b.year_started ?? 0;
  if (ay !== by) return by - ay;
  return a.id - b.id;
});

// top 9000
const top9000 = candidates.slice(0, 9000).map((r) => {
  const qid = r.series_qid ?? r.author_qid;
  const key = qid ? `${qid}|${r.title}` : `sid:${r.id}|${r.title}`;
  return {
    rank: 0, // filled below
    key,
    sid: r.id,
    qid,
    title: r.title,
    author: r.author_name,
    year_started: r.year_started,
    year_ended: r.year_ended,
    vol_count: r.std_unique_vols,
    vol_count_total: r.vol_count_total,
  };
});
top9000.forEach((r, i) => (r.rank = i + 1));

fs.mkdirSync(".cache", { recursive: true });
fs.writeFileSync(".cache/top-9000.json", JSON.stringify(top9000, null, 2));
console.log(`[select] wrote .cache/top-9000.json (= ${top9000.length} entries)`);

// Sanity check: rank 8950-9000
console.log(`\n=== rank 8950-9000 (= tail) ===`);
for (const r of top9000.slice(8950, 9000)) {
  console.log(`  ${r.rank.toString().padStart(4)}: vol=${r.vol_count.toString().padStart(3)} / ${r.title} (${r.author})`);
}

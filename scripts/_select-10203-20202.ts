import Database from "better-sqlite3";
import fs from "node:fs";

const db = new Database(".cache/db.sqlite", { readonly: true });
const rows = db.prepare(`
  SELECT s.id, s.qid AS series_qid, s.title, s.year_started, s.year_ended,
         (SELECT m.qid FROM series_authors sa JOIN mangaka m ON m.id = sa.mangaka_id
          WHERE sa.series_id = s.id ORDER BY CASE sa.role
            WHEN 'writer_artist' THEN 0 WHEN 'writer' THEN 1 WHEN 'artist' THEN 2
            WHEN 'original_author' THEN 3 ELSE 4 END, m.id LIMIT 1) AS author_qid,
         (SELECT m.name FROM series_authors sa JOIN mangaka m ON m.id = sa.mangaka_id
          WHERE sa.series_id = s.id ORDER BY CASE sa.role
            WHEN 'writer_artist' THEN 0 WHEN 'writer' THEN 1 WHEN 'artist' THEN 2
            WHEN 'original_author' THEN 3 ELSE 4 END, m.id LIMIT 1) AS author_name,
         (SELECT MAX(m.has_adult_credit) FROM series_authors sa
          JOIN mangaka m ON m.id = sa.mangaka_id WHERE sa.series_id = s.id) AS author_adult_credit,
         COALESCE(s.adult_score, 0) AS adult_score,
         (SELECT COUNT(*) FROM editions e JOIN volumes v ON v.edition_id = e.id
          WHERE e.series_id = s.id AND v.is_extra = 0 AND v.number >= 1) AS vol_count_total,
         (SELECT COUNT(DISTINCT v.number) FROM editions e JOIN volumes v ON v.edition_id = e.id
          WHERE e.series_id = s.id AND v.is_extra = 0 AND v.number >= 1
            AND e.type = 'standard') AS std_unique_vols
  FROM series s
`).all() as any[];

const cand = rows.filter(r => r.adult_score < 3 && !r.author_adult_credit && r.author_name && r.std_unique_vols >= 1);
cand.sort((a,b) => {
  if (a.std_unique_vols !== b.std_unique_vols) return b.std_unique_vols - a.std_unique_vols;
  const ay = a.year_started ?? 0, by = b.year_started ?? 0;
  if (ay !== by) return by - ay;
  return a.id - b.id;
});

const slice = cand.slice(10202, 20202).map((r,i) => ({
  rank: 10203 + i, key: r.series_qid ? `${r.series_qid}|${r.title}` : (r.author_qid ? `${r.author_qid}|${r.title}` : `sid:${r.id}|${r.title}`),
  sid: r.id, qid: r.series_qid ?? r.author_qid, title: r.title, author: r.author_name,
  year_started: r.year_started, year_ended: r.year_ended, vol_count: r.std_unique_vols,
}));
fs.writeFileSync(".cache/next-10000.json", JSON.stringify(slice, null, 2));
console.log(`wrote ${slice.length} entries (rank ${slice[0].rank}-${slice[slice.length-1].rank})`);
console.log(`first: rank=${slice[0].rank} vol=${slice[0].vol_count} title=${slice[0].title}`);
console.log(`last: rank=${slice[slice.length-1].rank} vol=${slice[slice.length-1].vol_count} title=${slice[slice.length-1].title}`);

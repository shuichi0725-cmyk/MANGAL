/**
 * 既存 series テーブルの全 row を series_archive に複製する一回限りのスクリプト。
 *
 * schema v7 で 3-state model (live / excluded / archive) を導入した時点で、
 * archive テーブルは空。 既に live (= series テーブル) に入っている row は
 * 「過去に import されて公開中」 という意味を持つので、 archive にも
 * current_state='live' で対応する row を作る必要がある。
 *
 * これをやらないと:
 *   - 次回 fetch:madb 実行時に existing archive row が見つからず、 全 series が
 *     「新規 import 扱い」 になり、 adult signal が当たれば即 excluded に飛ばされる
 *     (= 既に admin が公開中の series が無断で hide されうる、 まずい)。
 *   - admin UI から既存 series を 「除外」 する操作ができない
 *     (= excluded は archive_id を FK で参照するため、 archive に row が必要)。
 *
 * 使い方:
 *   npm run db:backfill-archive
 *
 * 冪等。 既に archive にある series_key は SKIP する。
 */
import "./_env";
import { openDb, tx } from "./_db";

async function main(): Promise<void> {
  const db = openDb();

  const liveSeries = db
    .prepare(
      `SELECT id, series_key, title, qid, title_kana, year_started, year_ended,
              status, demographic, publisher_key, magazine_key,
              genres, synopsis, wikipedia_url, adult_score, created_at
       FROM series
       ORDER BY id ASC`,
    )
    .all() as {
    id: number;
    series_key: string;
    title: string;
    qid: string | null;
    title_kana: string | null;
    year_started: number | null;
    year_ended: number | null;
    status: string | null;
    demographic: string | null;
    publisher_key: string | null;
    magazine_key: string | null;
    genres: string | null;
    synopsis: string | null;
    wikipedia_url: string | null;
    adult_score: number;
    created_at: string;
  }[];

  console.log(`[backfill-archive] found ${liveSeries.length} live series`);

  const selectArchive = db.prepare(
    "SELECT id FROM series_archive WHERE series_key = ?",
  );
  const insertArchive = db.prepare(
    `INSERT INTO series_archive
       (series_key, qid, title, title_kana, year_started, year_ended,
        status, demographic, publisher_key, magazine_key,
        genres, synopsis, wikipedia_url, adult_score,
        first_imported_at, last_imported_at, current_state)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'live')`,
  );

  let inserted = 0;
  let skipped = 0;
  tx(db, () => {
    for (const s of liveSeries) {
      const existing = selectArchive.get(s.series_key);
      if (existing) {
        skipped++;
        continue;
      }
      // first_imported_at/last_imported_at は series.created_at を使う (= 過去 import 時刻の近似)
      insertArchive.run(
        s.series_key,
        s.qid,
        s.title,
        s.title_kana,
        s.year_started,
        s.year_ended,
        s.status,
        s.demographic,
        s.publisher_key,
        s.magazine_key,
        s.genres,
        s.synopsis,
        s.wikipedia_url,
        s.adult_score,
        s.created_at,
        s.created_at,
      );
      inserted++;
    }
  });

  const archiveCount = (
    db.prepare("SELECT COUNT(*) AS c FROM series_archive").get() as {
      c: number;
    }
  ).c;

  console.log(`[backfill-archive] inserted=${inserted}, skipped=${skipped}`);
  console.log(`[backfill-archive] total archive rows: ${archiveCount}`);
  db.close();
}

main().catch((err) => {
  console.error("[fatal]", err);
  process.exit(1);
});

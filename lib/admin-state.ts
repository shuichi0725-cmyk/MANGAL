/**
 * 3-state model (live / excluded / archive) を操作する純 library。
 *
 * 設計方針:
 *   - 全ての遷移は「archive を source-of-truth として、 series (= live) と
 *     series_excluded を整合させる」 という考え方で書く。
 *   - 全操作で admin_audit に 1 行残す (= 「誰が、 いつ、 何を、 なぜ」)。
 *   - fetch:madb (= scripts/fetch-madb.ts) と並行実行されないことを前提
 *     (= UI/CLI は admin 操作のみ、 import は cron / 手動で別 timing)。
 *   - 列ごとの整合 (= series.series_key と series_archive.series_key の一致)
 *     を保つために必ず seriesKey を介して操作する。
 *
 * 状態遷移:
 *
 *   import 時 (scripts/fetch-madb.ts):
 *     [ø] → archive.live   (= clean な新規)
 *     [ø] → archive.excluded + series_excluded   (= adult signal new)
 *     archive.deleted → no-op   (= 完全削除済み、 import が来ても復活しない)
 *     archive.live → archive.live   (= sticky、 adult signal を無視)
 *     archive.excluded → archive.excluded   (= 引き続き excluded)
 *
 *   admin 操作 (本ファイル):
 *     archive.excluded + series_excluded
 *       --reinstate--> archive.live + series (空 stub) + admin_audit
 *     archive.excluded + series_excluded
 *       --permanentDelete--> archive.deleted + admin_audit
 *     archive.live + series
 *       --manualExclude--> archive.excluded + series_excluded + admin_audit
 *
 * 復帰後の volume 再投入:
 *   reinstate は series テーブルに stub row を作るだけで、 editions/volumes は
 *   作らない。 次回 fetch:madb 実行時に archive.current_state='live' なので
 *   adult signal が無視され、 自然に volumes が埋まる。 admin UI は復帰後に
 *   「fetch:madb を再実行してください」 と案内する。
 */
import type { DB } from "../scripts/_db";

export type ExcludedRow = {
  archiveId: number;
  seriesKey: string;
  title: string;
  yearStarted: number | null;
  yearEnded: number | null;
  publisherKey: string | null;
  adultScore: number;
  reason: string;
  signalsJson: string | null;
  excludedAt: string;
  excludedBy: string;
};

export type AdminAuditRow = {
  id: number;
  action: string;
  targetTable: string;
  targetId: number;
  performedBy: string | null;
  performedAt: string;
  reason: string | null;
  metadataJson: string | null;
};

/**
 * series_excluded の row を archive と join して返す (= 管理者 UI の一覧用)。
 */
export function listExcluded(
  db: DB,
  opts: { limit?: number; offset?: number; reason?: string } = {},
): ExcludedRow[] {
  const limit = opts.limit ?? 100;
  const offset = opts.offset ?? 0;
  const where = opts.reason ? "WHERE e.reason = ?" : "";
  const params: (string | number)[] = opts.reason ? [opts.reason] : [];
  params.push(limit, offset);

  const rows = db
    .prepare(
      `SELECT e.archive_id    AS archiveId,
              a.series_key    AS seriesKey,
              a.title         AS title,
              a.year_started  AS yearStarted,
              a.year_ended    AS yearEnded,
              a.publisher_key AS publisherKey,
              a.adult_score   AS adultScore,
              e.reason        AS reason,
              e.signals_json  AS signalsJson,
              e.excluded_at   AS excludedAt,
              e.excluded_by   AS excludedBy
       FROM series_excluded e
       JOIN series_archive a ON a.id = e.archive_id
       ${where}
       ORDER BY e.excluded_at DESC
       LIMIT ? OFFSET ?`,
    )
    .all(...params) as ExcludedRow[];
  return rows;
}

export function countExcluded(db: DB, reason?: string): number {
  if (reason) {
    return (
      db
        .prepare(
          `SELECT COUNT(*) AS c FROM series_excluded WHERE reason = ?`,
        )
        .get(reason) as { c: number }
    ).c;
  }
  return (
    db.prepare(`SELECT COUNT(*) AS c FROM series_excluded`).get() as {
      c: number;
    }
  ).c;
}

/**
 * 集計: reason ごとの excluded 件数 (= UI の左 nav / dashboard 用)。
 */
export function excludedReasonCounts(db: DB): { reason: string; n: number }[] {
  return db
    .prepare(
      `SELECT reason, COUNT(*) AS n FROM series_excluded GROUP BY reason ORDER BY n DESC`,
    )
    .all() as { reason: string; n: number }[];
}

function insertAudit(
  db: DB,
  action: string,
  targetId: number,
  performedBy: string,
  reason: string | null,
  metadata: unknown = null,
): void {
  db.prepare(
    `INSERT INTO admin_audit
       (action, target_table, target_id, performed_by, reason, metadata_json)
     VALUES (?, 'series_archive', ?, ?, ?, ?)`,
  ).run(
    action,
    targetId,
    performedBy,
    reason,
    metadata === null ? null : JSON.stringify(metadata),
  );
}

/**
 * archive.id から archive snapshot を取る (= 何度も使う query を 1 箇所に)。
 */
function getArchive(
  db: DB,
  archiveId: number,
): {
  id: number;
  series_key: string;
  qid: string | null;
  title: string;
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
  current_state: "live" | "excluded" | "deleted";
} | null {
  const row = db
    .prepare(`SELECT * FROM series_archive WHERE id = ?`)
    .get(archiveId);
  return (row ?? null) as ReturnType<typeof getArchive>;
}

/**
 * excluded → live。
 *   - archive.current_state を 'live' に更新
 *   - series テーブルに archive snapshot から row を作る (既に live にあれば UPDATE しない)
 *   - series_excluded から行を削除
 *   - admin_audit に 'reinstate' を記録
 *
 * 既に series テーブルに同じ series_key の行があれば、 そちらを正として
 * archive 側の state だけ live に直す (= 整合性回復ケース)。
 */
export function reinstate(
  db: DB,
  archiveId: number,
  opts: { performedBy: string; reason?: string },
): { archiveId: number; seriesId: number; created: boolean } {
  const arc = getArchive(db, archiveId);
  if (!arc) throw new Error(`series_archive id=${archiveId} not found`);

  const trx = db.transaction(() => {
    // 既存 live row があるか
    const existingSeries = db
      .prepare(`SELECT id FROM series WHERE series_key = ?`)
      .get(arc.series_key) as { id: number } | undefined;

    let seriesId: number;
    let created = false;
    if (existingSeries) {
      seriesId = existingSeries.id;
    } else {
      const info = db
        .prepare(
          `INSERT INTO series
             (series_key, qid, title, title_kana, year_started, year_ended,
              status, demographic, publisher_key, magazine_key,
              genres, synopsis, wikipedia_url, adult_score)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        )
        .run(
          arc.series_key,
          arc.qid,
          arc.title,
          arc.title_kana,
          arc.year_started,
          arc.year_ended,
          arc.status,
          arc.demographic,
          arc.publisher_key,
          arc.magazine_key,
          arc.genres,
          arc.synopsis,
          arc.wikipedia_url,
          arc.adult_score,
        );
      seriesId = Number(info.lastInsertRowid);
      created = true;
    }

    db.prepare(`DELETE FROM series_excluded WHERE archive_id = ?`).run(
      archiveId,
    );

    db.prepare(
      `UPDATE series_archive
       SET current_state = 'live',
           last_imported_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
       WHERE id = ?`,
    ).run(archiveId);

    insertAudit(db, "reinstate", archiveId, opts.performedBy, opts.reason ?? null, {
      seriesId,
      createdSeriesRow: created,
      previousState: arc.current_state,
    });

    return { archiveId, seriesId, created };
  });
  return trx();
}

/**
 * excluded (or live) → deleted (= archive にのみ残る)。
 *   - series_excluded から削除
 *   - series テーブルに同 series_key があれば削除 (cascade で editions/volumes も消える)
 *   - archive.current_state = 'deleted'
 *   - admin_audit に 'permanent_delete' を記録
 *
 * archive 行自体は永久に残る (= 監査 / 復活用)。
 */
export function permanentDelete(
  db: DB,
  archiveId: number,
  opts: { performedBy: string; reason?: string },
): { archiveId: number; deletedSeriesId: number | null } {
  const arc = getArchive(db, archiveId);
  if (!arc) throw new Error(`series_archive id=${archiveId} not found`);

  const trx = db.transaction(() => {
    db.prepare(`DELETE FROM series_excluded WHERE archive_id = ?`).run(
      archiveId,
    );

    // live にもあれば消す (= cascade で editions/volumes も)
    const liveRow = db
      .prepare(`SELECT id FROM series WHERE series_key = ?`)
      .get(arc.series_key) as { id: number } | undefined;
    if (liveRow) {
      db.prepare(`DELETE FROM series WHERE id = ?`).run(liveRow.id);
    }

    db.prepare(
      `UPDATE series_archive SET current_state = 'deleted' WHERE id = ?`,
    ).run(archiveId);

    insertAudit(
      db,
      "permanent_delete",
      archiveId,
      opts.performedBy,
      opts.reason ?? null,
      {
        deletedSeriesId: liveRow?.id ?? null,
        previousState: arc.current_state,
      },
    );

    return { archiveId, deletedSeriesId: liveRow?.id ?? null };
  });
  return trx();
}

/**
 * live → excluded (= 管理者が手動で hide)。
 *   - series_archive を取得 (= series.series_key 経由)。 無ければ snapshot を作る。
 *   - series テーブルから row を削除 (cascade)
 *   - series_excluded に upsert (reason='manual_admin')
 *   - archive.current_state = 'excluded'
 *   - admin_audit に 'manual_exclude'
 */
export function manualExcludeSeries(
  db: DB,
  seriesId: number,
  opts: { performedBy: string; reason?: string },
): { archiveId: number; seriesId: number } {
  const series = db
    .prepare(
      `SELECT id, series_key, title, qid, title_kana, year_started, year_ended,
              status, demographic, publisher_key, magazine_key,
              genres, synopsis, wikipedia_url, adult_score
       FROM series WHERE id = ?`,
    )
    .get(seriesId) as
    | {
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
      }
    | undefined;
  if (!series) throw new Error(`series id=${seriesId} not found`);

  const trx = db.transaction(() => {
    // archive row を取得 or 作成
    const existingArchive = db
      .prepare(`SELECT id FROM series_archive WHERE series_key = ?`)
      .get(series.series_key) as { id: number } | undefined;

    let archiveId: number;
    if (existingArchive) {
      archiveId = existingArchive.id;
      db.prepare(
        `UPDATE series_archive SET current_state = 'excluded' WHERE id = ?`,
      ).run(archiveId);
    } else {
      const info = db
        .prepare(
          `INSERT INTO series_archive
             (series_key, qid, title, title_kana, year_started, year_ended,
              status, demographic, publisher_key, magazine_key,
              genres, synopsis, wikipedia_url, adult_score, current_state)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'excluded')`,
        )
        .run(
          series.series_key,
          series.qid,
          series.title,
          series.title_kana,
          series.year_started,
          series.year_ended,
          series.status,
          series.demographic,
          series.publisher_key,
          series.magazine_key,
          series.genres,
          series.synopsis,
          series.wikipedia_url,
          series.adult_score,
        );
      archiveId = Number(info.lastInsertRowid);
    }

    db.prepare(
      `INSERT INTO series_excluded
         (archive_id, reason, signals_json, excluded_at, excluded_by)
       VALUES (?, 'manual_admin', NULL,
               strftime('%Y-%m-%dT%H:%M:%SZ','now'), ?)
       ON CONFLICT(archive_id) DO UPDATE SET
         reason       = excluded.reason,
         excluded_at  = excluded.excluded_at,
         excluded_by  = excluded.excluded_by`,
    ).run(archiveId, `admin:${opts.performedBy}`);

    db.prepare(`DELETE FROM series WHERE id = ?`).run(seriesId);

    insertAudit(
      db,
      "manual_exclude",
      archiveId,
      opts.performedBy,
      opts.reason ?? null,
      { seriesId },
    );

    return { archiveId, seriesId };
  });
  return trx();
}

export function listAudit(
  db: DB,
  opts: { limit?: number; offset?: number } = {},
): AdminAuditRow[] {
  const rows = db
    .prepare(
      `SELECT id,
              action,
              target_table  AS targetTable,
              target_id     AS targetId,
              performed_by  AS performedBy,
              performed_at  AS performedAt,
              reason,
              metadata_json AS metadataJson
       FROM admin_audit
       ORDER BY performed_at DESC, id DESC
       LIMIT ? OFFSET ?`,
    )
    .all(opts.limit ?? 50, opts.offset ?? 0) as AdminAuditRow[];
  return rows;
}

/**
 * SQLite DB の中身をテキスト形式で表示する診断ツール。
 * 主な用途は「成人判定で弾かれるはずのレコード」の目視確認。
 *
 *   npm run db:report                 # 全体サマリ (= archive live/excluded/deleted 含む)
 *   npm run db:report -- --adult      # 成人フラグ/スコアが立っているもの
 *   npm run db:report -- --excluded   # excluded queue の reason 別 + 直近 30 件
 *   npm run db:report -- --series     # シリーズ一覧（先頭20）
 *   npm run db:report -- --mangaka    # 漫画家一覧（先頭20）
 *   npm run db:report -- --sources    # source 別の件数
 *   npm run db:report -- --top 10     # 巻数トップ N シリーズの edition 内訳
 *   npm run db:report -- --query 'SELECT ...'  # 任意SQL（参照のみ推奨）
 */
import "./_env";
import fs from "node:fs";
import { DB_PATH, openDb } from "./_db";

type Args = {
  showAdult: boolean;
  showSeries: boolean;
  showMangaka: boolean;
  showSources: boolean;
  showExcluded: boolean;
  topN: number | null;
  query: string | null;
};

function parseArgs(argv: string[]): Args {
  const out: Args = {
    showAdult: false,
    showSeries: false,
    showMangaka: false,
    showSources: false,
    showExcluded: false,
    topN: null,
    query: null,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--adult") out.showAdult = true;
    else if (a === "--series") out.showSeries = true;
    else if (a === "--mangaka") out.showMangaka = true;
    else if (a === "--sources") out.showSources = true;
    else if (a === "--excluded") out.showExcluded = true;
    else if (a === "--top" && argv[i + 1]) {
      const n = Number(argv[++i]);
      if (Number.isFinite(n) && n > 0) out.topN = n;
    } else if (a === "--query" && argv[i + 1]) {
      out.query = argv[++i];
    }
  }
  return out;
}

function pad(s: string | number | null | undefined, w: number): string {
  const v = s === null || s === undefined ? "" : String(s);
  if (v.length >= w) return v.slice(0, w);
  return v + " ".repeat(w - v.length);
}

function main() {
  if (!fs.existsSync(DB_PATH)) {
    console.error(`${DB_PATH} がありません。先に \`npm run db:init\` を実行してください。`);
    process.exit(1);
  }

  const args = parseArgs(process.argv.slice(2));
  const db = openDb();

  // 全体サマリは常に表示
  const counts = {
    mangaka: (db.prepare("SELECT COUNT(*) AS n FROM mangaka").get() as { n: number }).n,
    mangaka_adult: (
      db.prepare("SELECT COUNT(*) AS n FROM mangaka WHERE has_adult_credit=1").get() as {
        n: number;
      }
    ).n,
    series: (db.prepare("SELECT COUNT(*) AS n FROM series").get() as { n: number }).n,
    series_adult: (
      db.prepare("SELECT COUNT(*) AS n FROM series WHERE adult_score>0").get() as {
        n: number;
      }
    ).n,
    editions: (db.prepare("SELECT COUNT(*) AS n FROM editions").get() as { n: number }).n,
    volumes: (db.prepare("SELECT COUNT(*) AS n FROM volumes").get() as { n: number }).n,
    sources: (db.prepare("SELECT COUNT(*) AS n FROM sources").get() as { n: number }).n,
    archive_total: (
      db.prepare("SELECT COUNT(*) AS n FROM series_archive").get() as { n: number }
    ).n,
    archive_excluded: (
      db
        .prepare("SELECT COUNT(*) AS n FROM series_archive WHERE current_state='excluded'")
        .get() as { n: number }
    ).n,
    archive_deleted: (
      db
        .prepare("SELECT COUNT(*) AS n FROM series_archive WHERE current_state='deleted'")
        .get() as { n: number }
    ).n,
  };

  console.log("=== summary ===");
  console.log(`  mangaka : ${counts.mangaka} (うち adult-credit: ${counts.mangaka_adult})`);
  console.log(`  series  : ${counts.series} (うち adult_score>0: ${counts.series_adult})`);
  console.log(`  editions: ${counts.editions}`);
  console.log(`  volumes : ${counts.volumes}`);
  console.log(`  sources : ${counts.sources}`);
  console.log(
    `  archive : ${counts.archive_total} ` +
      `(live=${counts.archive_total - counts.archive_excluded - counts.archive_deleted}, ` +
      `excluded=${counts.archive_excluded}, deleted=${counts.archive_deleted})`,
  );

  if (args.showSources) {
    console.log("\n=== sources by name ===");
    const rows = db
      .prepare(
        "SELECT source_name, ref_table, COUNT(*) AS n FROM sources GROUP BY source_name, ref_table ORDER BY source_name, ref_table",
      )
      .all() as { source_name: string; ref_table: string; n: number }[];
    for (const r of rows) {
      console.log(`  ${pad(r.source_name, 16)} ${pad(r.ref_table, 12)} ${r.n}`);
    }
  }

  if (args.showExcluded) {
    console.log("\n=== excluded by reason ===");
    const reasonRows = db
      .prepare(
        `SELECT reason, COUNT(*) AS n
         FROM series_excluded
         GROUP BY reason
         ORDER BY n DESC`,
      )
      .all() as { reason: string; n: number }[];
    if (reasonRows.length === 0) {
      console.log("  (なし — series_excluded 空)");
    } else {
      for (const r of reasonRows) {
        console.log(`  ${pad(r.reason, 22)} ${r.n}`);
      }
      const total = reasonRows.reduce((a, b) => a + b.n, 0);
      console.log(`  ${pad("total", 22)} ${total}`);
    }

    console.log("\n=== recent excluded (top 30 by excluded_at desc) ===");
    const recent = db
      .prepare(
        `SELECT a.id        AS arc_id,
                a.title     AS title,
                a.year_started AS year_started,
                a.year_ended   AS year_ended,
                a.publisher_key AS pub,
                a.adult_score AS score,
                e.reason     AS reason,
                e.signals_json AS signals_json,
                e.excluded_at  AS excluded_at,
                e.excluded_by  AS excluded_by
         FROM series_excluded e
         JOIN series_archive a ON a.id = e.archive_id
         ORDER BY e.excluded_at DESC, a.id DESC
         LIMIT 30`,
      )
      .all() as {
      arc_id: number;
      title: string;
      year_started: number | null;
      year_ended: number | null;
      pub: string | null;
      score: number;
      reason: string;
      signals_json: string | null;
      excluded_at: string;
      excluded_by: string;
    }[];

    if (recent.length === 0) {
      console.log("  (なし)");
    } else {
      console.log(
        `  ${pad("arc#", 6)} ${pad("score", 5)} ${pad("reason", 18)} ${pad("year", 11)} ${pad("by", 14)} title`,
      );
      for (const r of recent) {
        const yr = `${r.year_started ?? "????"}-${r.year_ended ?? ""}`;
        console.log(
          `  ${pad(r.arc_id, 6)} ${pad(r.score, 5)} ${pad(r.reason, 18)} ${pad(yr, 11)} ${pad(r.excluded_by, 14)} ${r.title}`,
        );
      }
    }
  }

  if (args.showAdult) {
    console.log("\n=== adult_publishers (Wikipedia 由来 known list) ===");
    const aps = db
      .prepare("SELECT name, source FROM adult_publishers ORDER BY name")
      .all() as { name: string; source: string }[];
    if (aps.length === 0) {
      console.log("  (なし — fetch:adult-lists 未実行?)");
    } else {
      for (const p of aps) console.log(`  ${p.name}`);
      console.log(`  → ${aps.length} entries`);
    }

    console.log("\n=== adult-credit mangaka (Wikidata hentai genre 経由) ===");
    const ms = db
      .prepare(
        "SELECT qid, name, alt_names FROM mangaka WHERE has_adult_credit=1 ORDER BY name LIMIT 50",
      )
      .all() as { qid: string; name: string; alt_names: string | null }[];
    if (ms.length === 0) {
      console.log("  (なし)");
    } else {
      for (const m of ms) {
        console.log(`  ${pad(m.qid, 12)} ${m.name}${m.alt_names ? ` (alt: ${m.alt_names})` : ""}`);
      }
      if (ms.length === 50) console.log("  ... (truncated to 50)");
    }

    console.log("\n=== adult_score>0 series (with edition imprints) ===");
    const ss = db
      .prepare(
        `SELECT s.id, s.title, s.year_started, s.adult_score, s.publisher_key,
                GROUP_CONCAT(DISTINCT m.name) AS authors
         FROM series s
         LEFT JOIN series_authors sa ON sa.series_id = s.id
         LEFT JOIN mangaka m ON m.id = sa.mangaka_id
         WHERE s.adult_score > 0
         GROUP BY s.id
         ORDER BY s.adult_score DESC, s.title
         LIMIT 50`,
      )
      .all() as {
      id: number;
      title: string;
      year_started: number | null;
      adult_score: number;
      publisher_key: string | null;
      authors: string | null;
    }[];
    if (ss.length === 0) {
      console.log("  (なし)");
    } else {
      const imprintStmt = db.prepare(
        `SELECT DISTINCT imprint FROM editions WHERE series_id = ? AND imprint IS NOT NULL`,
      );
      const sigStmt = db.prepare(
        `SELECT signal, weight FROM adult_signals WHERE series_id = ?`,
      );
      for (const s of ss) {
        const imps = (imprintStmt.all(s.id) as { imprint: string }[])
          .map((r) => r.imprint)
          .join(" / ") || "(no imprint)";
        const sigs = (sigStmt.all(s.id) as { signal: string; weight: number }[])
          .map((r) => `${r.signal}=${r.weight}`)
          .join(", ");
        console.log(
          `  score=${pad(String(s.adult_score), 3)} ${pad(s.title, 30)} ${pad(s.year_started, 5)} ${pad(s.publisher_key, 18)} ${s.authors ?? ""}`,
        );
        console.log(`        imprint: ${imps}`);
        console.log(`        signals: ${sigs || "(none recorded)"}`);
      }
      if (ss.length === 50) console.log("  ... (truncated to 50)");
    }
  }

  if (args.showSeries) {
    console.log("\n=== series (top 20 by id) ===");
    const ss = db
      .prepare(
        `SELECT s.id, s.title, s.year_started, s.year_ended, s.status, s.adult_score,
                s.publisher_key, s.magazine_key,
                COUNT(DISTINCT e.id) AS editions_n,
                COUNT(DISTINCT v.id) AS volumes_n
         FROM series s
         LEFT JOIN editions e ON e.series_id = s.id
         LEFT JOIN volumes v  ON v.edition_id = e.id
         GROUP BY s.id
         ORDER BY s.id
         LIMIT 20`,
      )
      .all() as {
      id: number;
      title: string;
      year_started: number | null;
      year_ended: number | null;
      status: string | null;
      adult_score: number;
      publisher_key: string | null;
      magazine_key: string | null;
      editions_n: number;
      volumes_n: number;
    }[];
    for (const s of ss) {
      const meta = `${s.publisher_key ?? "-"}/${s.magazine_key ?? "-"}`;
      console.log(
        `  #${pad(s.id, 4)} ${pad(s.title, 28)} ${pad(s.year_started, 5)}-${pad(s.year_ended ?? "", 4)} ed=${s.editions_n} vol=${s.volumes_n} ${pad(meta, 35)}${s.adult_score ? ` adult=${s.adult_score}` : ""}`,
      );
    }

    // 集計: publisher_key / magazine_key の埋まり率
    const meta = db
      .prepare(
        `SELECT
           COUNT(*) AS total,
           SUM(CASE WHEN publisher_key IS NOT NULL THEN 1 ELSE 0 END) AS pub_filled,
           SUM(CASE WHEN magazine_key IS NOT NULL THEN 1 ELSE 0 END) AS mag_filled
         FROM series`,
      )
      .get() as { total: number; pub_filled: number; mag_filled: number };
    console.log(
      `\n  series.publisher_key filled: ${meta.pub_filled}/${meta.total}`,
    );
    console.log(
      `  series.magazine_key filled : ${meta.mag_filled}/${meta.total}`,
    );
  }

  if (args.showMangaka) {
    console.log("\n=== mangaka (top 20 by id) ===");
    const ms = db
      .prepare(
        `SELECT m.id, m.qid, m.name, m.birth_year, m.death_year, m.has_adult_credit,
                COUNT(DISTINCT sa.series_id) AS series_n
         FROM mangaka m
         LEFT JOIN series_authors sa ON sa.mangaka_id = m.id
         GROUP BY m.id
         ORDER BY m.id
         LIMIT 20`,
      )
      .all() as {
      id: number;
      qid: string;
      name: string;
      birth_year: number | null;
      death_year: number | null;
      has_adult_credit: number;
      series_n: number;
    }[];
    for (const m of ms) {
      console.log(
        `  #${pad(m.id, 5)} ${pad(m.qid, 12)} ${pad(m.name, 22)} ${pad(m.birth_year, 5)}-${pad(m.death_year ?? "", 4)} series=${m.series_n}${m.has_adult_credit ? " [adult]" : ""}`,
      );
    }
  }

  if (args.topN !== null) {
    const N = args.topN;
    console.log(`\n=== top ${N} series (by volume count) — edition breakdown ===`);
    const top = db
      .prepare(
        `SELECT s.id, s.title,
                COUNT(DISTINCT v.id) AS vols
         FROM series s
         LEFT JOIN editions e ON e.series_id = s.id
         LEFT JOIN volumes  v ON v.edition_id = e.id
         GROUP BY s.id
         ORDER BY vols DESC, s.id
         LIMIT ?`,
      )
      .all(N) as { id: number; title: string; vols: number }[];

    const breakdownStmt = db.prepare(
      `SELECT e.type, e.label, e.imprint, e.year_started, e.year_ended,
              COUNT(v.id) AS vols,
              MIN(v.number) AS min_no,
              MAX(v.number) AS max_no
       FROM editions e
       LEFT JOIN volumes v ON v.edition_id = e.id
       WHERE e.series_id = ?
       GROUP BY e.id
       ORDER BY e.year_started, e.type`,
    );
    const dupStmt = db.prepare(
      `SELECT v.number, COUNT(*) AS dups
       FROM editions e
       JOIN volumes v ON v.edition_id = e.id
       WHERE e.series_id = ?
       GROUP BY v.number
       HAVING COUNT(*) > 1
       ORDER BY v.number
       LIMIT 8`,
    );

    for (const s of top) {
      console.log(`\n  #${s.id}  ${s.title}  (total vols=${s.vols})`);
      const eds = breakdownStmt.all(s.id) as {
        type: string;
        label: string;
        imprint: string | null;
        year_started: number | null;
        year_ended: number | null;
        vols: number;
        min_no: number | null;
        max_no: number | null;
      }[];
      for (const e of eds) {
        console.log(
          `    ${pad(e.type, 12)} ${pad(e.label, 16)} ${pad(e.year_started, 5)}-${pad(e.year_ended ?? "", 4)} vols=${pad(String(e.vols), 4)} no=${e.min_no ?? "?"}..${e.max_no ?? "?"} ${e.imprint ?? ""}`,
        );
      }
      const dups = dupStmt.all(s.id) as { number: number; dups: number }[];
      if (dups.length > 0) {
        const summary = dups
          .map((d) => `vol${d.number}×${d.dups}`)
          .join(", ");
        console.log(`    [duplicate vol numbers across editions] ${summary}${dups.length === 8 ? " ..." : ""}`);
      }
    }
  }

  if (args.query) {
    console.log(`\n=== custom query ===\n  ${args.query}`);
    const rows = db.prepare(args.query).all() as Record<string, unknown>[];
    console.log(`  → ${rows.length} rows`);
    for (const r of rows.slice(0, 50)) {
      console.log("  " + JSON.stringify(r));
    }
    if (rows.length > 50) console.log(`  ... (${rows.length - 50} more)`);
  }

  db.close();
}

main();

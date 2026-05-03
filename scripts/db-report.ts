/**
 * SQLite DB の中身をテキスト形式で表示する診断ツール。
 * 主な用途は「成人判定で弾かれるはずのレコード」の目視確認。
 *
 *   npm run db:report                 # 全体サマリ
 *   npm run db:report -- --adult      # 成人フラグ/スコアが立っているもの
 *   npm run db:report -- --series     # シリーズ一覧（先頭20）
 *   npm run db:report -- --mangaka    # 漫画家一覧（先頭20）
 *   npm run db:report -- --sources    # source 別の件数
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
  query: string | null;
};

function parseArgs(argv: string[]): Args {
  const out: Args = {
    showAdult: false,
    showSeries: false,
    showMangaka: false,
    showSources: false,
    query: null,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--adult") out.showAdult = true;
    else if (a === "--series") out.showSeries = true;
    else if (a === "--mangaka") out.showMangaka = true;
    else if (a === "--sources") out.showSources = true;
    else if (a === "--query" && argv[i + 1]) {
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
  };

  console.log("=== summary ===");
  console.log(`  mangaka : ${counts.mangaka} (うち adult-credit: ${counts.mangaka_adult})`);
  console.log(`  series  : ${counts.series} (うち adult_score>0: ${counts.series_adult})`);
  console.log(`  editions: ${counts.editions}`);
  console.log(`  volumes : ${counts.volumes}`);
  console.log(`  sources : ${counts.sources}`);

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

  if (args.showAdult) {
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

    console.log("\n=== adult_score>0 series ===");
    const ss = db
      .prepare(
        `SELECT s.title, s.year_started, s.adult_score, s.publisher_key, GROUP_CONCAT(m.name, ' / ') AS authors
         FROM series s
         LEFT JOIN series_authors sa ON sa.series_id = s.id
         LEFT JOIN mangaka m ON m.id = sa.mangaka_id
         WHERE s.adult_score > 0
         GROUP BY s.id
         ORDER BY s.adult_score DESC, s.title
         LIMIT 50`,
      )
      .all() as {
      title: string;
      year_started: number | null;
      adult_score: number;
      publisher_key: string | null;
      authors: string | null;
    }[];
    if (ss.length === 0) {
      console.log("  (なし)");
    } else {
      for (const s of ss) {
        console.log(
          `  score=${pad(String(s.adult_score), 3)} ${pad(s.title, 30)} ${pad(s.year_started, 5)} ${pad(s.publisher_key, 18)} ${s.authors ?? ""}`,
        );
      }
      if (ss.length === 50) console.log("  ... (truncated to 50)");
    }
  }

  if (args.showSeries) {
    console.log("\n=== series (top 20 by id) ===");
    const ss = db
      .prepare(
        `SELECT s.id, s.title, s.year_started, s.year_ended, s.status, s.adult_score,
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
      editions_n: number;
      volumes_n: number;
    }[];
    for (const s of ss) {
      console.log(
        `  #${pad(s.id, 4)} ${pad(s.title, 28)} ${pad(s.year_started, 5)}-${pad(s.year_ended ?? "", 4)} ed=${s.editions_n} vol=${s.volumes_n}${s.adult_score ? ` adult=${s.adult_score}` : ""}`,
      );
    }
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

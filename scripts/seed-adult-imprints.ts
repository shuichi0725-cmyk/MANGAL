/**
 * Tier 2 Phase 2: data/seeds/adult-imprints.yml を読んで adult_imprints テーブルへ INSERT。
 *
 *   npm run seed:adult-imprints                # 既存行があれば REPLACE
 *   npm run seed:adult-imprints -- --refresh   # テーブルを TRUNCATE して再投入
 *
 * 投入対象:
 *   - yaml の `imprints` セクション (NFKC 正規化済 imprint 名 + publisher + count)
 * 投入しない:
 *   - `distribution_channels`: imprint は adult だが publisher が配信プラットフォーム
 *     のエントリ。 当面 signal を発火させるかは保留 (false-positive リスク評価中)。
 *   - `ambiguous`: 同名 imprint × 異 publisher (mainstream/adult collision)。
 */
import "./_env";
import path from "node:path";
import { openDb, recordSource, tx } from "./_db";
import { loadAdultImprintsFile } from "../lib/adult-imprints";

const YAML_PATH = path.join(process.cwd(), "data", "seeds", "adult-imprints.yml");

type Args = { refresh: boolean };

function parseArgs(argv: string[]): Args {
  return { refresh: argv.includes("--refresh") };
}

function main(): void {
  const args = parseArgs(process.argv.slice(2));
  const file = loadAdultImprintsFile(YAML_PATH);
  console.log(
    `[seed:adult-imprints] yaml schema=${file.schema_version} imprints=${file.imprints.length}`,
  );
  if (file.ambiguous && file.ambiguous.length > 0) {
    console.log(
      `[seed:adult-imprints] ambiguous=${file.ambiguous.length} (skip — false-positive 防止)`,
    );
  }
  if (file.distribution_channels && file.distribution_channels.length > 0) {
    console.log(
      `[seed:adult-imprints] distribution_channels=${file.distribution_channels.length} (skip — 現在は投入しない)`,
    );
  }
  if (file.false_positives && file.false_positives.length > 0) {
    console.log(
      `[seed:adult-imprints] false_positives=${file.false_positives.length} (skip — probe で FP rate >=50% と判明)`,
    );
  }

  const db = openDb();
  if (args.refresh) {
    db.exec("DELETE FROM adult_imprints;");
    console.log("[seed:adult-imprints] cleared adult_imprints table");
  }

  const ins = db.prepare(
    `INSERT OR REPLACE INTO adult_imprints (imprint, publisher, count, source) VALUES (?, ?, ?, ?)`,
  );
  let n = 0;
  tx(db, () => {
    for (const e of file.imprints) {
      ins.run(e.imprint, e.publisher, e.count, "manual_seed");
      n++;
    }
    recordSource(db, "adult_imprints_yaml", "adult_imprints", "all", {
      count: file.imprints.length,
      schema_version: file.schema_version,
    });
  });

  console.log(`[seed:adult-imprints] inserted ${n} rows`);
  db.close();
}

main();

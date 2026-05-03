/**
 * 空 (またはスキーマのみ) の SQLite DB を `.cache/db.sqlite` に作る。
 *
 *   npm run db:init                  # 既存があれば追加だけして残す
 *   npm run db:init -- --reset       # 既存ファイルを削除して新規作成
 *
 * Phase 0 のスキャフォルド用。実データ投入は Phase 1 以降のフェッチスクリプトが行う。
 */
import "./_env";
import fs from "node:fs";
import { DB_PATH, openDb } from "./_db";

function parseArgs(argv: string[]): { reset: boolean } {
  return { reset: argv.includes("--reset") };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));

  const existed = fs.existsSync(DB_PATH);
  if (args.reset && existed) {
    fs.rmSync(DB_PATH, { force: true });
    // SQLite WAL のサイドカーファイルも消しておく
    for (const ext of ["-wal", "-shm"]) {
      const sidecar = `${DB_PATH}${ext}`;
      if (fs.existsSync(sidecar)) fs.rmSync(sidecar, { force: true });
    }
    console.log(`[reset] removed existing ${DB_PATH}`);
  }

  const db = openDb();
  const tables = (
    db.prepare("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").all() as {
      name: string;
    }[]
  ).map((r) => r.name);

  console.log(`[ok] DB ready at ${DB_PATH}`);
  console.log(`[ok] tables: ${tables.join(", ")}`);

  if (!existed) {
    console.log(
      "[hint] 続いて Phase 1 のフェッチスクリプト（NDL/Wikidata）でデータを投入する。",
    );
  }

  db.close();
}

main().catch((err) => {
  console.error("[fatal]", err);
  process.exit(1);
});

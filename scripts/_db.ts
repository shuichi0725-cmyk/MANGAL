/**
 * SQLite (better-sqlite3) ハンドリングの共通ヘルパ。
 * 各 fetch スクリプトの先頭で `import { openDb } from "./_db"` して使う。
 *
 * DB ファイル位置: `.cache/db.sqlite`（gitignore 済み）
 * スキーマ定義: `db/schema.sql`
 *
 * better-sqlite3 は同期 API。WAL モードで複数スクリプト並列実行に備える。
 */
import fs from "node:fs";
import path from "node:path";
import Database from "better-sqlite3";

export const DB_PATH = path.join(process.cwd(), ".cache", "db.sqlite");
export const SCHEMA_PATH = path.join(process.cwd(), "db", "schema.sql");

export type DB = Database.Database;

/**
 * DB を開く。スキーマ未適用の場合は schema.sql を流す。
 * 親ディレクトリが無ければ作る。
 */
export function openDb(filePath: string = DB_PATH): DB {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const db = new Database(filePath);
  db.pragma("journal_mode = WAL");
  db.pragma("foreign_keys = ON");
  applySchemaIfNeeded(db);
  return db;
}

/**
 * 「mangaka テーブルが無ければ schema.sql 全部を流す」というシンプル判定。
 * IF NOT EXISTS が schema.sql 側に書いてあるので二重実行しても安全。
 */
function applySchemaIfNeeded(db: DB): void {
  const row = db
    .prepare(
      "SELECT name FROM sqlite_master WHERE type='table' AND name='mangaka'",
    )
    .get();
  if (row) return;
  if (!fs.existsSync(SCHEMA_PATH)) {
    throw new Error(`schema not found at ${SCHEMA_PATH}`);
  }
  const sql = fs.readFileSync(SCHEMA_PATH, "utf8");
  db.exec(sql);
}

/**
 * 任意の write 操作をトランザクションで包む薄いラッパ。
 * better-sqlite3 の transaction() は同期関数を要求する。
 */
export function tx<T>(db: DB, fn: () => T): T {
  return db.transaction(fn)();
}

/**
 * provenance を 1 行記録するヘルパ。
 *   recordSource(db, "ndl", "volumes", isbn13, rawJson)
 */
export function recordSource(
  db: DB,
  source: string,
  refTable: string,
  refId: string,
  rawJson?: unknown,
): void {
  db.prepare(
    `INSERT OR REPLACE INTO sources (source_name, ref_table, ref_id, fetched_at, raw_json)
     VALUES (?, ?, ?, ?, ?)`,
  ).run(
    source,
    refTable,
    refId,
    new Date().toISOString(),
    rawJson === undefined ? null : JSON.stringify(rawJson),
  );
}

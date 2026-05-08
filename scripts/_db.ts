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
  // L2: 大規模投入を見越して PRAGMA を調整。
  //  - WAL は同時参照に強いが書き込みは依然シリアライズ。
  //  - synchronous=NORMAL は WAL モードでは FULL より速く、十分に安全
  //    （クラッシュ時にコミット済みトランザクションは保持される）。
  //  - cache_size は負値で KiB 指定（-65536 = 64MB）。
  //  - temp_store=MEMORY で一時テーブル/インデックスを RAM に。
  //  - mmap_size はファイル全体を mmap して I/O を減らす。
  db.pragma("journal_mode = WAL");
  db.pragma("synchronous = NORMAL");
  db.pragma("cache_size = -65536");
  db.pragma("temp_store = MEMORY");
  db.pragma("mmap_size = 268435456"); // 256MB
  db.pragma("foreign_keys = ON");
  applySchemaIfNeeded(db);
  return db;
}

/**
 * schema.sql を常に exec する。 全ての CREATE/INSERT が IF NOT EXISTS / OR IGNORE
 * で書かれている前提なので、 既存 DB に対して新テーブル/新 INDEX だけが追加される。
 * これにより schema_version が上がった時の追従 (= v6 → v7 のテーブル追加等) が
 * `npm run db:init` だけで完了する。
 *
 * NOTE: 将来 ALTER TABLE 等の非 idempotent な migration が必要になったら、
 * meta.schema_version を見て分岐する仕組みに切り替える。
 */
function applySchemaIfNeeded(db: DB): void {
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

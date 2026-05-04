/**
 * data/publishers.yml と data/magazines.yml を SQLite の publishers/magazines
 * テーブルにミラーする。NDL/Rakuten から取り込んだ series.publisher_key /
 * magazine_key の整合性を SQL FK で守るため。
 *
 * source-of-truth は YAML 側。SQLite 側はあくまで最新スナップショットの
 * 写しで、YAML 更新後に再実行して同期する。
 *
 *   npm run db:import:masters
 */
import "./_env";
import fs from "node:fs";
import path from "node:path";
import YAML from "yaml";
import { openDb, recordSource, tx } from "./_db";

const PUBLISHERS_PATH = path.join(process.cwd(), "data", "publishers.yml");
const MAGAZINES_PATH = path.join(process.cwd(), "data", "magazines.yml");

type PublisherEntry = { name: string };
type MagazineEntry = { name: string; publisher: string; demographic: string };

function readMaster<T>(filePath: string): Record<string, T> {
  if (!fs.existsSync(filePath)) {
    throw new Error(`master not found: ${filePath}`);
  }
  return YAML.parse(fs.readFileSync(filePath, "utf8")) as Record<string, T>;
}

function main() {
  const pubs = readMaster<PublisherEntry>(PUBLISHERS_PATH);
  const mags = readMaster<MagazineEntry>(MAGAZINES_PATH);

  const db = openDb();

  const upsertPub = db.prepare(
    `INSERT INTO publishers (key, name) VALUES (?, ?)
     ON CONFLICT(key) DO UPDATE SET name = excluded.name`,
  );
  const upsertMag = db.prepare(
    `INSERT INTO magazines (key, name, publisher, demographic) VALUES (?, ?, ?, ?)
     ON CONFLICT(key) DO UPDATE SET
       name        = excluded.name,
       publisher   = excluded.publisher,
       demographic = excluded.demographic`,
  );

  let nPub = 0;
  let nMag = 0;
  tx(db, () => {
    for (const [key, val] of Object.entries(pubs)) {
      upsertPub.run(key, val.name);
      recordSource(db, "yaml_publishers", "publishers", key);
      nPub++;
    }
    for (const [key, val] of Object.entries(mags)) {
      // FK 制約のため publisher の key が存在することを先に確認
      const pubExists = db
        .prepare("SELECT 1 FROM publishers WHERE key = ?")
        .get(val.publisher);
      if (!pubExists) {
        console.warn(
          `  [skip] magazine ${key}: publisher='${val.publisher}' が publishers に未登録`,
        );
        continue;
      }
      upsertMag.run(key, val.name, val.publisher, val.demographic);
      recordSource(db, "yaml_magazines", "magazines", key);
      nMag++;
    }
  });

  console.log(`[import-masters] publishers: ${nPub} / magazines: ${nMag}`);
  db.close();
}

main();

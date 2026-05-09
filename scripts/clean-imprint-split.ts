/**
 * 一回限り: 旧 fetch-madb (= splitMadbLiteral 適用前) で投入された
 * `editions.imprint` の 「漢字 ∥ カナ」 文字列を漢字部分だけに刈り込む。
 *
 * splitMadbLiteral fix (lib/madb-jsonld.ts) は extractRecord の publisher/brand
 * に作用するが、 既存 editions.imprint は upsert の COALESCE 仕様で上書きされない。
 * 1 回手動で掃除する。
 */
import { openDb, tx } from "/home/user/MANGAL/scripts/_db";
import { splitMadbLiteral } from "/home/user/MANGAL/lib/madb-jsonld";

const db = openDb();

const dirty = db.prepare(
  `SELECT id, imprint FROM editions WHERE imprint LIKE '%∥%'`,
).all() as { id: number; imprint: string }[];

console.log(`[clean] dirty editions.imprint rows: ${dirty.length}`);
let updated = 0, unchanged = 0;
const upd = db.prepare(`UPDATE editions SET imprint = ? WHERE id = ?`);
tx(db, () => {
  for (const r of dirty) {
    const cleaned = splitMadbLiteral(r.imprint);
    if (cleaned !== r.imprint) {
      upd.run(cleaned || null, r.id);
      updated++;
    } else {
      unchanged++;
    }
  }
});
console.log(`[clean] updated=${updated}, unchanged=${unchanged}`);

const remaining = (db.prepare(
  `SELECT COUNT(*) AS c FROM editions WHERE imprint LIKE '%∥%'`,
).get() as { c: number }).c;
console.log(`[verify] editions still with ∥: ${remaining}`);
db.close();

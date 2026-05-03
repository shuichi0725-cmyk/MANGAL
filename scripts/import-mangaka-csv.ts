/**
 * data/seed/mangaka.csv（fetch-mangaka.ts の出力）を SQLite の mangaka テーブルに
 * upsert する。NDL/Wikidata からのフェッチ前に実行しておく前提。
 *
 *   npm run db:import:mangaka                 # 全件
 *   npm run db:import:mangaka -- --limit 100  # テスト用
 */
import "./_env";
import fs from "node:fs";
import path from "node:path";
import { openDb, recordSource, tx } from "./_db";

const CSV_PATH = path.join(process.cwd(), "data", "seed", "mangaka.csv");

type CsvRow = {
  qid: string;
  name: string;
  birth_year: string;
  death_year: string;
  alt_names: string;
  has_adult_credit: string;
};

function parseCsv(text: string): CsvRow[] {
  const rows: string[][] = [];
  let cur: string[] = [];
  let field = "";
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else inQuotes = false;
      } else field += ch;
    } else if (ch === '"') inQuotes = true;
    else if (ch === ",") {
      cur.push(field);
      field = "";
    } else if (ch === "\n") {
      cur.push(field);
      rows.push(cur);
      cur = [];
      field = "";
    } else if (ch === "\r") {
      // skip
    } else field += ch;
  }
  if (field.length > 0 || cur.length > 0) {
    cur.push(field);
    rows.push(cur);
  }
  if (rows.length === 0) return [];
  const header = rows[0];
  const idx = (k: string) => header.indexOf(k);
  const out: CsvRow[] = [];
  for (let r = 1; r < rows.length; r++) {
    const row = rows[r];
    if (row.length === 1 && row[0] === "") continue;
    out.push({
      qid: row[idx("qid")] ?? "",
      name: row[idx("name")] ?? "",
      birth_year: row[idx("birth_year")] ?? "",
      death_year: row[idx("death_year")] ?? "",
      alt_names: row[idx("alt_names")] ?? "",
      has_adult_credit: row[idx("has_adult_credit")] ?? "false",
    });
  }
  return out;
}

function parseArgs(argv: string[]): { limit: number | null } {
  const out = { limit: null as number | null };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--limit" && argv[i + 1]) {
      out.limit = Number(argv[++i]);
    }
  }
  return out;
}

function main() {
  if (!fs.existsSync(CSV_PATH)) {
    console.error(`${CSV_PATH} がありません。先に \`npm run fetch:mangaka\` を実行してください。`);
    process.exit(1);
  }
  const args = parseArgs(process.argv.slice(2));
  const csv = fs.readFileSync(CSV_PATH, "utf8");
  let rows = parseCsv(csv);
  if (args.limit !== null) rows = rows.slice(0, args.limit);
  console.log(`[import] ${rows.length} rows from ${CSV_PATH}`);

  const db = openDb();

  const upsert = db.prepare(
    `INSERT INTO mangaka (qid, name, birth_year, death_year, alt_names, has_adult_credit)
     VALUES (@qid, @name, @birth_year, @death_year, @alt_names, @has_adult_credit)
     ON CONFLICT(qid) DO UPDATE SET
       name=excluded.name,
       birth_year=excluded.birth_year,
       death_year=excluded.death_year,
       alt_names=excluded.alt_names,
       has_adult_credit=excluded.has_adult_credit`,
  );

  const toInt = (s: string): number | null => {
    if (!s) return null;
    const n = Number(s);
    return Number.isFinite(n) ? n : null;
  };

  let n = 0;
  let nAdult = 0;
  tx(db, () => {
    for (const r of rows) {
      if (!r.qid || !r.name) continue;
      const adult = r.has_adult_credit === "true" ? 1 : 0;
      upsert.run({
        qid: r.qid,
        name: r.name,
        birth_year: toInt(r.birth_year),
        death_year: toInt(r.death_year),
        alt_names: r.alt_names || null,
        has_adult_credit: adult,
      });
      recordSource(db, "mangaka_csv", "mangaka", r.qid);
      n++;
      if (adult) nAdult++;
    }
  });

  console.log(`[import] upserted ${n} mangaka (うち adult-credit: ${nAdult})`);
  db.close();
}

main();

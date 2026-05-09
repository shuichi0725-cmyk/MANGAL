/**
 * verify-coverage.ts — 20 manga seed の coverage 計測ハーネス
 *
 * 目的:
 *   `data/seed/verification-20.tsv` に列挙した 20 件の有名作品それぞれについて、
 *   - source side: `.cache/madb/metadata101.json` を streaming scan して
 *     「タイトル部分一致 AND 著者名一致 のいずれか」 で record を集め、
 *     distinct ISBN-13 数を真値とする
 *   - DB side: `series.title` に部分一致する series の全 editions の volumes に
 *     ぶら下がる distinct ISBN-13 数を取る
 *   - coverage = (DB ∩ source) / source を %表示
 *   サンプルとして、 source にあって DB に無い ISBN を 5 件まで列挙
 *
 * 使い方:
 *   npx tsx scripts/verify-coverage.ts \
 *     --seed data/seed/verification-20.tsv \
 *     --jsonld-path .cache/madb/metadata101.json
 *
 * このスクリプトは read-only。 DB / metadata101.json には一切書き込まない。
 */
import "./_env";
import fs from "node:fs";
import chain from "stream-chain";
import sjParser from "stream-json";
import streamArray from "stream-json/streamers/stream-array.js";
import pick from "stream-json/filters/pick.js";
import { openDb } from "./_db";
import {
  extractRecord,
  type MadbJsonLdRecord,
} from "../lib/madb-jsonld";
import { normalizeIsbn13 } from "../lib/edition";

type SeedRow = {
  title: string;
  authors: string[]; // primary, secondary (なければ 1 件)
  primaryQid: string;
  secondaryQid: string;
  expectedVols: number;
  tags: string[];
};

function parseSeed(path: string): SeedRow[] {
  const raw = fs.readFileSync(path, "utf8");
  const rows: SeedRow[] = [];
  for (const line of raw.split(/\r?\n/)) {
    const t = line.trim();
    if (!t || t.startsWith("#")) continue;
    if (t.startsWith("title_canonical\t")) continue; // header
    const cols = line.split("\t");
    if (cols.length < 6) continue;
    const [title, authorsJp, primaryQid, secondaryQid, expectedVols, tags] = cols;
    rows.push({
      title: title.trim(),
      authors: authorsJp.split("|").map((s) => s.trim()).filter(Boolean),
      primaryQid: primaryQid.trim(),
      secondaryQid: secondaryQid.trim(),
      expectedVols: Number(expectedVols),
      tags: tags.split(",").map((s) => s.trim()).filter(Boolean),
    });
  }
  return rows;
}

type SourceMatch = {
  isbns: Set<string>;
  byImprint: Map<string, number>;
  sampleVolStrings: Set<string>;
};

async function scanSource(
  jsonldPath: string,
  seeds: SeedRow[],
): Promise<Map<number, SourceMatch>> {
  const result = new Map<number, SourceMatch>();
  for (let i = 0; i < seeds.length; i++) {
    result.set(i, {
      isbns: new Set(),
      byImprint: new Map(),
      sampleVolStrings: new Set(),
    });
  }

  // タイトル部分一致用: 軽い正規化 (= NFKC + 半角化、 大文字小文字無視)。
  // 著者一致用: 名前 substring (= 「花咲アキラ」 等の漢字名)。
  const seedNormTitles = seeds.map((s) => s.title.normalize("NFKC").toLowerCase());
  const seedAuthors = seeds.map((s) => s.authors);

  const stream = chain([
    fs.createReadStream(jsonldPath),
    sjParser(),
    pick({ filter: /^@graph$/ }),
    streamArray(),
  ]);

  let total = 0;
  for await (const item of stream) {
    total++;
    if (total % 100000 === 0) {
      console.log(`  [scan] ${total} records processed`);
    }
    const value = (item as { key: number; value: MadbJsonLdRecord }).value;
    const rec = extractRecord(value);
    if (!rec) continue;
    const isbn13 = normalizeIsbn13(rec.isbn);
    if (!isbn13) continue;
    const titleNorm = (rec.title || "").normalize("NFKC").toLowerCase();
    if (!titleNorm) continue;

    for (let i = 0; i < seeds.length; i++) {
      const seedTitle = seedNormTitles[i];
      // タイトル部分一致 AND (著者一覧に seed の著者いずれかが含まれる)
      if (!titleNorm.includes(seedTitle)) continue;
      const authorsList = rec.authors;
      const hasAuthor = seedAuthors[i].some((a) =>
        authorsList.some((ra) => ra.includes(a)),
      );
      if (!hasAuthor) continue;
      const m = result.get(i)!;
      m.isbns.add(isbn13);
      const imp = rec.brand || "(no imprint)";
      m.byImprint.set(imp, (m.byImprint.get(imp) || 0) + 1);
      if (m.sampleVolStrings.size < 6) {
        m.sampleVolStrings.add(rec.volumeNumber || "(no vol)");
      }
    }
  }
  console.log(`  [scan] total ${total} records scanned`);
  return result;
}

type DbMatch = {
  seriesIds: number[];
  seriesTitles: string[];
  isbns: Set<string>;
  byEdition: { type: string; imprint: string | null; n: number }[];
};

function queryDb(seeds: SeedRow[]): Map<number, DbMatch> {
  const db = openDb();
  const result = new Map<number, DbMatch>();
  for (let i = 0; i < seeds.length; i++) {
    const seed = seeds[i];
    // 部分一致 title (= series.title に seed.title が含まれる)。
    const series = db
      .prepare(`SELECT id, title FROM series WHERE title LIKE ?`)
      .all(`%${seed.title}%`) as { id: number; title: string }[];

    const isbns = new Set<string>();
    const byEdition: { type: string; imprint: string | null; n: number }[] = [];
    for (const s of series) {
      const eds = db
        .prepare(
          `SELECT id, type, imprint FROM editions WHERE series_id = ?`,
        )
        .all(s.id) as { id: number; type: string; imprint: string | null }[];
      for (const e of eds) {
        const vols = db
          .prepare(
            `SELECT isbn13 FROM volumes WHERE edition_id = ? AND isbn13 IS NOT NULL`,
          )
          .all(e.id) as { isbn13: string }[];
        for (const v of vols) isbns.add(v.isbn13);
        byEdition.push({ type: e.type, imprint: e.imprint, n: vols.length });
      }
    }
    result.set(i, {
      seriesIds: series.map((s) => s.id),
      seriesTitles: series.map((s) => s.title),
      isbns,
      byEdition,
    });
  }
  db.close();
  return result;
}

function parseArgs(argv: string[]) {
  const out: { seed: string; jsonldPath: string } = {
    seed: "data/seed/verification-20.tsv",
    jsonldPath: ".cache/madb/metadata101.json",
  };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--seed") out.seed = argv[++i];
    else if (argv[i] === "--jsonld-path") out.jsonldPath = argv[++i];
  }
  return out;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const seeds = parseSeed(args.seed);
  console.log(`Loaded ${seeds.length} seed manga from ${args.seed}`);

  console.log(`\n[1/2] Streaming source: ${args.jsonldPath}`);
  const sourceStart = Date.now();
  const source = await scanSource(args.jsonldPath, seeds);
  console.log(`  done in ${((Date.now() - sourceStart) / 1000).toFixed(1)}s`);

  console.log(`\n[2/2] Querying DB`);
  const dbMatches = queryDb(seeds);

  console.log(`\n=== coverage report ===`);
  console.log(
    `  ${"#".padStart(2)} ${"title".padEnd(22)} ${"src".padStart(4)} ${"db".padStart(4)} ${"hit".padStart(4)} ${"%".padStart(5)}  series_ids`,
  );
  let totalSrc = 0,
    totalHit = 0;
  const failing: number[] = [];
  for (let i = 0; i < seeds.length; i++) {
    const seed = seeds[i];
    const src = source.get(i)!;
    const dbm = dbMatches.get(i)!;
    const intersect = [...src.isbns].filter((x) => dbm.isbns.has(x)).length;
    const cov = src.isbns.size === 0 ? 0 : (100 * intersect) / src.isbns.size;
    totalSrc += src.isbns.size;
    totalHit += intersect;
    if (cov < 95) failing.push(i);
    console.log(
      `  ${String(i + 1).padStart(2)} ${seed.title.padEnd(22)} ${String(src.isbns.size).padStart(4)} ${String(dbm.isbns.size).padStart(4)} ${String(intersect).padStart(4)} ${cov.toFixed(1).padStart(5)}  [${dbm.seriesIds.join(",")}]`,
    );
  }
  const overall = totalSrc === 0 ? 0 : (100 * totalHit) / totalSrc;
  console.log(`\n  TOTAL src=${totalSrc} hit=${totalHit} coverage=${overall.toFixed(1)}%`);

  if (failing.length > 0) {
    console.log(`\n=== detail for failing series (cov < 95%) ===`);
    for (const i of failing) {
      const seed = seeds[i];
      const src = source.get(i)!;
      const dbm = dbMatches.get(i)!;
      const missing = [...src.isbns].filter((x) => !dbm.isbns.has(x));
      console.log(`\n  [${i + 1}] ${seed.title} (authors=${seed.authors.join(",")})`);
      console.log(`    src ISBNs=${src.isbns.size}, db ISBNs=${dbm.isbns.size}, missing=${missing.length}`);
      console.log(`    src imprints (top 5):`);
      const imprintsSorted = [...src.byImprint.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
      for (const [imp, n] of imprintsSorted) console.log(`      ${n}\t${imp}`);
      console.log(`    db editions:`);
      for (const e of dbm.byEdition) console.log(`      ${e.type}\t${e.imprint}\t${e.n} ISBNs`);
      console.log(`    sample missing ISBNs:`);
      for (const m of missing.slice(0, 5)) console.log(`      ${m}`);
      console.log(`    sample vol strings (src): ${[...src.sampleVolStrings].slice(0, 6).join(" | ")}`);
    }
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

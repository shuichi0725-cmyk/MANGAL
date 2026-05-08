/**
 * メディア芸術データベース (MADB) 公式 JSON-LD (= GitHub release
 * `metadata101_json.zip` を展開した `metadata101.json`) を streaming
 * 読み込みして SQLite に投入する fetcher。
 *
 * 使い方:
 *   npm run fetch:madb -- --jsonld-path .cache/madb/metadata101.json --qid Q11331084
 *   npm run fetch:madb -- --jsonld-path .cache/madb/metadata101.json --name "諫山創"
 *   npm run fetch:madb -- --jsonld-path .cache/madb/metadata101.json --all
 *   npm run fetch:madb -- --jsonld-path .cache/madb/metadata101.json --all --limit 50
 *   npm run fetch:madb -- --jsonld-path .cache/madb/metadata101.json --all --include-adult
 *
 * 経緯:
 *   - SPARQL 路線 (= 旧実装) を廃止: rate limit / schema discovery / 完全版
 *     判定の複雑さを回避。
 *   - CSV 路線 (= 5/8 午前の実装) も廃止: 公式 GitHub release は CSV を
 *     提供せず JSON-LD / TTL のみ。 安定 URL のため JSON-LD 採用。
 *   - data source: GitHub `mediaarts-db/dataset` の latest release asset
 *     (= 例 tag `1.2.15`、 `metadata101_json.zip` 47.5MB)。 展開後 627MB
 *     の単一 JSON で `@graph` array に ≈390k records。 stream-json で
 *     1 record ずつ pull。
 *
 * adult filter (= lib/madb-jsonld.ts isAdultMadbRecord、 4 層):
 *   1. schema:contentRating == "成年コミック"   ← MADB 公式 (= 一次)
 *   2. schema:description に "成年コミック" 含む ← rating 漏れ catch
 *   3. schema:brand ∈ adult_imprints              ← Tier 2 シード DB 照合
 *   4. schema:publisher ∈ adult_publishers         ← Tier 1 シード DB 照合
 */
import "./_env";
import fs from "node:fs";
import path from "node:path";
import YAML from "yaml";
// stream-json v2.1.0 は CJS で `export = make` の形。 esModuleInterop で
// default import 可能だが、 サブパスは `.js` 拡張子を明示しないと resolve
// 失敗する (= package.json exports の `./*` パターン由来)。
// stream-chain の `chain()` を使うと .pipe() の型問題を避けられる。
import chain from "stream-chain";
import sjParser from "stream-json";
import streamArray from "stream-json/streamers/stream-array.js";
import pick from "stream-json/filters/pick.js";
import {
  type EditionType,
  EDITION_LABELS,
  baseTitle,
  buildSeriesKey,
  classifyEdition,
  extractVolumeNumber,
  normalizeCreatorName,
  normalizeIsbn13,
  normalizeReleaseDate,
} from "../lib/edition";
import {
  extractRecord,
  isAdultMadbRecord,
  parseVolumeNumber,
  type AdultMatchSignal,
  type MadbJsonLdRecord,
  type MadbRecord,
} from "../lib/madb-jsonld";
import type { Statement as BSStatement } from "better-sqlite3";
import { openDb, recordSource, tx, type DB } from "./_db";

type Stmt = BSStatement<unknown[], unknown>;

type Args = {
  jsonldPath: string | null;
  qid: string | null;
  name: string | null;
  all: boolean;
  limit: number | null;
  includeAdult: boolean;
};

function parseArgs(argv: string[]): Args {
  const out: Args = {
    jsonldPath: null,
    qid: null,
    name: null,
    all: false,
    limit: null,
    includeAdult: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = argv[i + 1];
    if (a === "--jsonld-path" && next) {
      out.jsonldPath = next;
      i++;
    } else if (a === "--qid" && next) {
      out.qid = next;
      i++;
    } else if (a === "--name" && next) {
      out.name = next;
      i++;
    } else if (a === "--all") {
      out.all = true;
    } else if (a === "--limit" && next) {
      out.limit = Number(next);
      i++;
    } else if (a === "--include-adult") {
      out.includeAdult = true;
    }
  }
  return out;
}

/**
 * publishers.yml の name → key 逆引きマップ。
 */
type MasterMaps = {
  publisher: Map<string, string>;
};

let cachedMasters: MasterMaps | null = null;

function getMasters(): MasterMaps {
  if (cachedMasters) return cachedMasters;
  const dataDir = path.join(process.cwd(), "data");
  const pubYaml = YAML.parse(
    fs.readFileSync(path.join(dataDir, "publishers.yml"), "utf8"),
  ) as Record<string, { name: string }>;
  const publisher = new Map<string, string>();
  for (const [k, v] of Object.entries(pubYaml)) {
    publisher.set(v.name.normalize("NFKC"), k);
  }
  cachedMasters = { publisher };
  return cachedMasters;
}

function loadAdultSeeds(db: DB): {
  adultImprints: Set<string>;
  adultPublishers: Set<string>;
} {
  const adultImprints = new Set<string>();
  for (const r of db.prepare("SELECT imprint FROM adult_imprints").all() as {
    imprint: string;
  }[]) {
    adultImprints.add(r.imprint.normalize("NFKC"));
  }
  const adultPublishers = new Set<string>();
  for (const r of db.prepare("SELECT name FROM adult_publishers").all() as {
    name: string;
  }[]) {
    adultPublishers.add(r.name.normalize("NFKC"));
  }
  return { adultImprints, adultPublishers };
}

type AuthorRef = {
  qid: string | null;
  name: string;
  altNames: string[];
  mangakaId: number | null;
};

/** upsertVolume の入力。 旧 SPARQL/CSV 経路と同じシェイプを保つ。 */
type UpsertRec = {
  manifestationUri: string;
  title: string | null;
  creator: string;
  isbn13: string;
  publisher: string | null;
  imprint: string | null;
  /** 「完全版」 等の判定に使う 副題的文字列 (= JSON-LD では schema:alternativeHeadline) */
  editionLabel: string | null;
  datePublished: string | null;
  csvVolumeNumber: number | null;
};

/**
 * MadbRecord (= JSON-LD 抽出後の typed shape) を upsertVolume 入力に変換。
 */
function recordToUpsert(rec: MadbRecord): UpsertRec | null {
  const isbn13 = normalizeIsbn13(rec.isbn);
  if (!isbn13) return null;
  const creator = rec.authors.join(" / ").trim();
  if (!creator) return null;
  return {
    manifestationUri: `https://mediaarts-db.artmuseums.go.jp/id/${rec.madbId}`,
    title: rec.title || null,
    creator,
    isbn13,
    publisher: rec.publisher || null,
    imprint: rec.brand || null,
    editionLabel: rec.subtitle || null,
    datePublished: rec.datePublished || null,
    csvVolumeNumber: parseVolumeNumber(rec.volumeNumber),
  };
}

type VolumeStmts = {
  selectSeries: Stmt;
  insertSeries: Stmt;
  updateSeriesYear: Stmt;
  updateSeriesPublisherKey: Stmt;
  insertSeriesAuthor: Stmt;
  selectEdition: Stmt;
  insertEdition: Stmt;
  updateEditionImprint: Stmt;
  updateEditionYear: Stmt;
  selectVolume: Stmt;
  insertVolume: Stmt;
  updateVolume: Stmt;
};

let cachedStmts: { db: DB; stmts: VolumeStmts } | null = null;

function getStmts(db: DB): VolumeStmts {
  if (cachedStmts && cachedStmts.db === db) return cachedStmts.stmts;
  const stmts: VolumeStmts = {
    selectSeries: db.prepare(
      "SELECT id, year_started, year_ended FROM series WHERE series_key = ?",
    ),
    insertSeries: db.prepare(
      `INSERT INTO series (series_key, title, year_started, year_ended)
       VALUES (?, ?, ?, ?)`,
    ),
    updateSeriesYear: db.prepare(
      `UPDATE series
       SET year_started = ?, year_ended = ?,
           updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
       WHERE id = ?`,
    ),
    updateSeriesPublisherKey: db.prepare(
      `UPDATE series
       SET publisher_key = COALESCE(publisher_key, ?),
           updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
       WHERE id = ?`,
    ),
    insertSeriesAuthor: db.prepare(
      `INSERT OR IGNORE INTO series_authors (series_id, mangaka_id, role)
       VALUES (?, ?, ?)`,
    ),
    selectEdition: db.prepare(
      "SELECT id, year_started, year_ended FROM editions WHERE series_id = ? AND type = ?",
    ),
    insertEdition: db.prepare(
      `INSERT INTO editions (series_id, type, label, imprint, year_started, year_ended)
       VALUES (?, ?, ?, ?, ?, ?)`,
    ),
    updateEditionImprint: db.prepare(
      `UPDATE editions
       SET imprint = COALESCE(imprint, ?),
           updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
       WHERE id = ?`,
    ),
    updateEditionYear: db.prepare(
      `UPDATE editions
       SET year_started = ?, year_ended = ?,
           updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
       WHERE id = ?`,
    ),
    selectVolume: db.prepare(
      "SELECT edition_id FROM volumes WHERE isbn13 = ?",
    ),
    insertVolume: db.prepare(
      `INSERT INTO volumes (edition_id, isbn13, number, is_extra, release_date)
       VALUES (?, ?, ?, ?, ?)`,
    ),
    updateVolume: db.prepare(
      `UPDATE volumes
       SET edition_id   = ?,
           number       = ?,
           is_extra     = ?,
           release_date = COALESCE(?, release_date),
           updated_at   = strftime('%Y-%m-%dT%H:%M:%SZ','now')
       WHERE isbn13 = ?`,
    ),
  };
  cachedStmts = { db, stmts };
  return stmts;
}

/**
 * 1 record を upsert。
 *
 * JSON-LD 由来データの優先順:
 *   - editionType: rec.editionLabel (= schema:alternativeHeadline、 「完全版」
 *     等が入る) を最優先 → fallback で title から classifyEdition
 *   - volumeNumber: rec.csvVolumeNumber (= schema:volumeNumber) → fallback
 *     で title から extractVolumeNumber
 *   - imprint: rec.imprint (= schema:brand)
 *   - publisher_key: rec.publisher (= schema:publisher を publishers.yml で解決)
 */
function upsertVolume(db: DB, author: AuthorRef, rec: UpsertRec): void {
  const titleForKey = rec.title ?? rec.isbn13;
  const seriesKey = buildSeriesKey(titleForKey, {
    qid: author.qid,
    name: author.name,
  });
  const seriesDisplay = baseTitle(titleForKey);

  // editionLabel (= schema:alternativeHeadline) があれば最優先。
  // CSV 路線では 「版表示」 column だったが、 JSON-LD では subtitle に
  // 完全版 / 特装版 等が記録される。 空なら title から classifyEdition。
  const editionInput = rec.editionLabel ?? rec.title ?? "";
  let editionType: EditionType = classifyEdition(editionInput);
  const volumeNumber =
    rec.csvVolumeNumber ?? (rec.title ? extractVolumeNumber(rec.title) : null);
  if (volumeNumber === null && editionType === "standard") {
    editionType = "other";
  }
  const releaseDate = normalizeReleaseDate(rec.datePublished);
  const issuedYear =
    releaseDate && /^\d{4}/.test(releaseDate)
      ? Number(releaseDate.slice(0, 4))
      : null;

  const stmts = getStmts(db);
  const masters = getMasters();
  const publisherKey =
    rec.publisher !== null
      ? (masters.publisher.get(rec.publisher.normalize("NFKC")) ?? null)
      : null;

  const existingSeries = stmts.selectSeries.get(seriesKey) as
    | { id: number; year_started: number | null; year_ended: number | null }
    | undefined;

  let seriesId: number;
  if (existingSeries) {
    seriesId = existingSeries.id;
    if (issuedYear !== null) {
      const newStart =
        existingSeries.year_started === null
          ? issuedYear
          : Math.min(existingSeries.year_started, issuedYear);
      const newEnd =
        existingSeries.year_ended === null
          ? issuedYear
          : Math.max(existingSeries.year_ended, issuedYear);
      if (
        newStart !== existingSeries.year_started ||
        newEnd !== existingSeries.year_ended
      ) {
        stmts.updateSeriesYear.run(newStart, newEnd, seriesId);
      }
    }
  } else {
    const info = stmts.insertSeries.run(
      seriesKey,
      seriesDisplay,
      issuedYear,
      issuedYear,
    );
    seriesId = Number(info.lastInsertRowid);
  }

  if (author.mangakaId !== null) {
    stmts.insertSeriesAuthor.run(seriesId, author.mangakaId, "writer_artist");
  }

  if (publisherKey !== null) {
    stmts.updateSeriesPublisherKey.run(publisherKey, seriesId);
  }

  const existingEdition = stmts.selectEdition.get(seriesId, editionType) as
    | { id: number; year_started: number | null; year_ended: number | null }
    | undefined;

  const imprintForRow = rec.imprint ?? rec.publisher;

  let editionId: number;
  if (existingEdition) {
    editionId = existingEdition.id;
    if (imprintForRow) {
      stmts.updateEditionImprint.run(imprintForRow, editionId);
    }
    if (issuedYear !== null) {
      const newStart =
        existingEdition.year_started === null
          ? issuedYear
          : Math.min(existingEdition.year_started, issuedYear);
      const newEnd =
        existingEdition.year_ended === null
          ? issuedYear
          : Math.max(existingEdition.year_ended, issuedYear);
      if (
        newStart !== existingEdition.year_started ||
        newEnd !== existingEdition.year_ended
      ) {
        stmts.updateEditionYear.run(newStart, newEnd, editionId);
      }
    }
  } else {
    const info = stmts.insertEdition.run(
      seriesId,
      editionType,
      EDITION_LABELS[editionType],
      imprintForRow,
      issuedYear,
      issuedYear,
    );
    editionId = Number(info.lastInsertRowid);
  }

  const numberVal = volumeNumber ?? 1;
  const isExtra = volumeNumber === null ? 1 : 0;
  const existingVolume = stmts.selectVolume.get(rec.isbn13) as
    | { edition_id: number }
    | undefined;
  if (existingVolume) {
    stmts.updateVolume.run(
      editionId,
      numberVal,
      isExtra,
      releaseDate,
      rec.isbn13,
    );
  } else {
    stmts.insertVolume.run(
      editionId,
      rec.isbn13,
      numberVal,
      isExtra,
      releaseDate,
    );
  }

  recordSource(db, "madb", "volumes", rec.isbn13, {
    manifestation: rec.manifestationUri,
    title: rec.title,
    creator: rec.creator,
    publisher: rec.publisher,
    imprint: rec.imprint,
    editionLabel: rec.editionLabel,
    datePublished: rec.datePublished,
  });
}

type ResolvedAuthor = AuthorRef & { display: string };

function resolveAuthors(db: DB, args: Args): ResolvedAuthor[] {
  if (args.qid) {
    const row = db
      .prepare(
        "SELECT id, qid, name, alt_names, has_adult_credit FROM mangaka WHERE qid = ?",
      )
      .get(args.qid) as
      | {
          id: number;
          qid: string;
          name: string;
          alt_names: string | null;
          has_adult_credit: number;
        }
      | undefined;
    if (!row) {
      console.warn(`[warn] qid=${args.qid} not found in DB.mangaka. exit.`);
      return [];
    }
    if (row.has_adult_credit && !args.includeAdult) {
      console.warn(
        `[skip] qid=${args.qid} (= ${row.name}) has has_adult_credit=true. use --include-adult to override.`,
      );
      return [];
    }
    return [
      {
        qid: row.qid,
        name: row.name,
        altNames: (row.alt_names ?? "")
          .split("|")
          .map((s) => s.trim())
          .filter(Boolean),
        mangakaId: row.id,
        display: `${row.name} (${row.qid})`,
      },
    ];
  }
  if (args.name) {
    return [
      {
        qid: null,
        name: args.name,
        altNames: [],
        mangakaId: null,
        display: args.name,
      },
    ];
  }
  if (args.all) {
    let q = "SELECT id, qid, name, alt_names FROM mangaka WHERE qid IS NOT NULL";
    if (!args.includeAdult) {
      q += " AND (has_adult_credit IS NULL OR has_adult_credit = 0)";
    }
    q += " ORDER BY id ASC";
    if (args.limit !== null) q += ` LIMIT ${args.limit}`;
    const rows = db.prepare(q).all() as {
      id: number;
      qid: string;
      name: string;
      alt_names: string | null;
    }[];
    return rows.map((r) => ({
      qid: r.qid,
      name: r.name,
      altNames: (r.alt_names ?? "")
        .split("|")
        .map((s) => s.trim())
        .filter(Boolean),
      mangakaId: r.id,
      display: `${r.name} (${r.qid})`,
    }));
  }
  return [];
}

function buildAuthorIndex(
  authors: ResolvedAuthor[],
): Map<string, ResolvedAuthor[]> {
  const idx = new Map<string, ResolvedAuthor[]>();
  for (const a of authors) {
    const names = [a.name, ...a.altNames];
    for (const n of names) {
      const key = normalizeCreatorName(n);
      if (!key) continue;
      const list = idx.get(key);
      if (list) list.push(a);
      else idx.set(key, [a]);
    }
  }
  return idx;
}

type Stats = {
  totalRecords: number;
  parseErrors: number;
  skippedAdultRating: number;
  skippedAdultDescription: number;
  skippedAdultImprint: number;
  skippedAdultPublisher: number;
  matchedRecords: number;
  upsertedVolumes: number;
  insertedVolumes: number;
  updatedVolumes: number;
  errors: number;
};

function newStats(): Stats {
  return {
    totalRecords: 0,
    parseErrors: 0,
    skippedAdultRating: 0,
    skippedAdultDescription: 0,
    skippedAdultImprint: 0,
    skippedAdultPublisher: 0,
    matchedRecords: 0,
    upsertedVolumes: 0,
    insertedVolumes: 0,
    updatedVolumes: 0,
    errors: 0,
  };
}

function bumpAdultStat(stats: Stats, signal: AdultMatchSignal): void {
  if (signal === "rating") stats.skippedAdultRating++;
  else if (signal === "description") stats.skippedAdultDescription++;
  else if (signal === "imprint") stats.skippedAdultImprint++;
  else if (signal === "publisher") stats.skippedAdultPublisher++;
}

/**
 * stream-json で `@graph` array を pull しながら 1 record ずつ:
 *   1. extractRecord で typed shape に変換
 *   2. adult filter 4 層
 *   3. 作者 index で mangaka 紐付け (= 共著は 1:N)
 *   4. matched record をキューに積む (= 全行スキャン後に 1 transaction で投入)
 *
 * メモリ: queued 配列のみ蓄積 (= 397k record × 一部 mangaka match なので
 * 通常 数十 MB で収まる)。
 */
async function processJsonld(
  db: DB,
  jsonldPath: string,
  authorIndex: Map<string, ResolvedAuthor[]>,
  adultSeeds: { adultImprints: Set<string>; adultPublishers: Set<string> },
  args: Args,
): Promise<Stats> {
  const stats = newStats();
  if (!fs.existsSync(jsonldPath)) {
    throw new Error(`json-ld not found: ${jsonldPath}`);
  }

  const queued: { author: ResolvedAuthor; rec: UpsertRec }[] = [];

  // stream-json の filter は dotted path 表記または RegExp。 `@graph` は
  // `@` 記号入りなので RegExp で表す。 stream-chain の chain() で typing
  // 整合 (= .pipe() で組むと Flushable 型と Node Stream 型の差異で TS error)。
  const stream = chain([
    fs.createReadStream(jsonldPath),
    sjParser(),
    pick({ filter: /^@graph$/ }),
    streamArray(),
  ]);

  let progressCounter = 0;
  for await (const item of stream) {
    const value = (item as { key: number; value: MadbJsonLdRecord }).value;
    stats.totalRecords++;
    progressCounter++;
    if (progressCounter % 50000 === 0) {
      console.log(
        `[progress] processed=${progressCounter}, matched=${stats.matchedRecords}, queued=${queued.length}`,
      );
    }

    const rec = extractRecord(value);
    if (!rec) {
      stats.parseErrors++;
      continue;
    }

    if (!args.includeAdult) {
      const adultSig = isAdultMadbRecord(
        rec,
        adultSeeds.adultImprints,
        adultSeeds.adultPublishers,
      );
      if (adultSig) {
        bumpAdultStat(stats, adultSig);
        continue;
      }
    }

    const matched: ResolvedAuthor[] = [];
    for (const a of rec.authors) {
      const key = normalizeCreatorName(a);
      if (!key) continue;
      const hits = authorIndex.get(key);
      if (hits) matched.push(...hits);
    }
    if (matched.length === 0) continue;
    stats.matchedRecords++;

    const up = recordToUpsert(rec);
    if (!up) {
      stats.parseErrors++;
      continue;
    }

    const seen = new Set<number | string>();
    for (const a of matched) {
      const key = a.mangakaId ?? `name:${a.name}`;
      if (seen.has(key)) continue;
      seen.add(key);
      queued.push({ author: a, rec: up });
    }
  }

  console.log(
    `[stream] read ${stats.totalRecords} records, matched=${stats.matchedRecords}, queued=${queued.length}`,
  );

  tx(db, () => {
    const stmts = getStmts(db);
    for (const { author, rec } of queued) {
      try {
        const before = stmts.selectVolume.get(rec.isbn13);
        upsertVolume(db, author, rec);
        if (before) stats.updatedVolumes++;
        else stats.insertedVolumes++;
        stats.upsertedVolumes++;
      } catch (err) {
        stats.errors++;
        console.warn(
          `  [error] isbn=${rec.isbn13}: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
    }
  });

  return stats;
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  if (!args.jsonldPath) {
    console.error(
      "usage: fetch-madb --jsonld-path <path> [--qid Q1234 | --name 'X' | --all] [--limit N] [--include-adult]",
    );
    process.exit(1);
  }
  if (!args.qid && !args.name && !args.all) {
    console.error("require --qid, --name, or --all");
    process.exit(1);
  }

  const db = openDb();
  const authors = resolveAuthors(db, args);
  if (authors.length === 0) {
    console.warn("[fetch-madb] no mangaka resolved, exit.");
    db.close();
    return;
  }

  console.log(
    `[fetch-madb] jsonld=${args.jsonldPath} authors=${authors.length}, includeAdult=${args.includeAdult}`,
  );

  const adultSeeds = loadAdultSeeds(db);
  console.log(
    `[adult-seeds] imprints=${adultSeeds.adultImprints.size}, publishers=${adultSeeds.adultPublishers.size}`,
  );

  const authorIndex = buildAuthorIndex(authors);
  console.log(
    `[author-index] ${authorIndex.size} unique normalized name keys (incl. alt_names)`,
  );

  const stats = await processJsonld(
    db,
    args.jsonldPath,
    authorIndex,
    adultSeeds,
    args,
  );

  console.log(`\n[fetch-madb] done`);
  console.log(`  total records          : ${stats.totalRecords}`);
  console.log(`  parse errors           : ${stats.parseErrors}`);
  console.log(`  skipped (rating)       : ${stats.skippedAdultRating}`);
  console.log(`  skipped (description)  : ${stats.skippedAdultDescription}`);
  console.log(`  skipped (imprint)      : ${stats.skippedAdultImprint}`);
  console.log(`  skipped (publisher)    : ${stats.skippedAdultPublisher}`);
  console.log(`  matched records        : ${stats.matchedRecords}`);
  console.log(`  upserted volumes       : ${stats.upsertedVolumes}`);
  console.log(`    inserted             : ${stats.insertedVolumes}`);
  console.log(`    updated              : ${stats.updatedVolumes}`);
  console.log(`  errors                 : ${stats.errors}`);

  db.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

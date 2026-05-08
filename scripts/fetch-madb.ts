/**
 * メディア芸術データベース (MADB) 公式 CSV (= cm101 マンガ単行本 全量、
 * もしくは cm104 差分) を読み込んで SQLite に投入する fetcher。
 *
 * 使い方:
 *   npm run fetch:madb -- --csv-path .cache/madb/cm101.csv --qid Q11331084     # 単一 mangaka
 *   npm run fetch:madb -- --csv-path .cache/madb/cm101.csv --name "諫山創"     # 名前指定
 *   npm run fetch:madb -- --csv-path .cache/madb/cm101.csv --all               # mangaka.qid IS NOT NULL の全員
 *   npm run fetch:madb -- --csv-path .cache/madb/cm101.csv --all --limit 50    # 動作確認
 *   npm run fetch:madb -- --csv-path .cache/madb/cm101.csv --all --include-adult   # adult-credit 作家もスキップしない
 *
 * SPARQL 路線 (旧実装) からの転換理由:
 *   - rate limit / schema discovery 不要
 *   - 「版表示」「巻」「レーティング」が独立 column 化されており、 完全版判定 +
 *     成年コミック判定が SPARQL より正確
 *   - 70MB CSV を 1 パス読むだけで 397k record 全件処理 (= 数分)
 *
 * adult filter は 4 層 (= lib/madb-csv.ts isAdultMadbRecord 参照):
 *   1. レーティング = 成年コミック     ← MADB 公式 rating (= 一次)
 *   2. 概要に 成年コミック 含む          ← rating 漏れ catch
 *   3. 単行本レーベル ∈ adult_imprints  ← imprint 単位の DB seed (= Tier 2)
 *   4. 発行者名 ∈ adult_publishers      ← publisher 単位の DB seed (= Tier 1)
 */
import "./_env";
import fs from "node:fs";
import path from "node:path";
import readline from "node:readline";
import YAML from "yaml";
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
  isAdultMadbRecord,
  parseCsvLine,
  parseVolumeNumber,
  rowToMadbCsvRow,
  splitAuthors,
  stripBom,
  type AdultMatchSignal,
  type MadbCsvRow,
} from "../lib/madb-csv";
import type { Statement as BSStatement } from "better-sqlite3";
import { openDb, recordSource, tx, type DB } from "./_db";

type Stmt = BSStatement<unknown[], unknown>;

type Args = {
  csvPath: string | null;
  qid: string | null;
  name: string | null;
  all: boolean;
  limit: number | null;
  includeAdult: boolean;
};

function parseArgs(argv: string[]): Args {
  const out: Args = {
    csvPath: null,
    qid: null,
    name: null,
    all: false,
    limit: null,
    includeAdult: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = argv[i + 1];
    if (a === "--csv-path" && next) {
      out.csvPath = next;
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
 * publishers.yml の name → key 逆引きマップ。 series.publisher_key を
 * MADB CSV の 発行者名 から解決するのに使う。
 * magazine_key は MADB 構造上 単行本側から取れないので fetch:wikipedia 担当。
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

/**
 * adult_imprints / adult_publishers テーブルから NFKC 正規化済の Set を作る。
 * isAdultMadbRecord の引数として CSV の 1 row ごとに参照される。
 */
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

/** upsertVolume が要求する作家識別。 mangaka_id が無い場合は null で OK。 */
type AuthorRef = {
  qid: string | null;
  name: string;
  altNames: string[];
  mangakaId: number | null;
};

/**
 * MadbRec は upsertVolume の入力。 CSV row を直接食わせるのでなく、
 * 旧 SPARQL 経路で慣らしたシェイプを保つ (= 後で SPARQL を再採用したく
 * なっても upsertVolume を変える必要がない)。
 */
type MadbRec = {
  manifestationUri: string;
  title: string | null;
  creator: string;
  isbn13: string;
  /** 発行者 (= 出版社、 series.publisher_key 解決の入力) */
  publisher: string | null;
  /** 単行本レーベル (= imprint、 editions.imprint 行き) */
  imprint: string | null;
  /** 版表示 (= "完全版" / "特装版" 等。 classifyEdition 入力に最優先で使う) */
  editionLabel: string | null;
  /** YYYY-MM-DD or partial */
  datePublished: string | null;
  /** CSV 由来の純数字巻番号 (= 取れた時のみ。 取れなければ null で title fallback) */
  csvVolumeNumber: number | null;
};

/**
 * MadbCsvRow → MadbRec 変換。 ISBN 不正 / 必須 field 欠落は null で skip。
 */
function csvRowToMadbRec(row: MadbCsvRow): MadbRec | null {
  const isbn13 = normalizeIsbn13(row.isbn);
  if (!isbn13) return null;
  // creator は CSV では 1 個の string (= "X　＼＼　Y" 形式)。 mangaka 紐付け
  // 用に splitAuthors した個別名は別経路、 ここは raw value を保存して
  // sources.raw_json で audit できるようにしておく。
  const creator = row.authorName.trim();
  if (!creator) return null;
  return {
    manifestationUri: `https://mediaarts-db.artmuseums.go.jp/data/manifestation/${row.madbId}`,
    title: row.title.trim() || null,
    creator,
    isbn13,
    publisher: row.publisherName.trim() || null,
    imprint: row.bookLabel.trim() || null,
    editionLabel: row.editionLabel.trim() || null,
    datePublished: row.publishedAt.trim() || null,
    csvVolumeNumber: parseVolumeNumber(row.volumeNumber),
  };
}

/**
 * fetch-ndl と同じく prepared statements をモジュールレベルにキャッシュ。
 */
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
    // ユーザ意思: 既存 NDL 由来 volume は MADB データで上書き。
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
 * 1 record を upsert。 fetch-ndl の upsertVolume と同等の責務。
 *
 * CSV 由来データの優先順:
 *   - editionType: rec.editionLabel (= 「版表示」 column) を最優先 →
 *     fallback で title から classifyEdition
 *   - volumeNumber: rec.csvVolumeNumber (= 「巻」 column の純数字) →
 *     fallback で title から extractVolumeNumber
 *   - imprint: rec.imprint (= 「単行本レーベル」)
 *   - publisher_key: rec.publisher (= 「発行者名」 を publishers.yml で解決)
 */
function upsertVolume(db: DB, author: AuthorRef, rec: MadbRec): void {
  const titleForKey = rec.title ?? rec.isbn13;
  const seriesKey = buildSeriesKey(titleForKey, {
    qid: author.qid,
    name: author.name,
  });
  const seriesDisplay = baseTitle(titleForKey);

  // editionLabel が空でないなら最優先 (= MADB 公式の「版表示」)。
  // 空なら title から classifyEdition (= keyword scan)。
  const editionInput = rec.editionLabel ?? rec.title ?? "";
  let editionType: EditionType = classifyEdition(editionInput);
  // 巻番号は CSV の 「巻」 column を最優先、 取れなければ title fallback。
  const volumeNumber =
    rec.csvVolumeNumber ?? (rec.title ? extractVolumeNumber(rec.title) : null);
  // 巻番号取れない record は本編 series でないことが多い (= 関連書籍 /
  // セット商品 / ガイドブック)。 standard edition に混ぜると vol1 集約で
  // 誤集計になるので type=other に分離。
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

  // ===== series upsert =====
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

  // ===== series_authors 紐付け =====
  if (author.mangakaId !== null) {
    stmts.insertSeriesAuthor.run(seriesId, author.mangakaId, "writer_artist");
  }

  // series.publisher_key を master 解決値で埋める。 既存値があれば touch しない。
  if (publisherKey !== null) {
    stmts.updateSeriesPublisherKey.run(publisherKey, seriesId);
  }

  // ===== edition upsert =====
  const existingEdition = stmts.selectEdition.get(seriesId, editionType) as
    | { id: number; year_started: number | null; year_ended: number | null }
    | undefined;

  // imprint には CSV の 「単行本レーベル」 を最優先。 無ければ publisher 名で fallback。
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

  // ===== volume upsert (= 既存 NDL volume があれば MADB で上書き) =====
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

  // ===== sources 記録 =====
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

/** 解決済 mangaka 情報。 名前 index と 1:N 紐付けに使う。 */
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

/**
 * 「正規化済名前 → 紐付ける ResolvedAuthor 群」 の index を作る。
 * MADB CSV の 作者名 column (= splitAuthors 後) と normalizeCreatorName で
 * exact match させて 1:N 解決する。
 */
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
  totalRows: number;
  parsedRows: number;
  parseErrors: number;
  skippedAdultRating: number;
  skippedAdultSummary: number;
  skippedAdultImprint: number;
  skippedAdultPublisher: number;
  matchedRows: number;
  upsertedVolumes: number;
  insertedVolumes: number;
  updatedVolumes: number;
  errors: number;
};

function newStats(): Stats {
  return {
    totalRows: 0,
    parsedRows: 0,
    parseErrors: 0,
    skippedAdultRating: 0,
    skippedAdultSummary: 0,
    skippedAdultImprint: 0,
    skippedAdultPublisher: 0,
    matchedRows: 0,
    upsertedVolumes: 0,
    insertedVolumes: 0,
    updatedVolumes: 0,
    errors: 0,
  };
}

function bumpAdultStat(stats: Stats, signal: AdultMatchSignal): void {
  if (signal === "rating") stats.skippedAdultRating++;
  else if (signal === "summary") stats.skippedAdultSummary++;
  else if (signal === "imprint") stats.skippedAdultImprint++;
  else if (signal === "publisher") stats.skippedAdultPublisher++;
}

/**
 * CSV を 1 パスで読み、 各 row を adult filter → 作者 index で紐付け →
 * 該当 mangaka 全員に対して upsertVolume を呼ぶ。
 *
 * トランザクション境界は CSV 全体で 1 つ。 better-sqlite3 は同期 API なので
 * stream の各行で immediate 実行できる。
 */
async function processCsv(
  db: DB,
  csvPath: string,
  authorIndex: Map<string, ResolvedAuthor[]>,
  adultSeeds: { adultImprints: Set<string>; adultPublishers: Set<string> },
  args: Args,
): Promise<Stats> {
  const stats = newStats();

  if (!fs.existsSync(csvPath)) {
    throw new Error(`csv not found: ${csvPath}`);
  }

  const rl = readline.createInterface({
    input: fs.createReadStream(csvPath, { encoding: "utf8" }),
    crlfDelay: Infinity,
  });

  let isFirstLine = true;
  // tx() は同期関数を要求するので、 CSV 行を一旦配列に貯めてから transaction
  // で投入する。 メモリは 397k × 12 column ≈ 数十 MB の想定。
  const queued: { author: ResolvedAuthor; rec: MadbRec }[] = [];

  for await (let line of rl) {
    if (isFirstLine) {
      isFirstLine = false;
      // header 行は捨てる (= column position は EXPECTED_COLUMN_COUNT で
      // 固定前提)
      line = stripBom(line);
      continue;
    }
    stats.totalRows++;

    const cells = parseCsvLine(line);
    const csvRow = rowToMadbCsvRow(cells);
    if (!csvRow) {
      stats.parseErrors++;
      continue;
    }
    stats.parsedRows++;

    if (!args.includeAdult) {
      const adultSig = isAdultMadbRecord(
        csvRow,
        adultSeeds.adultImprints,
        adultSeeds.adultPublishers,
      );
      if (adultSig) {
        bumpAdultStat(stats, adultSig);
        continue;
      }
    }

    // 作者 1:N 紐付け
    const authorsInRow = splitAuthors(csvRow.authorName);
    const matched: ResolvedAuthor[] = [];
    for (const a of authorsInRow) {
      const key = normalizeCreatorName(a);
      if (!key) continue;
      const hits = authorIndex.get(key);
      if (hits) matched.push(...hits);
    }
    if (matched.length === 0) continue;
    stats.matchedRows++;

    const rec = csvRowToMadbRec(csvRow);
    if (!rec) {
      stats.parseErrors++;
      continue;
    }

    // 同じ csv row が複数 mangaka にヒットすることもある (共著)。 重複なく
    // 1 record × N author で投入。
    const seen = new Set<number | string>();
    for (const a of matched) {
      const key = a.mangakaId ?? `name:${a.name}`;
      if (seen.has(key)) continue;
      seen.add(key);
      queued.push({ author: a, rec });
    }
  }

  console.log(
    `[csv] read ${stats.totalRows} rows, parsed=${stats.parsedRows}, matched=${stats.matchedRows}, queued=${queued.length}`,
  );

  // ===== DB 投入 (= 1 トランザクション) =====
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
  if (!args.csvPath) {
    console.error(
      "usage: fetch-madb --csv-path <path> [--qid Q1234 | --name 'X' | --all] [--limit N] [--include-adult]",
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
    `[fetch-madb] csv=${args.csvPath} authors=${authors.length}, includeAdult=${args.includeAdult}`,
  );

  const adultSeeds = loadAdultSeeds(db);
  console.log(
    `[adult-seeds] imprints=${adultSeeds.adultImprints.size}, publishers=${adultSeeds.adultPublishers.size}`,
  );

  const authorIndex = buildAuthorIndex(authors);
  console.log(
    `[author-index] ${authorIndex.size} unique normalized name keys (incl. alt_names)`,
  );

  const stats = await processCsv(db, args.csvPath, authorIndex, adultSeeds, args);

  console.log(`\n[fetch-madb] done`);
  console.log(`  total rows           : ${stats.totalRows}`);
  console.log(`  parsed rows          : ${stats.parsedRows}`);
  console.log(`  parse errors         : ${stats.parseErrors}`);
  console.log(`  skipped (rating)     : ${stats.skippedAdultRating}`);
  console.log(`  skipped (summary)    : ${stats.skippedAdultSummary}`);
  console.log(`  skipped (imprint)    : ${stats.skippedAdultImprint}`);
  console.log(`  skipped (publisher)  : ${stats.skippedAdultPublisher}`);
  console.log(`  matched rows         : ${stats.matchedRows}`);
  console.log(`  upserted volumes     : ${stats.upsertedVolumes}`);
  console.log(`    inserted           : ${stats.insertedVolumes}`);
  console.log(`    updated            : ${stats.updatedVolumes}`);
  console.log(`  errors               : ${stats.errors}`);

  db.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

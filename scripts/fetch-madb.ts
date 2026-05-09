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
  /**
   * 巻番号 (= 採用優先順位)。 仕様上 schema:position が deterministic な数値、
   * schema:volumeNumber は表示文字列なので、 まず position を採用、 不在時のみ
   * volumeNumber を parseVolumeNumber で解釈。 これにより銀魂 (= "其之1" / "巻ノ
   * 五十") のような非数値表示でも position が integer なら正しく拾える。
   */
  csvVolumeNumber: number | null;
  /** schema:image 由来の cover URL。 無ければ null。 */
  coverUrl: string | null;
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
    // position 優先 → 不在なら volumeNumber を parse。
    csvVolumeNumber: rec.volumeSort ?? parseVolumeNumber(rec.volumeNumber),
    coverUrl: rec.coverImage || null,
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

type ArchiveStmts = {
  selectArchive: Stmt;
  insertArchive: Stmt;
  updateArchive: Stmt;
  upsertExcluded: Stmt;
  deleteExcluded: Stmt;
};

let cachedStmts: { db: DB; stmts: VolumeStmts } | null = null;
let cachedArchiveStmts: { db: DB; stmts: ArchiveStmts } | null = null;

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
      `INSERT INTO volumes (edition_id, isbn13, number, is_extra, release_date, cover_url)
       VALUES (?, ?, ?, ?, ?, ?)`,
    ),
    updateVolume: db.prepare(
      `UPDATE volumes
       SET edition_id   = ?,
           number       = ?,
           is_extra     = ?,
           release_date = COALESCE(?, release_date),
           cover_url    = COALESCE(?, cover_url),
           updated_at   = strftime('%Y-%m-%dT%H:%M:%SZ','now')
       WHERE isbn13 = ?`,
    ),
  };
  cachedStmts = { db, stmts };
  return stmts;
}

function getArchiveStmts(db: DB): ArchiveStmts {
  if (cachedArchiveStmts && cachedArchiveStmts.db === db)
    return cachedArchiveStmts.stmts;
  const stmts: ArchiveStmts = {
    selectArchive: db.prepare(
      `SELECT id, year_started, year_ended, current_state, adult_score
       FROM series_archive WHERE series_key = ?`,
    ),
    insertArchive: db.prepare(
      `INSERT INTO series_archive
         (series_key, title, year_started, year_ended, publisher_key,
          adult_score, current_state)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
    ),
    updateArchive: db.prepare(
      `UPDATE series_archive
       SET title         = ?,
           year_started  = ?,
           year_ended    = ?,
           publisher_key = COALESCE(publisher_key, ?),
           adult_score   = MAX(adult_score, ?),
           current_state = ?,
           last_imported_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
       WHERE id = ?`,
    ),
    upsertExcluded: db.prepare(
      `INSERT INTO series_excluded
         (archive_id, reason, signals_json, excluded_at, excluded_by)
       VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'), 'auto')
       ON CONFLICT(archive_id) DO UPDATE SET
         reason       = excluded.reason,
         signals_json = excluded.signals_json`,
    ),
    deleteExcluded: db.prepare(
      `DELETE FROM series_excluded WHERE archive_id = ?`,
    ),
  };
  cachedArchiveStmts = { db, stmts };
  return stmts;
}

/**
 * AdultMatchSignal → archive.adult_score 用の重み。 admin UI で
 * 重い signal 順にソートする時の sort key として使う。
 */
const ADULT_SIGNAL_WEIGHT: Record<NonNullable<AdultMatchSignal>, number> = {
  rating: 5,
  description: 3,
  imprint: 3,
  publisher: 3,
};

/**
 * AdultMatchSignal → series_excluded.reason への label 変換 (= UI 表示・集計用)。
 */
const ADULT_SIGNAL_REASON: Record<NonNullable<AdultMatchSignal>, string> = {
  rating: "adult_rating",
  description: "adult_description",
  imprint: "adult_imprint",
  publisher: "adult_publisher",
};

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
      rec.coverUrl,
      rec.isbn13,
    );
  } else {
    stmts.insertVolume.run(
      editionId,
      rec.isbn13,
      numberVal,
      isExtra,
      releaseDate,
      rec.coverUrl,
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
  /** record 単位で adult signal が当たった件数の内訳 (= debug 用) */
  adultRecordsRating: number;
  adultRecordsDescription: number;
  adultRecordsImprint: number;
  adultRecordsPublisher: number;
  matchedRecords: number;
  /** 2nd pass で dcterms:creator の C-ID 経由 で 解決できた件数 (= 1st pass の
   *  schema:creator 文字列 match が外れた record で C-ID 学習済 author を当てた数)。 */
  matchedViaCid: number;
  /** archive (= source-of-truth) に upsert した uniqe series 数 */
  archivedSeriesNew: number;
  archivedSeriesUpdated: number;
  /** 自動的に excluded に振り分けた series 数 (= 今 run 内で新規/再評価) */
  excludedSeries: number;
  /** archive.current_state='live' (= 過去に admin 復帰させた) の series で
   * adult signal が当たったが live を維持した件数。 admin に通知すべき可能性あり。 */
  liveDespiteSignal: number;
  /** archive.current_state='deleted' で skip した series 数 */
  skippedDeleted: number;
  upsertedVolumes: number;
  insertedVolumes: number;
  updatedVolumes: number;
  errors: number;
};

function newStats(): Stats {
  return {
    totalRecords: 0,
    parseErrors: 0,
    adultRecordsRating: 0,
    adultRecordsDescription: 0,
    adultRecordsImprint: 0,
    adultRecordsPublisher: 0,
    matchedRecords: 0,
    matchedViaCid: 0,
    archivedSeriesNew: 0,
    archivedSeriesUpdated: 0,
    excludedSeries: 0,
    liveDespiteSignal: 0,
    skippedDeleted: 0,
    upsertedVolumes: 0,
    insertedVolumes: 0,
    updatedVolumes: 0,
    errors: 0,
  };
}

function bumpAdultStat(stats: Stats, signal: AdultMatchSignal): void {
  if (signal === "rating") stats.adultRecordsRating++;
  else if (signal === "description") stats.adultRecordsDescription++;
  else if (signal === "imprint") stats.adultRecordsImprint++;
  else if (signal === "publisher") stats.adultRecordsPublisher++;
}

/**
 * 1 series 分の archive 用メタ。 stream で record を見ながら集約していく。
 */
type SeriesMeta = {
  seriesKey: string;
  title: string;
  yearStarted: number | null;
  yearEnded: number | null;
  publisherKey: string | null;
};

/**
 * stream-json で `@graph` array を pull しながら 1 record ずつ:
 *   1. extractRecord で typed shape に変換
 *   2. adult filter 4 層 (= 結果は早期 skip せず record に付与する)
 *   3. 作者 index で mangaka 紐付け (= 共著は 1:N)
 *   4. matched record をキューに積む (= 全行スキャン後に 1 transaction で投入)
 *
 * Transaction phase は 2 pass:
 *   Pass A: 各 series_key について
 *     - series_archive を upsert (= source-of-truth、 全 import 履歴を保持)
 *     - 既に archive.current_state='deleted' なら以後 skip (= 完全削除済み)
 *     - 既に archive.current_state='live' なら adult signal を無視して live (= sticky reinstate)
 *     - それ以外で adult signal が当たれば series_excluded に upsert、 state='excluded'
 *     - それ以外は state='live'
 *   Pass B: queued の 1 record ずつ upsertVolume (= 既存の series/editions/volumes 経路)
 *           ただし pass A で 'live' 判定されなかった series_key の record は skip。
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

  const masters = getMasters();

  type Queued = {
    author: ResolvedAuthor;
    rec: UpsertRec;
    seriesKey: string;
    /** この record が当たった adult signal (= null なら clean) */
    adultSig: AdultMatchSignal;
  };
  const queued: Queued[] = [];

  // dcterms:creator (= C-ID URI) を schema:creator match と 紐付けて学習する
  // single-pass map。 同 C-ID の record が以降に出てきた時、 schema:creator
  // 文字列 match が外れていても以前の学習結果で author 解決できる。
  const cidIndex = new Map<string, ResolvedAuthor[]>();

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

    // adult signal は record 単位で判定する。 ここでは early skip せず、
    // queued に持ち越して transaction で series 単位に集約する。
    const adultSig = isAdultMadbRecord(
      rec,
      adultSeeds.adultImprints,
      adultSeeds.adultPublishers,
    );
    if (adultSig) bumpAdultStat(stats, adultSig);

    // 1st pass match: schema:creator 文字列ベース (= cleanCreatorStrings 後の
    // clean 著者名で authorIndex を引く)。
    const matched: ResolvedAuthor[] = [];
    for (const a of rec.authors) {
      const key = normalizeCreatorName(a);
      if (!key) continue;
      const hits = authorIndex.get(key);
      if (hits) matched.push(...hits);
    }

    // 2nd pass match: dcterms:creator (= C-ID Agent entity URI) ベース。
    // 同 C-ID が以前の record で schema:creator 経由で mangaka に解決済の場合、
    // それを再利用する。 schema:creator が空 / 異形 prefix で 1st pass を
    // すり抜けた record を救う仕組み。 C-ID の学習は下で行う。
    if (matched.length === 0 && rec.creatorRefs.length > 0) {
      for (const cid of rec.creatorRefs) {
        const learned = cidIndex.get(cid);
        if (learned) {
          for (const a of learned) {
            if (
              !matched.some((m) => m.qid === a.qid && m.name === a.name)
            ) {
              matched.push(a);
            }
          }
        }
      }
      if (matched.length > 0) stats.matchedViaCid++;
    }

    if (matched.length === 0) continue;
    stats.matchedRecords++;

    // 学習: C-ID ↔ author を **1:1 の record でのみ** 紐付ける。 共著 record
    // (= matched.length>1 or creatorRefs.length>1) で位置対応が不明な場合に
    // 学習すると、 1 つの C-ID に複数 author を誤紐付けして以降の lookup が
    // 暴発する (= 同 C-ID の他 record が全 author を queued に追加) ため除外。
    // 1:1 record だけ学習しても、 同 author の単独著作 record は通常多数あるので
    // C-ID 解決の coverage はほぼ落ちない。
    if (matched.length === 1 && rec.creatorRefs.length === 1) {
      const cid = rec.creatorRefs[0];
      const existing = cidIndex.get(cid);
      if (!existing) {
        cidIndex.set(cid, [matched[0]]);
      } else if (
        !existing.some(
          (e) => e.qid === matched[0].qid && e.name === matched[0].name,
        )
      ) {
        existing.push(matched[0]);
      }
    }

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
      const titleForKey = up.title ?? up.isbn13;
      const seriesKey = buildSeriesKey(titleForKey, {
        qid: a.qid,
        name: a.name,
      });
      queued.push({ author: a, rec: up, seriesKey, adultSig });
    }
  }

  console.log(
    `[stream] read ${stats.totalRecords} records, matched=${stats.matchedRecords}, queued=${queued.length}`,
  );

  // Transaction phase
  tx(db, () => {
    const stmts = getStmts(db);
    const archiveStmts = getArchiveStmts(db);

    // ----- 集約: series_key 単位の meta + adult signal set -----
    const seriesMeta = new Map<string, SeriesMeta>();
    const seriesAdultSigs = new Map<
      string,
      Set<NonNullable<AdultMatchSignal>>
    >();
    for (const q of queued) {
      let meta = seriesMeta.get(q.seriesKey);
      if (!meta) {
        meta = {
          seriesKey: q.seriesKey,
          title: baseTitle(q.rec.title ?? q.rec.isbn13),
          yearStarted: null,
          yearEnded: null,
          publisherKey: null,
        };
        seriesMeta.set(q.seriesKey, meta);
      }
      const releaseDate = normalizeReleaseDate(q.rec.datePublished);
      const issuedYear =
        releaseDate && /^\d{4}/.test(releaseDate)
          ? Number(releaseDate.slice(0, 4))
          : null;
      if (issuedYear !== null) {
        meta.yearStarted =
          meta.yearStarted === null
            ? issuedYear
            : Math.min(meta.yearStarted, issuedYear);
        meta.yearEnded =
          meta.yearEnded === null
            ? issuedYear
            : Math.max(meta.yearEnded, issuedYear);
      }
      if (meta.publisherKey === null && q.rec.publisher) {
        meta.publisherKey =
          masters.publisher.get(q.rec.publisher.normalize("NFKC")) ?? null;
      }
      if (q.adultSig) {
        let sigs = seriesAdultSigs.get(q.seriesKey);
        if (!sigs) {
          sigs = new Set();
          seriesAdultSigs.set(q.seriesKey, sigs);
        }
        sigs.add(q.adultSig);
      }
    }

    // ----- Pass A: archive + excluded -----
    const goLive = new Map<string, boolean>();
    for (const [seriesKey, meta] of seriesMeta) {
      const existing = archiveStmts.selectArchive.get(seriesKey) as
        | {
            id: number;
            year_started: number | null;
            year_ended: number | null;
            current_state: "live" | "excluded" | "deleted";
            adult_score: number;
          }
        | undefined;

      if (existing?.current_state === "deleted") {
        // 完全削除済み: archive 行は触らず (= last_imported_at も更新しない)、
        // live への投入も行わない。 admin が明示的に復活させない限り消えたまま。
        stats.skippedDeleted++;
        goLive.set(seriesKey, false);
        continue;
      }

      const sigs = seriesAdultSigs.get(seriesKey);
      const sigList = sigs ? [...sigs] : [];
      const adultScore =
        sigList.length > 0
          ? Math.max(...sigList.map((s) => ADULT_SIGNAL_WEIGHT[s]))
          : 0;

      // state 判定。
      //   - 既に live (= 過去 import 済み or admin 復帰): live を維持。
      //     adult signal が新たに当たっていても sticky に live のまま (= 通知のみ)。
      //   - includeAdult=true: live にする (= dev 用 override)。
      //   - 上記以外で adult signal あり: excluded。
      //   - それ以外: live。
      let newState: "live" | "excluded";
      if (existing?.current_state === "live") {
        newState = "live";
        if (sigList.length > 0) stats.liveDespiteSignal++;
      } else if (args.includeAdult) {
        newState = "live";
      } else if (sigList.length > 0) {
        newState = "excluded";
      } else {
        newState = "live";
      }

      // start/end year は既存値と min/max で merge (= archive は全 import の包絡)
      const mergedStart =
        existing?.year_started === null || existing?.year_started === undefined
          ? meta.yearStarted
          : meta.yearStarted === null
            ? existing.year_started
            : Math.min(existing.year_started, meta.yearStarted);
      const mergedEnd =
        existing?.year_ended === null || existing?.year_ended === undefined
          ? meta.yearEnded
          : meta.yearEnded === null
            ? existing.year_ended
            : Math.max(existing.year_ended, meta.yearEnded);

      let archiveId: number;
      if (existing) {
        archiveStmts.updateArchive.run(
          meta.title,
          mergedStart,
          mergedEnd,
          meta.publisherKey,
          adultScore,
          newState,
          existing.id,
        );
        archiveId = existing.id;
        stats.archivedSeriesUpdated++;
      } else {
        const info = archiveStmts.insertArchive.run(
          seriesKey,
          meta.title,
          meta.yearStarted,
          meta.yearEnded,
          meta.publisherKey,
          adultScore,
          newState,
        );
        archiveId = Number(info.lastInsertRowid);
        stats.archivedSeriesNew++;
      }

      if (newState === "excluded") {
        const reason = ADULT_SIGNAL_REASON[sigList[0]];
        const signalsJson = JSON.stringify(sigList);
        archiveStmts.upsertExcluded.run(archiveId, reason, signalsJson);
        stats.excludedSeries++;
      } else {
        // state が live になった (= reinstate 含む) なら excluded を掃除する。
        // 過去に excluded だった record でも、 admin が live に戻した後の re-run
        // では excluded 行が残らないように。
        archiveStmts.deleteExcluded.run(archiveId);
      }

      goLive.set(seriesKey, newState === "live");
    }

    // ----- Pass B: live volumes (= 既存 series/editions/volumes 経路) -----
    for (const { author, rec, seriesKey } of queued) {
      if (!goLive.get(seriesKey)) continue;
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
  console.log(`  matched records        : ${stats.matchedRecords}`);
  console.log(`    via dcterms:creator  : ${stats.matchedViaCid}`);
  console.log(`  adult records (rating) : ${stats.adultRecordsRating}`);
  console.log(`  adult records (desc)   : ${stats.adultRecordsDescription}`);
  console.log(`  adult records (imprint): ${stats.adultRecordsImprint}`);
  console.log(`  adult records (pub)    : ${stats.adultRecordsPublisher}`);
  console.log(`  archive new            : ${stats.archivedSeriesNew}`);
  console.log(`  archive updated        : ${stats.archivedSeriesUpdated}`);
  console.log(`  excluded series        : ${stats.excludedSeries}`);
  console.log(`  live despite signal    : ${stats.liveDespiteSignal}`);
  console.log(`  skipped (deleted)      : ${stats.skippedDeleted}`);
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

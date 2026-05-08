/**
 * メディア芸術データベース (MADB) の SPARQL endpoint から、 指定漫画家の
 * 作品を取得して SQLite に投入する。 既存 fetch-ndl.ts の構造を踏襲、
 * NDL pipeline と並走する想定 (= ユーザ意思: NDL 仕組みは残置、 データは
 * MADB 由来に置換)。
 *
 * 使い方:
 *   npm run fetch:madb -- --qid Q11331084                    # 単一 mangaka (DB 紐付けあり)
 *   npm run fetch:madb -- --name "諫山創"                      # 名前指定 (= DB 紐付けなし)
 *   npm run fetch:madb -- --qid Q11331084 --include-original-author  # [原作] credits も拾う
 *   npm run fetch:madb -- --all                              # mangaka.qid IS NOT NULL の全員
 *   npm run fetch:madb -- --all --limit 50                   # 動作確認用
 *   npm run fetch:madb -- --qid Q11331084 --include-adult    # adult-credit 作家もスキップしない
 *
 * SPARQL endpoint: https://mediaarts-db.artmuseums.go.jp/sparql
 *
 * MADB の vocabulary は probe-madb.ts の schema discovery で確定済:
 *   class:MangaBook (= 漫画単行本、 397k 件)
 *   schema:creator (= 役割タグ + 名前を連結した literal、 例 "[著]諫山創")
 *   schema:isbn / schema:publisher / schema:isPartOf / schema:datePublished
 *   prop: prefix で MADB 独自プロパティ (= originalWorkCreator 等)
 *
 * NDL fetcher と異なり、 MADB は creator が literal なので URI dereferencing
 * 不要。 役割タグ (= [著]/[原作]/[画]/[作画]/[漫画]) と共著連結 (= [著]A,B)
 * を REGEX で吸収する。
 */
import "./_env";
import fs from "node:fs";
import path from "node:path";
import YAML from "yaml";
import {
  type EditionType,
  EDITION_LABELS,
  baseTitle,
  buildSeriesKey,
  classifyEdition,
  extractVolumeNumber,
  normalizeIsbn13,
  normalizeReleaseDate,
} from "../lib/edition";
import type { Statement as BSStatement } from "better-sqlite3";
import { openDb, recordSource, tx, type DB } from "./_db";

type Stmt = BSStatement<unknown[], unknown>;

const ENDPOINT = "https://mediaarts-db.artmuseums.go.jp/sparql";
const REQUEST_INTERVAL_MS = 1100;
const MAX_RETRIES = 4;
const QUERY_LIMIT = 2000;

const RAW_DIR = path.join(process.cwd(), ".cache", "madb");

type Args = {
  qid: string | null;
  name: string | null;
  all: boolean;
  limit: number | null;
  includeAdult: boolean;
  includeOriginalAuthor: boolean;
};

function parseArgs(argv: string[]): Args {
  const out: Args = {
    qid: null,
    name: null,
    all: false,
    limit: null,
    includeAdult: false,
    includeOriginalAuthor: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = argv[i + 1];
    if (a === "--qid" && next) {
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
    } else if (a === "--include-original-author") {
      out.includeOriginalAuthor = true;
    }
  }
  return out;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * MADB の publisher / magazine literal は「漢字　∥　カナ」 (= 全角空白 +
 * ダブルスラッシュ + 全角空白) で連結された 1 文字列で発行される。
 * 例: "講談社　∥　コウダンシャ" / "週刊少年ジャンプ　∥　シュウカンショウネンジャンプ"
 *
 * downstream で扱いやすいよう漢字部分のみ抽出。 連結子が無い場合は元値
 * をそのまま返す (= 海外版書誌 等の例外ケース安全)。
 */
function splitMadbLiteral(s: string | null): string | null {
  if (!s) return null;
  const idx = s.indexOf("∥");
  return (idx >= 0 ? s.slice(0, idx) : s).trim() || null;
}

/**
 * publishers.yml / magazines.yml を読み込んで「name → key」 逆引きマップ
 * を作る。 fetch-wikipedia の loadMasterMaps を縮約した版。 read-only。
 */
type MasterMaps = {
  publisher: Map<string, string>;
  magazine: Map<string, string>;
};

let cachedMasters: MasterMaps | null = null;

function getMasters(): MasterMaps {
  if (cachedMasters) return cachedMasters;
  const dataDir = path.join(process.cwd(), "data");
  const pubYaml = YAML.parse(
    fs.readFileSync(path.join(dataDir, "publishers.yml"), "utf8"),
  ) as Record<string, { name: string }>;
  const magYaml = YAML.parse(
    fs.readFileSync(path.join(dataDir, "magazines.yml"), "utf8"),
  ) as Record<string, { name: string }>;
  const publisher = new Map<string, string>();
  for (const [k, v] of Object.entries(pubYaml)) {
    publisher.set(v.name.normalize("NFKC"), k);
  }
  const magazine = new Map<string, string>();
  for (const [k, v] of Object.entries(magYaml)) {
    magazine.set(v.name.normalize("NFKC"), k);
  }
  cachedMasters = { publisher, magazine };
  return cachedMasters;
}

type SparqlBinding = Record<string, { type?: string; value?: string }>;

/**
 * SPARQL を POST + form-urlencoded で叩く。 GET より長文 query / CDN
 * キャッシュ回避に有利。 リトライは 5xx 系のみ exponential backoff。
 */
async function sparqlFetch(query: string): Promise<{
  ok: boolean;
  bindings: SparqlBinding[];
  error: string | null;
}> {
  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    try {
      const res = await fetch(ENDPOINT, {
        method: "POST",
        headers: {
          Accept: "application/sparql-results+json",
          "Content-Type": "application/x-www-form-urlencoded",
          "User-Agent":
            "MANGAL-MADBFetcher/0.1 (+https://github.com/shuichi0725-cmyk/MANGAL)",
        },
        body: `query=${encodeURIComponent(query)}`,
      });
      if (res.ok) {
        const j = (await res.json()) as {
          results?: { bindings?: SparqlBinding[] };
        };
        return {
          ok: true,
          bindings: j.results?.bindings ?? [],
          error: null,
        };
      }
      // 4xx は再試行しても変わらないので即座に失敗。 5xx のみ retry。
      if (res.status < 500) {
        const body = (await res.text()).slice(0, 200);
        return {
          ok: false,
          bindings: [],
          error: `HTTP ${res.status}: ${body.replace(/\s+/g, " ")}`,
        };
      }
      console.warn(
        `  [retry ${attempt + 1}/${MAX_RETRIES}] HTTP ${res.status}, backoff...`,
      );
    } catch (err) {
      console.warn(
        `  [retry ${attempt + 1}/${MAX_RETRIES}] ${err instanceof Error ? err.message : String(err)}, backoff...`,
      );
    }
    await sleep(1000 * Math.pow(2, attempt)); // 1s / 2s / 4s / 8s
  }
  return { ok: false, bindings: [], error: `failed after ${MAX_RETRIES} retries` };
}

/**
 * SPARQL の REGEX literal にそのまま埋める時に正規表現メタ文字を escape。
 * MADB の創作者 literal には漢字主体だが、 念のためカッコ・アスタリスク等を
 * 安全にする。
 */
function escapeRegex(s: string): string {
  return s.replace(/[\\^$.*+?()[\]{}|]/g, "\\\\$&");
}

/**
 * MADB SPARQL に作家名で query。 役割タグ ([著]/[原作]/[画] 等) と共著連結
 * ([著]A,B) を REGEX で吸収する。 末尾境界を「文字列終端 / カンマ / 半角空白
 * / 全角空白 / ]」 で固定して、 同名別人 (= "諫山創 太郎") を排除。
 *
 *   FILTER(REGEX(?creator, "(^|\\]|,|[ 　])諫山創($|,|[ 　\\]])"))
 *
 * --include-original-author 無しなら schema:creator のみ、 ありなら
 * prop:originalWorkCreator も UNION (= [原作] 名義の作品も拾う)。
 */
async function fetchMadbForName(
  authorName: string,
  includeOriginalAuthor: boolean,
): Promise<{ ok: boolean; bindings: SparqlBinding[]; error: string | null }> {
  const escaped = escapeRegex(authorName);
  // SPARQL の string literal は C 風 escape (\\ → \) で、 さらに regex
  // 引数で \] = literal ] になる。 JS template の \\\\ は JS string の \\
  // (2 文字)、 SPARQL parser 後 \ (1 文字)、 regex は ] と組合わせて \] と読む。
  // 全角空白は literal char そのもの (= U+3000) を入れる (\\u3000 は SPARQL
  // string escape として標準じゃないので避ける)。
  const re = `(^|\\\\]|,|[ 　])${escaped}($|,|[ 　\\\\]])`;

  const creatorClause = includeOriginalAuthor
    ? `{ ?manifestation schema:creator ?creator }
       UNION
       { ?manifestation prop:originalWorkCreator ?creator }`
    : `?manifestation schema:creator ?creator .`;

  const query = `
    PREFIX schema: <https://schema.org/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX class: <https://mediaarts-db.artmuseums.go.jp/data/class#>
    PREFIX prop: <https://mediaarts-db.artmuseums.go.jp/data/property#>
    SELECT DISTINCT ?manifestation ?title ?creator ?isbn ?publisher ?magazine ?datePublished WHERE {
      ?manifestation a class:MangaBook .
      ${creatorClause}
      FILTER(REGEX(STR(?creator), "${re}"))
      OPTIONAL { ?manifestation rdfs:label ?title }
      OPTIONAL { ?manifestation schema:isbn ?isbn }
      OPTIONAL { ?manifestation schema:publisher ?publisher }
      OPTIONAL { ?manifestation schema:isPartOf ?magazine }
      OPTIONAL { ?manifestation schema:datePublished ?datePublished }
    } LIMIT ${QUERY_LIMIT}
  `;
  return sparqlFetch(query);
}

type MadbRec = {
  manifestationUri: string;
  title: string | null;
  creator: string;
  isbn13: string;
  publisher: string | null;
  magazine: string | null;
  datePublished: string | null;
};

/**
 * SPARQL binding を内部 record に正規化。 ISBN 不正 / 欠落は null 返しで
 * 呼び出し側が skip。
 */
function normalizeBinding(b: SparqlBinding): MadbRec | null {
  const manifestationUri = b["manifestation"]?.value;
  const rawIsbn = b["isbn"]?.value?.trim();
  const creator = b["creator"]?.value?.trim();
  if (!manifestationUri || !rawIsbn || !creator) return null;
  const isbn13 = normalizeIsbn13(rawIsbn);
  if (!isbn13) return null;
  return {
    manifestationUri,
    title: b["title"]?.value?.trim() || null,
    creator,
    isbn13,
    publisher: b["publisher"]?.value?.trim() || null,
    magazine: b["magazine"]?.value?.trim() || null,
    datePublished: b["datePublished"]?.value?.trim() || null,
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
  updateSeriesMagazineKey: Stmt;
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
    // COALESCE で既存値があれば touch しない (= 別 record で先に設定された
    // publisher_key / magazine_key を上書きで失わないため)。
    updateSeriesPublisherKey: db.prepare(
      `UPDATE series
       SET publisher_key = COALESCE(publisher_key, ?),
           updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
       WHERE id = ?`,
    ),
    updateSeriesMagazineKey: db.prepare(
      `UPDATE series
       SET magazine_key = COALESCE(magazine_key, ?),
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
    // edition_id も MADB 由来 edition に貼り替える。
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

type AuthorRef = {
  qid: string | null;
  name: string;
  altNames: string[];
  mangakaId: number | null;
};

/** 1 record を upsert。 fetch-ndl の upsertVolume と同等の責務。 */
function upsertVolume(db: DB, author: AuthorRef, rec: MadbRec): void {
  const titleForKey = rec.title ?? rec.isbn13;
  const seriesKey = buildSeriesKey(titleForKey, {
    qid: author.qid,
    name: author.name,
  });
  const seriesDisplay = baseTitle(titleForKey);

  let editionType: EditionType = classifyEdition(rec.title ?? "");
  const volumeNumber = rec.title ? extractVolumeNumber(rec.title) : null;
  // Task 1: 巻番号が抽出できない record は本編 series でないことが多い
  // (= 関連書籍 / セット商品 / ガイドブック / 全巻パック)。 標準 edition
  // (= type=standard) に混ぜると vol1 に集約されて誤集計になるため、
  // edition.type='other' に分離する。 既に classifyEdition が "完全版"
  // 等を識別している場合 (= editionType !== "standard") は触らない。
  if (volumeNumber === null && editionType === "standard") {
    editionType = "other";
  }
  const releaseDate = normalizeReleaseDate(rec.datePublished);
  const issuedYear =
    releaseDate && /^\d{4}/.test(releaseDate) ? Number(releaseDate.slice(0, 4)) : null;

  // Task 2: publisher literal を 「漢字　∥　カナ」 から漢字だけ抽出。
  // Task 3: 同様に magazine literal の漢字部分のみ取る。
  const publisherName = splitMadbLiteral(rec.publisher);
  const magazineName = splitMadbLiteral(rec.magazine);

  const stmts = getStmts(db);
  const masters = getMasters();
  const publisherKey =
    publisherName !== null
      ? (masters.publisher.get(publisherName.normalize("NFKC")) ?? null)
      : null;
  const magazineKey =
    magazineName !== null
      ? (masters.magazine.get(magazineName.normalize("NFKC")) ?? null)
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

  // ===== series_authors 紐付け (mangaka_id があるときのみ) =====
  if (author.mangakaId !== null) {
    stmts.insertSeriesAuthor.run(seriesId, author.mangakaId, "writer_artist");
  }

  // Task 2/3: series.publisher_key / magazine_key を master 解決値で埋める。
  // 既存値がある場合は COALESCE で touch しない (= 別 record で先に設定
  // された値を新しい record で上書きしない)。
  if (publisherKey !== null) {
    stmts.updateSeriesPublisherKey.run(publisherKey, seriesId);
  }
  if (magazineKey !== null) {
    stmts.updateSeriesMagazineKey.run(magazineKey, seriesId);
  }

  // ===== edition upsert =====
  const existingEdition = stmts.selectEdition.get(seriesId, editionType) as
    | { id: number; year_started: number | null; year_ended: number | null }
    | undefined;

  let editionId: number;
  if (existingEdition) {
    editionId = existingEdition.id;
    // Task 2: imprint には publisher 漢字部分のみ (= ∥ カナ部分は除外)
    if (publisherName) {
      stmts.updateEditionImprint.run(publisherName, editionId);
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
    // editions.label は NOT NULL なので EDITION_LABELS の固定文字列を使う。
    // Task 2: imprint には publisher 漢字部分のみ (= ∥ カナ部分は除外)
    const info = stmts.insertEdition.run(
      seriesId,
      editionType,
      EDITION_LABELS[editionType],
      publisherName,
      issuedYear,
      issuedYear,
    );
    editionId = Number(info.lastInsertRowid);
  }

  // ===== volume upsert (= 既存 NDL volume があれば MADB で上書き) =====
  // volumes.number は NOT NULL なので、 タイトルから抽出できなかった
  // ケース (= "総集編" / "外伝" 等) は 1 でフォールバック + is_extra=1 で
  // 識別。 fetch-ndl と同じ運用。
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
    magazine: rec.magazine,
    datePublished: rec.datePublished,
  });
}

/** mangaka を解決 (= --qid / --name / --all で異なる経路) */
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
      console.warn(
        `[warn] qid=${args.qid} not found in DB.mangaka; falling back to bare name from CLI is not supported. exit.`,
      );
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

async function processAuthor(
  db: DB,
  author: ResolvedAuthor,
  args: Args,
): Promise<{ inserted: number; updated: number; skipped: number }> {
  console.log(`[fetch] ${author.display}`);

  // primary name を first attempt、 alt_names は fallback として連結試行。
  // 6 作家 probe 結果 (= 諫山創 89 件 / 浦沢直樹 328 件) は primary だけで
  // 十分取れることが確認済。 alt_names は珍しい表記揺れの fallback。
  const allNames = [author.name, ...author.altNames];
  const seenIsbns = new Set<string>();
  const records: MadbRec[] = [];

  for (const name of allNames) {
    const r = await fetchMadbForName(name, args.includeOriginalAuthor);
    if (!r.ok) {
      console.warn(`  [error] name="${name}": ${r.error}`);
      continue;
    }
    let added = 0;
    for (const b of r.bindings) {
      const rec = normalizeBinding(b);
      if (!rec) continue;
      if (seenIsbns.has(rec.isbn13)) continue;
      seenIsbns.add(rec.isbn13);
      records.push(rec);
      added++;
    }
    console.log(
      `  [ok] name="${name}" ${r.bindings.length} bindings → ${added} new ISBN13s`,
    );
    await sleep(REQUEST_INTERVAL_MS);
  }

  // raw dump
  fs.mkdirSync(RAW_DIR, { recursive: true });
  const dumpPath = path.join(
    RAW_DIR,
    `${(author.qid ?? author.name).replace(/[^A-Za-z0-9_.-]/g, "_")}.json`,
  );
  fs.writeFileSync(
    dumpPath,
    JSON.stringify({ author: author.display, records }, null, 2),
    "utf8",
  );

  // DB 投入
  let inserted = 0;
  let updated = 0;
  let skipped = 0;
  tx(db, () => {
    const stmts = getStmts(db);
    for (const rec of records) {
      try {
        const before = stmts.selectVolume.get(rec.isbn13);
        upsertVolume(db, author, rec);
        if (before) updated++;
        else inserted++;
      } catch (err) {
        skipped++;
        console.warn(
          `  [skip] isbn=${rec.isbn13}: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
    }
  });
  console.log(
    `  [db] ${records.length} records → inserted=${inserted} updated=${updated} skipped=${skipped}`,
  );
  return { inserted, updated, skipped };
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  if (!args.qid && !args.name && !args.all) {
    console.error(
      "usage: fetch-madb --qid Q1234 | --name 'X' | --all [--limit N] [--include-adult] [--include-original-author]",
    );
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
    `[fetch-madb] start: ${authors.length} mangaka, includeOriginalAuthor=${args.includeOriginalAuthor}`,
  );

  const totals = { inserted: 0, updated: 0, skipped: 0 };
  for (const author of authors) {
    const r = await processAuthor(db, author, args);
    totals.inserted += r.inserted;
    totals.updated += r.updated;
    totals.skipped += r.skipped;
  }

  console.log(
    `\n[fetch-madb] done: total inserted=${totals.inserted} updated=${totals.updated} skipped=${totals.skipped}`,
  );
  console.log(`  raw dumps in .cache/madb/`);
  db.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

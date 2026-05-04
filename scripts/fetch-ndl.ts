/**
 * 国立国会図書館サーチ (NDLサーチ) の SRU API から、指定漫画家の作品を取得して
 * SQLite に投入する。Phase 1 のメインフェッチャ。
 *
 * 使い方:
 *   npm run fetch:ndl -- --qid Q193300                    # 高橋留美子（QID指定・DB紐付け可）
 *   npm run fetch:ndl -- --name "高橋留美子"               # 名前のみ（QID無し許容）
 *   npm run fetch:ndl -- --qid Q193300 --max-pages 3       # 最大 3 ページに制限
 *   npm run fetch:ndl -- --qid Q193300 --include-adult     # adult-credit も無視せず取得
 *
 * SRU API:
 *   GET https://ndlsearch.ndl.go.jp/api/sru
 *     ?operation=searchRetrieve
 *     &version=1.2
 *     &recordSchema=dcndl
 *     &recordPacking=xml
 *     &query=creator="高橋留美子" AND ndc="726"
 *     &startRecord=1
 *     &maximumRecords=200
 *
 * 1 ページ最大 200 件 (NDL 仕様)。漫画家あたり通常 1〜3 ページで完結。
 * レート制限: NDL は明示制限を公開していないが、礼儀として 1 req/sec。
 *
 * Amazon ToS 観点: mangaka.has_adult_credit=true の作家はデフォルトでスキップ。
 * 取得した個々のレコードについては Phase 4 (成人判定) で score 付け。
 */
import "./_env";
import fs from "node:fs";
import path from "node:path";
import { XMLParser } from "fast-xml-parser";
import {
  type EditionType,
  EDITION_LABELS,
  baseTitle,
  buildCreatorClause,
  buildSeriesKey,
  classifyEdition,
  escapeCql,
  extractVolumeNumber,
  normalizeCreatorName,
  normalizeIsbn13,
  normalizeReleaseDate,
  toLccCreatorForm,
} from "../lib/edition";
import type { Statement as BSStatement } from "better-sqlite3";
import { openDb, recordSource, tx, type DB } from "./_db";

type Stmt = BSStatement<unknown[], unknown>;

const ENDPOINT = "https://ndlsearch.ndl.go.jp/api/sru";
const PAGE_SIZE = 200;
const REQUEST_INTERVAL_MS = 1100;
const MAX_RETRIES = 4;
const MAX_PAGES_DEFAULT = 5;

const CSV_PATH = path.join(process.cwd(), "data", "seed", "mangaka.csv");
const RAW_DIR = path.join(process.cwd(), ".cache", "ndl");

type Args = {
  qid: string | null;
  name: string | null;
  maxPages: number;
  includeAdult: boolean;
};

function parseArgs(argv: string[]): Args {
  const out: Args = {
    qid: null,
    name: null,
    maxPages: MAX_PAGES_DEFAULT,
    includeAdult: false,
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
    } else if (a === "--max-pages" && next) {
      out.maxPages = Number(next);
      i++;
    } else if (a === "--include-adult") {
      out.includeAdult = true;
    }
  }
  return out;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

type CsvRow = {
  qid: string;
  name: string;
  alt_names: string[]; // pipe-separated → array
  has_adult_credit: string;
};

function lookupCsv(qidOrName: { qid?: string; name?: string }): CsvRow | null {
  if (!fs.existsSync(CSV_PATH)) return null;
  const text = fs.readFileSync(CSV_PATH, "utf8");
  const lines = text.split(/\r?\n/);
  const header = lines[0]?.split(",") ?? [];
  const idx = (k: string) => header.indexOf(k);
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i];
    if (!line) continue;
    // 簡易パース（CSV のクオート対応は import-mangaka-csv 側に集約）
    const cols = line.split(",");
    const altRaw = cols[idx("alt_names")] ?? "";
    const row: CsvRow = {
      qid: cols[idx("qid")] ?? "",
      name: cols[idx("name")] ?? "",
      alt_names: altRaw.split("|").map((s) => s.trim()).filter(Boolean),
      has_adult_credit: cols[idx("has_adult_credit")] ?? "false",
    };
    if (qidOrName.qid && row.qid === qidOrName.qid) return row;
    if (qidOrName.name && row.name === qidOrName.name) return row;
  }
  return null;
}

async function callOnce(query: string, startRecord: number): Promise<string> {
  const url = new URL(ENDPOINT);
  url.searchParams.set("operation", "searchRetrieve");
  url.searchParams.set("version", "1.2");
  url.searchParams.set("recordSchema", "dcndl");
  url.searchParams.set("recordPacking", "xml");
  url.searchParams.set("startRecord", String(startRecord));
  url.searchParams.set("maximumRecords", String(PAGE_SIZE));
  url.searchParams.set("query", query);

  const res = await fetch(url, {
    headers: {
      "User-Agent":
        "MANGAL-DataFetch/0.1 (+https://github.com/shuichi0725-cmyk/MANGAL)",
      Accept: "application/xml",
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`NDL HTTP ${res.status}: ${body.slice(0, 300)}`);
  }
  return await res.text();
}

async function call(query: string, startRecord: number): Promise<string> {
  let lastErr: unknown;
  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await callOnce(query, startRecord);
    } catch (err) {
      lastErr = err;
      const msg = err instanceof Error ? err.message : String(err);
      const is429 = /HTTP 429/.test(msg);
      const isHostBlocked = /HTTP 403/.test(msg) && /allowlist/i.test(msg);
      const retriable =
        is429 ||
        /HTTP 5\d\d/.test(msg) ||
        /timeout|ETIMEDOUT|ECONNRESET|fetch failed/i.test(msg);
      // H5: 403 "Host not in allowlist" は IP/Referer の構造的問題なので
      // 即時 fail。延々リトライしても復帰しないし NDL 側に余計な負荷。
      if (isHostBlocked) break;
      if (!retriable || attempt === MAX_RETRIES) break;
      // H5: 429 はレート制限なので通常のバックオフより長くクールダウン。
      // 30s, 60s, 120s, 240s と倍々で、4回失敗で諦める。
      const delay = is429
        ? 30000 * 2 ** (attempt - 1)
        : 2000 * 2 ** (attempt - 1);
      console.warn(
        `  attempt ${attempt} failed: ${msg}; retrying in ${delay}ms${is429 ? " (429 cooldown)" : ""}`,
      );
      await sleep(delay);
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error(String(lastErr));
}

/** dcndl レスポンスから 1 レコード分を取り出した中間構造 */
type NdlRec = {
  isbn13: string;
  title: string;            // 個別巻のタイトル（dcterms:title）
  seriesTitle: string | null; // dcndl:seriesTitle（あればシリーズ束ねの主情報源）
  partTitle: string | null;   // dcndl:partTitle（巻ごとのサブタイトル）
  titleKana: string | null;   // dcndl:transcription（読みがな、M6 で使用）
  // dcndl:edition / dcndl:editionStatement 等。「新装版」「完全版」が
  // dcterms:title には入らずこちら側にだけ来る場合があるため抽出。
  edition: string | null;
  // dcndl:volume — NDL が独立フィールドで巻番号を持っている。文字列なのに
  // 数値化できれば extractVolumeNumber(title) より信頼できる。
  volumeRaw: string | null;
  creators: string[];
  publisher: string | null;
  issued: string | null;      // YYYY-MM-DD or YYYY-MM or YYYY
  ndc: string | null;
  rawJson: unknown;
};

function asArray<T>(v: T | T[] | undefined): T[] {
  if (v === undefined || v === null) return [];
  return Array.isArray(v) ? v : [v];
}

function pickText(node: unknown): string | null {
  if (node === null || node === undefined) return null;
  if (typeof node === "string") return node.trim() || null;
  if (typeof node === "number") return String(node);
  if (typeof node === "object") {
    const v = (node as Record<string, unknown>)["#text"];
    if (typeof v === "string") return v.trim() || null;
    if (typeof v === "number") return String(v);
  }
  return null;
}

function extractIsbn13FromIdentifiers(idNodes: unknown[]): string | null {
  for (const n of idNodes) {
    const obj = n as Record<string, unknown> | string | undefined;
    if (typeof obj === "string") {
      const isbn = normalizeIsbn13(obj);
      if (isbn) return isbn;
      continue;
    }
    if (!obj) continue;
    const xsiType = (obj["@_xsi:type"] ?? obj["@_type"] ?? "") as string;
    if (typeof xsiType === "string" && /ISBN/i.test(xsiType)) {
      const txt = pickText(obj);
      const isbn = normalizeIsbn13(txt ?? "");
      if (isbn) return isbn;
    }
  }
  // フォールバック: type 指定が無い identifier も試す
  for (const n of idNodes) {
    const txt = pickText(n);
    if (!txt) continue;
    const isbn = normalizeIsbn13(txt);
    if (isbn) return isbn;
  }
  return null;
}

function extractCreators(creatorNodes: unknown[]): string[] {
  const out: string[] = [];
  for (const n of creatorNodes) {
    if (typeof n === "string") {
      out.push(n.trim());
      continue;
    }
    const text = pickText(n);
    if (text) out.push(text);
    // foaf:Agent / dcndl:Person 構造内の foaf:name
    if (typeof n === "object" && n !== null) {
      const obj = n as Record<string, unknown>;
      for (const v of Object.values(obj)) {
        if (typeof v === "object" && v !== null) {
          const nameVal = (v as Record<string, unknown>)["foaf:name"] ?? (v as Record<string, unknown>).name;
          const t = pickText(nameVal);
          if (t) out.push(t);
        }
      }
    }
  }
  return Array.from(new Set(out.filter(Boolean)));
}

// 診断: 最初の数レコードの BibResource フィールド名一覧を **プロセス全体で**
// 一度だけログ出力する。parseRecords がページ毎に呼ばれてもここで通算カウント
// するため重複ダンプを避ける。NDL_DEBUG_KEYS=0 で無効化。
const DEBUG_KEY_LIMIT =
  process.env.NDL_DEBUG_KEYS === "0" ? 0 : 3;
let debugKeysDumped = 0;

function parseRecords(xml: string): { total: number; recs: NdlRec[] } {
  const parser = new XMLParser({
    ignoreAttributes: false,
    attributeNamePrefix: "@_",
    removeNSPrefix: false,
    parseTagValue: false,
    trimValues: true,
  });
  const json = parser.parse(xml) as Record<string, unknown>;

  const resp = (json["searchRetrieveResponse"] ?? json) as Record<string, unknown>;
  const total = Number(resp["numberOfRecords"] ?? 0);
  const records = (resp["records"] as Record<string, unknown> | undefined) ?? {};
  const recordList = asArray((records["record"] as unknown) as unknown);

  const out: NdlRec[] = [];
  // Issue 1: NDL は同一 ISBN について複数の目録レコード (NDL/NACSIS/JLA 等)
  // を返すことがある。タイトル文字列が微妙に違って、後段の classifyEdition
  // で edition_type がブレる結果 [edition-rebind] 警告が同じ ISBN について
  // 何度も出る。レスポンス内で先勝ち dedup する。
  const seenIsbn = new Set<string>();
  for (const r of recordList) {
    const rd = (r as Record<string, unknown>)["recordData"] as
      | Record<string, unknown>
      | undefined;
    if (!rd) continue;
    const rdf = (rd["rdf:RDF"] ?? rd["RDF"]) as Record<string, unknown> | undefined;
    if (!rdf) continue;
    const bib = (rdf["dcndl:BibResource"] ?? rdf["BibResource"]) as
      | Record<string, unknown>
      | Record<string, unknown>[]
      | undefined;
    if (!bib) continue;
    const bibs = Array.isArray(bib) ? bib : [bib];
    // H3: dcndl は record 内に Work レベルと Manifestation レベルの BibResource
    // を両方入れることがある。Work には ISBN が無く、Manifestation にだけ
    // ISBN がある。ISBN の有無で Manifestation を判定し、Manifestation だけ
    // 採用する。両方 ISBN を持つ場合は最初の 1 件のみ（複製を避ける）。
    let manifestationProcessed = false;
    for (const b of bibs) {
      if (manifestationProcessed) break;

      // 診断ダンプ（プロセス全体で先頭 3 件のみ・行頭から console.log で出す）
      if (debugKeysDumped < DEBUG_KEY_LIMIT) {
        const keys = Object.keys(b).slice(0, 60);
        // 既存の `process.stdout.write(...)` 行と混ざらないよう先頭に \n を付加
        console.log(
          `\n[debug] BibResource[${debugKeysDumped + 1}] keys: ${keys.join(", ")}`,
        );
        debugKeysDumped++;
      }

      const titleRaw =
        pickText(b["dcterms:title"] ?? b["dc:title"] ?? b["title"]) ?? "";
      if (!titleRaw) continue;

      const idNodes = asArray(
        (b["dcterms:identifier"] ?? b["dc:identifier"] ?? b["identifier"]) as unknown,
      );
      const isbn = extractIsbn13FromIdentifiers(idNodes);
      if (!isbn) continue; // ISBN 無しは Work レベルか UI 用としては不要
      if (seenIsbn.has(isbn)) {
        // 同一レスポンス内で重複した ISBN は最初の 1 件だけ採用。
        // 同 record 内でなく別 record に同 ISBN が入る (典型: NDL 蔵書版と
        // 全国書誌版で同じ書籍を別々に登録) ケースに対応。
        manifestationProcessed = true;
        break;
      }
      seenIsbn.add(isbn);

      const creatorNodes = asArray(
        (b["dcterms:creator"] ?? b["dc:creator"] ?? b["creator"]) as unknown,
      );
      const creators = extractCreators(creatorNodes);

      const publisherNode = b["dcterms:publisher"] ?? b["dc:publisher"] ?? b["publisher"];
      let publisherText = pickText(publisherNode);
      if (!publisherText && typeof publisherNode === "object" && publisherNode !== null) {
        for (const v of Object.values(publisherNode as Record<string, unknown>)) {
          const t = pickText(
            (v as Record<string, unknown>)?.["foaf:name"] ?? v,
          );
          if (t) {
            publisherText = t;
            break;
          }
        }
      }

      const issuedRaw = pickText(
        b["dcterms:issued"] ?? b["dc:issued"] ?? b["issued"] ?? b["dcterms:date"],
      );
      const issued = normalizeReleaseDate(issuedRaw);

      const subjectNodes = asArray((b["dcterms:subject"] ?? b["dc:subject"]) as unknown);
      let ndc: string | null = null;
      for (const s of subjectNodes) {
        const t = pickText(s);
        if (t && /^\d{3}(\.\d+)?$/.test(t)) {
          ndc = t;
          break;
        }
      }

      // H1: dcndl:seriesTitle / partTitle / titleTranscription を抽出。
      // seriesTitle が取れる場合はそちらが「うる星やつら〔新装版〕」のような
      // シリーズ束ねの主情報源になる。partTitle は巻のサブタイトル。
      const seriesTitle = pickText(
        b["dcndl:seriesTitle"] ?? b["seriesTitle"],
      );
      const partTitle = pickText(b["dcndl:partTitle"] ?? b["partTitle"]);
      // M6: titleTranscription はヨミガナ（series.title_kana の素）。
      const titleKana = pickText(
        b["dcndl:titleTranscription"] ??
          b["titleTranscription"] ??
          b["dcndl:transcription"],
      );

      // eds=1 fix: edition 文字列は dcterms:title に入らないことが多く、
      // 別フィールドに格納されている。候補名を順に試す。NDL の dcndl は
      // バージョンによってフィールド名が揺れるので 5 系統見る。
      // 後段の classifyEdition がここを文字列マッチして 完全版 / 新装版 等
      // を識別する。
      const edition =
        pickText(b["dcndl:edition"]) ??
        pickText(b["dcndl:editionStatement"]) ??
        pickText(b["dcterms:hasFormat"]) ??
        pickText(b["edition"]) ??
        pickText(b["dc:edition"]);

      // dcndl:volume は巻番号の独立フィールド。"5" "11" "上" "下" "別巻"
      // 等の文字列が入ることがあるので生のまま保持し、後段で number 化。
      const volumeRaw = pickText(b["dcndl:volume"]);

      out.push({
        isbn13: isbn,
        title: titleRaw,
        seriesTitle,
        partTitle,
        titleKana,
        edition,
        volumeRaw,
        creators,
        publisher: publisherText,
        issued,
        ndc,
        rawJson: b,
      });
      manifestationProcessed = true;
    }
  }
  return { total, recs: out };
}

/**
 * L1: 大量レコードのループで毎回 db.prepare() するとパース回数が嵩む
 * （better-sqlite3 内部キャッシュはあるが、明示で持ち回したほうが速いし
 * 何のステートメントが使われているかも一覧しやすい）。一度だけ作って
 * 使い回す。1 度だけ呼ばれる関数の中で持ってもいい程度の数だが、
 * バッチ実行を見越して module-level に出す。
 */
type VolumeStmts = {
  selectSeries: Stmt;
  updateSeriesYear: Stmt;
  updateSeriesYearWhenEmpty: Stmt;
  updateSeriesKana: Stmt;
  insertSeries: Stmt;
  insertSeriesAuthor: Stmt;
  selectEdition: Stmt;
  updateEditionImprint: Stmt;
  updateEditionYear: Stmt;
  insertEdition: Stmt;
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
    updateSeriesYear: db.prepare(
      `UPDATE series
       SET year_started = ?, year_ended = ?,
           updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
       WHERE id = ?`,
    ),
    updateSeriesYearWhenEmpty: db.prepare(
      `UPDATE series
       SET year_started = ?, year_ended = ?,
           updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
       WHERE id = ?`,
    ),
    updateSeriesKana: db.prepare(
      `UPDATE series
       SET title_kana = COALESCE(title_kana, ?),
           updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
       WHERE id = ?`,
    ),
    insertSeries: db.prepare(
      `INSERT INTO series (series_key, title, title_kana, year_started, year_ended)
       VALUES (?, ?, ?, ?, ?)`,
    ),
    insertSeriesAuthor: db.prepare(
      `INSERT OR IGNORE INTO series_authors (series_id, mangaka_id, role)
       VALUES (?, ?, ?)`,
    ),
    selectEdition: db.prepare(
      "SELECT id, year_started, year_ended FROM editions WHERE series_id = ? AND type = ?",
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
    insertEdition: db.prepare(
      `INSERT INTO editions (series_id, type, label, imprint, year_started, year_ended)
       VALUES (?, ?, ?, ?, ?, ?)`,
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
       SET number       = ?,
           is_extra     = ?,
           release_date = COALESCE(release_date, ?),
           updated_at   = strftime('%Y-%m-%dT%H:%M:%SZ','now')
       WHERE isbn13 = ?`,
    ),
  };
  cachedStmts = { db, stmts };
  return stmts;
}

/** SQLite に upsert する (mangaka_id は既知) */
function upsertVolume(
  db: DB,
  mangakaId: number,
  authorRef: { qid: string | null; name: string },
  rec: NdlRec,
): { seriesId: number; editionId: number; isbn: string; rebound: boolean } {
  // H1: seriesTitle が取れたら baseTitle より先にそちらを優先する。
  // dcndl:seriesTitle = "うる星やつら〔新装版〕" のように既にシリーズ束ね用に
  // 整理されているケースが多く、自前の baseTitle 文字列削りより信頼できる。
  // eds=1 fix: 最も重要な edition 情報源は dcndl:edition フィールド
  // （「新装版」等が NDL の独立フィールドに格納されている）。これを最初に置く。
  const editionSourceText = [
    rec.edition,
    rec.title,
    rec.seriesTitle,
    rec.partTitle,
  ]
    .filter(Boolean)
    .join(" ");
  const editionType: EditionType = classifyEdition(editionSourceText);

  // C2 + H1 fix: シリーズキーは「seriesTitle (or baseTitle(title))」+ 著者識別子
  const titleForKey = rec.seriesTitle ?? rec.title;
  const seriesKey = buildSeriesKey(titleForKey, {
    qid: authorRef.qid,
    name: authorRef.name,
  });
  const seriesDisplay = rec.seriesTitle
    ? baseTitle(rec.seriesTitle)
    : baseTitle(rec.title);

  const issuedYear =
    rec.issued && /^\d{4}/.test(rec.issued) ? Number(rec.issued.slice(0, 4)) : null;

  // L1: prepared statements を使い回す
  const stmts = getStmts(db);

  // series upsert
  // H4: year_started 更新は「standard edition の年」を優先採用。
  const existingSeries = stmts.selectSeries.get(seriesKey) as
    | { id: number; year_started: number | null; year_ended: number | null }
    | undefined;
  let seriesId: number;
  if (existingSeries) {
    seriesId = existingSeries.id;
    if (issuedYear && editionType === "standard") {
      const newStart =
        existingSeries.year_started === null
          ? issuedYear
          : Math.min(existingSeries.year_started, issuedYear);
      const newEnd =
        existingSeries.year_ended === null
          ? issuedYear
          : Math.max(existingSeries.year_ended, issuedYear);
      stmts.updateSeriesYear.run(newStart, newEnd, seriesId);
    } else if (issuedYear && existingSeries.year_started === null) {
      // standard が一切来ていない暫定値として埋める（後で standard が来たら上書き）
      stmts.updateSeriesYearWhenEmpty.run(issuedYear, issuedYear, seriesId);
    }
    // M6: title_kana を取れたら埋める（既存値があれば残す）
    if (rec.titleKana) {
      stmts.updateSeriesKana.run(rec.titleKana, seriesId);
    }
  } else {
    const info = stmts.insertSeries.run(
      seriesKey,
      seriesDisplay,
      rec.titleKana,
      issuedYear,
      issuedYear,
    );
    seriesId = Number(info.lastInsertRowid);
  }

  // series_authors 紐付け
  // H2: NDL の creator 表記揺れチェック（実害は出ないが将来の差分検知用に保留）。
  const targetNorm = normalizeCreatorName(authorRef.name);
  const matched = rec.creators.some(
    (c) => normalizeCreatorName(c) === targetNorm,
  );
  void matched; // 現状は warning に使わず、CQL ヒット事実を尊重して紐付け
  stmts.insertSeriesAuthor.run(seriesId, mangakaId, "writer_artist");

  // edition upsert
  const existingEdition = stmts.selectEdition.get(seriesId, editionType) as
    | { id: number; year_started: number | null; year_ended: number | null }
    | undefined;
  let editionId: number;
  if (existingEdition) {
    editionId = existingEdition.id;
    if (rec.publisher) {
      stmts.updateEditionImprint.run(rec.publisher, editionId);
    }
    if (issuedYear) {
      const newStart =
        existingEdition.year_started === null
          ? issuedYear
          : Math.min(existingEdition.year_started, issuedYear);
      const newEnd =
        existingEdition.year_ended === null
          ? issuedYear
          : Math.max(existingEdition.year_ended, issuedYear);
      stmts.updateEditionYear.run(newStart, newEnd, editionId);
    }
  } else {
    const info = stmts.insertEdition.run(
      seriesId,
      editionType,
      EDITION_LABELS[editionType],
      rec.publisher,
      issuedYear,
      issuedYear,
    );
    editionId = Number(info.lastInsertRowid);
  }

  // volume upsert (H6: silent rebind 禁止)
  // 巻番号は dcndl:volume フィールド最優先 → title からの推測 → 0 (外伝扱い)
  // dcndl:volume は "5" "上" "下" "別巻" などの文字列なので数値だけ抽出。
  const volFromField = rec.volumeRaw
    ? Number((rec.volumeRaw.match(/\d{1,3}/) ?? [""])[0])
    : NaN;
  const number =
    Number.isFinite(volFromField) && volFromField > 0
      ? volFromField
      : (extractVolumeNumber(rec.title) ?? 0);
  const isExtra = number === 0 ? 1 : 0;
  const existingVol = stmts.selectVolume.get(rec.isbn13) as
    | { edition_id: number }
    | undefined;

  let rebound = false;
  if (!existingVol) {
    stmts.insertVolume.run(editionId, rec.isbn13, number, isExtra, rec.issued);
  } else if (existingVol.edition_id === editionId) {
    stmts.updateVolume.run(number, isExtra, rec.issued, rec.isbn13);
  } else {
    rebound = true; // edition 移動は黙ってやらない
  }

  return { seriesId, editionId, isbn: rec.isbn13, rebound };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.qid && !args.name) {
    console.error("Usage: npm run fetch:ndl -- --qid <QID> | --name <作家名>");
    process.exit(1);
  }

  const csvRow = lookupCsv({
    qid: args.qid ?? undefined,
    name: args.name ?? undefined,
  });
  const name = args.name ?? csvRow?.name ?? null;
  const qid = args.qid ?? csvRow?.qid ?? null;
  if (!name) {
    console.error("作家名が解決できません。--name を直接指定してください。");
    process.exit(1);
  }
  if (csvRow?.has_adult_credit === "true" && !args.includeAdult) {
    console.log(
      `[skip] ${qid ?? ""} ${name} は has_adult_credit=true のためスキップ。--include-adult で取得可。`,
    );
    return;
  }

  const db = openDb();

  // mangaka を SQLite に upsert（QID あり）
  let mangakaId: number;
  if (qid) {
    const existing = db.prepare("SELECT id FROM mangaka WHERE qid = ?").get(qid) as
      | { id: number }
      | undefined;
    if (existing) {
      mangakaId = existing.id;
    } else {
      const info = db
        .prepare(
          `INSERT INTO mangaka (qid, name, has_adult_credit)
           VALUES (?, ?, ?)`,
        )
        .run(qid, name, csvRow?.has_adult_credit === "true" ? 1 : 0);
      mangakaId = Number(info.lastInsertRowid);
    }
  } else {
    // QID 無しは便宜上 "noqid:<name>" を qid 列に
    const synthetic = `noqid:${name}`;
    const existing = db.prepare("SELECT id FROM mangaka WHERE qid = ?").get(synthetic) as
      | { id: number }
      | undefined;
    if (existing) mangakaId = existing.id;
    else {
      const info = db
        .prepare(`INSERT INTO mangaka (qid, name) VALUES (?, ?)`)
        .run(synthetic, name);
      mangakaId = Number(info.lastInsertRowid);
    }
  }

  fs.mkdirSync(RAW_DIR, { recursive: true });
  const probesDir = path.join(RAW_DIR, "probes");
  fs.mkdirSync(probesDir, { recursive: true });

  // C3 + C4: 作家名と alt_names を CQL でエスケープして OR 結合（厳密版）。
  // ただし NDL の CQL 実装は環境により挙動が違うので、0 件返ってきた時に
  // **異なる検索戦略**を順に試す（同じクエリの引用符違いではない）。
  //
  //   1. strict   : (creator="A" OR creator="B"...) AND ndc="726"
  //                  — 別名含む厳密一致
  //   2. any-token: creator any "primary" AND ndc="726"
  //                  — CQL `any` 演算子。トークン分割マッチ
  //   3. lcc-form : creator="姓, 名" AND ndc="726"
  //                  — NDL/MARC の姓カンマ名形式
  //   4. dc-prefix: dc.creator="primary" AND ndc="726"
  //                  — DC 名前空間を明示
  //   5. no-ndc   : creator="primary"
  //                  — 漫画以外も入る最後の砦（採用時 warn）
  //
  // 各 variant の応答 XML は .cache/ndl/probes/ に残してデバッグ可能に。
  // 1 個失敗（CQL 構文エラー等）しても次の variant を試す。host blocked
  // のような構造的エラーは即 abort（同 host で他 variant 試しても無駄）。
  const altNames = csvRow?.alt_names ?? [];
  const allNames = [name, ...altNames];

  type VariantSpec = { name: string; sql: string; warn?: boolean };
  const candidates: VariantSpec[] = [
    {
      name: "strict",
      sql: `${buildCreatorClause(allNames)} AND ndc="726"`,
    },
    {
      name: "any-token",
      sql: `creator any "${escapeCql(name)}" AND ndc="726"`,
    },
    {
      name: "lcc-form",
      sql: `creator="${escapeCql(toLccCreatorForm(name))}" AND ndc="726"`,
    },
    {
      name: "dc-prefix",
      sql: `dc.creator="${escapeCql(name)}" AND ndc="726"`,
    },
    {
      name: "no-ndc",
      sql: `creator="${escapeCql(name)}"`,
      warn: true,
    },
  ];

  const fileSafe = (s: string) => encodeURIComponent(s).replace(/%/g, "_");
  const probeStem = fileSafe(qid ?? `name-${name}`);

  let adoptedQuery = "";
  let adoptedXml: string | null = null;
  let adoptedTotal = 0;
  let adoptedVariant: VariantSpec | null = null;

  for (let i = 0; i < candidates.length; i++) {
    const v = candidates[i];
    if (i > 0) await sleep(REQUEST_INTERVAL_MS);
    process.stdout.write(`[ndl] probe ${v.name}: ${v.sql.slice(0, 100)} ... `);
    let xml: string;
    try {
      xml = await call(v.sql, 1);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.log(`FAILED: ${msg.slice(0, 200)}`);
      try {
        fs.writeFileSync(
          path.join(probesDir, `${probeStem}-${v.name}.error.txt`),
          `query: ${v.sql}\n\n${msg}\n`,
          "utf8",
        );
      } catch {
        // ignore disk error during diagnostic write
      }
      // host blocked / 5xx は同じ host への他 variant でも復帰しないので即 abort
      if (
        /Host not in allowlist/i.test(msg) ||
        /HTTP 5\d\d/.test(msg)
      ) {
        throw err;
      }
      // それ以外（CQL 4xx 等）は次 variant で挽回可能なので継続
      continue;
    }
    fs.writeFileSync(
      path.join(probesDir, `${probeStem}-${v.name}.xml`),
      xml,
      "utf8",
    );
    const { total } = parseRecords(xml);
    console.log(`${total} records`);
    if (total > 0) {
      adoptedQuery = v.sql;
      adoptedXml = xml;
      adoptedTotal = total;
      adoptedVariant = v;
      break;
    }
  }

  if (adoptedVariant === null || adoptedXml === null) {
    console.log(
      `[ndl] 全 ${candidates.length} variants で 0 件。NDL にデータが無い、` +
        `または NDL CQL 仕様が想定外。.cache/ndl/probes/ の応答 XML を確認。`,
    );
    db.close();
    return;
  }
  console.log(
    `[ndl] adopted: variant '${adoptedVariant.name}' (${adoptedTotal} records reported)`,
  );
  console.log(`       SQL: ${adoptedQuery}`);
  if (adoptedVariant.warn) {
    console.warn(
      `[ndl] ⚠ variant '${adoptedVariant.name}' は ndc=726 制約を外して` +
        `当てたため、漫画以外（小説・画集・評論・ガイドブック等）が混入する` +
        `可能性があります。Phase 4 (成人/ジャンル判定) でフィルタリング前提。`,
    );
  }

  const query = adoptedQuery; // 以降の page ループで使い回す
  // Issue 2: total は probe 時点の値を保持する。page ループで「最終ページが
  // 0 件」を返した瞬間に上書きされるのを防ぐ（NDL は超過 startRecord で
  // numberOfRecords=0 を返すことがある）。
  const totalReported = adoptedTotal;
  let fetched = 0;
  let inserted = 0;
  let reboundCount = 0;
  // Issue 1: クロスページの ISBN 重複も dedup する。parseRecords 側で
  // 同一レスポンス内の重複は弾いているが、ページをまたいで同じ ISBN が
  // 出ることもあるため belt-and-suspenders。
  const seenIsbnAcrossPages = new Set<string>();

  for (let page = 0; page < args.maxPages; page++) {
    const startRecord = page * PAGE_SIZE + 1;
    let xml: string;
    if (page === 0) {
      // 1 ページ目は variant probe で既に取得済みのものを再利用（API 節約）
      xml = adoptedXml;
      process.stdout.write(`[ndl] page 1 start=1 (reuse from probe)... `);
    } else {
      await sleep(REQUEST_INTERVAL_MS);
      process.stdout.write(`[ndl] page ${page + 1} start=${startRecord}... `);
      xml = await call(query, startRecord);
    }
    // R6: name に / 等が混じった場合の path 破壊を避けるため encode する
    fs.writeFileSync(
      path.join(RAW_DIR, `${probeStem}-p${page + 1}.xml`),
      xml,
      "utf8",
    );
    const { total: tot, recs } = parseRecords(xml);
    fetched += recs.length;
    console.log(
      `${recs.length} records (page reported total: ${tot}; running total: ${totalReported})`,
    );

    tx(db, () => {
      for (const rec of recs) {
        if (seenIsbnAcrossPages.has(rec.isbn13)) continue;
        seenIsbnAcrossPages.add(rec.isbn13);
        try {
          const r = upsertVolume(db, mangakaId, { qid, name }, rec);
          if (r.rebound) {
            reboundCount++;
            // H6: edition 切り替わりは silent rebind しない。
            // sources に new edition の存在を記録しつつ既存 row は据え置き。
            // 連発するとログを汚すので最初の 5 件だけ詳細表示し、後はカウンタ。
            if (reboundCount <= 5) {
              console.warn(
                `  [edition-rebind] ISBN=${rec.isbn13} 既存 edition と異なる分類。volumes 据え置き。`,
              );
            } else if (reboundCount === 6) {
              console.warn(
                `  [edition-rebind] (以後の rebind は省略・summary に総数を表示)`,
              );
            }
          }
          recordSource(db, "ndl", "volumes", rec.isbn13, rec.rawJson);
          inserted++;
        } catch (err) {
          console.warn(
            `  [skip] ${rec.isbn13} ${rec.title.slice(0, 30)}: ${
              err instanceof Error ? err.message : err
            }`,
          );
        }
      }
    });

    if (fetched >= totalReported || recs.length === 0) break;
  }

  console.log("\n=== fetch:ndl summary ===");
  console.log(`  作家       : ${name} (${qid ?? "no-qid"})`);
  console.log(`  total reported : ${totalReported}`);
  console.log(`  fetched    : ${fetched}`);
  console.log(`  upserted   : ${inserted} volumes`);
  console.log(`  rebinds    : ${reboundCount} (edition 分類が後から変わった ISBN)`);

  const seriesRows = db
    .prepare(
      `SELECT s.id, s.title, COUNT(DISTINCT e.id) AS eds, COUNT(DISTINCT v.id) AS vols
       FROM series s
       JOIN series_authors sa ON sa.series_id = s.id
       LEFT JOIN editions e ON e.series_id = s.id
       LEFT JOIN volumes v ON v.edition_id = e.id
       WHERE sa.mangaka_id = ?
       GROUP BY s.id
       ORDER BY vols DESC, s.title
       LIMIT 30`,
    )
    .all(mangakaId) as { id: number; title: string; eds: number; vols: number }[];

  console.log("\n=== series for this mangaka (top 30 by volume count) ===");
  for (const s of seriesRows) {
    console.log(`  #${s.id}\t${s.title}\teds=${s.eds}\tvols=${s.vols}`);
  }

  db.close();
}

main().catch((err) => {
  console.error("[fatal]", err);
  process.exit(1);
});

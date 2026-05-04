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
  extractVolumeNumber,
  normalizeIsbn13,
  normalizeReleaseDate,
} from "../lib/edition";
import { openDb, recordSource, tx, type DB } from "./_db";

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
      const retriable =
        /HTTP (429|5\d\d)/.test(msg) ||
        /timeout|ETIMEDOUT|ECONNRESET|fetch failed/i.test(msg);
      if (!retriable || attempt === MAX_RETRIES) break;
      const delay = 2000 * 2 ** (attempt - 1);
      console.warn(`  attempt ${attempt} failed: ${msg}; retrying in ${delay}ms`);
      await sleep(delay);
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error(String(lastErr));
}

/** dcndl レスポンスから 1 レコード分を取り出した中間構造 */
type NdlRec = {
  isbn13: string;
  title: string;
  creators: string[];
  publisher: string | null;
  issued: string | null; // YYYY-MM-DD or YYYY-MM or YYYY
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
    for (const b of bibs) {
      const titleRaw =
        pickText(b["dcterms:title"] ?? b["dc:title"] ?? b["title"]) ?? "";
      if (!titleRaw) continue;

      const idNodes = asArray(
        (b["dcterms:identifier"] ?? b["dc:identifier"] ?? b["identifier"]) as unknown,
      );
      const isbn = extractIsbn13FromIdentifiers(idNodes);
      if (!isbn) continue; // ISBN 無しは UI 用としては不要

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

      out.push({
        isbn13: isbn,
        title: titleRaw,
        creators,
        publisher: publisherText,
        issued,
        ndc,
        rawJson: b,
      });
    }
  }
  return { total, recs: out };
}

/** SQLite に upsert する (mangaka_id は既知) */
function upsertVolume(
  db: DB,
  mangakaId: number,
  authorRef: { qid: string | null; name: string },
  rec: NdlRec,
): { seriesId: number; editionId: number; isbn: string } {
  // C2 fix: タイトル単独だと同名異作家衝突するので必ず作家識別子を含める。
  const seriesKey = buildSeriesKey(rec.title, {
    qid: authorRef.qid,
    name: authorRef.name,
  });
  const editionType: EditionType = classifyEdition(rec.title);

  // series upsert
  const existingSeries = db
    .prepare("SELECT id FROM series WHERE series_key = ?")
    .get(seriesKey) as { id: number } | undefined;
  let seriesId: number;
  if (existingSeries) {
    seriesId = existingSeries.id;
    // 開始年は早い方で更新
    const issuedYear =
      rec.issued && /^\d{4}/.test(rec.issued) ? Number(rec.issued.slice(0, 4)) : null;
    if (issuedYear) {
      db.prepare(
        `UPDATE series
         SET year_started = MIN(COALESCE(year_started, 9999), ?),
             year_ended   = MAX(COALESCE(year_ended,   0),    ?)
         WHERE id = ?`,
      ).run(issuedYear, issuedYear, seriesId);
    }
  } else {
    const issuedYear =
      rec.issued && /^\d{4}/.test(rec.issued) ? Number(rec.issued.slice(0, 4)) : null;
    const info = db
      .prepare(
        `INSERT INTO series (series_key, title, year_started, year_ended)
         VALUES (?, ?, ?, ?)`,
      )
      .run(seriesKey, baseTitle(rec.title), issuedYear, issuedYear);
    seriesId = Number(info.lastInsertRowid);
  }

  // series_authors upsert
  db.prepare(
    `INSERT OR IGNORE INTO series_authors (series_id, mangaka_id, role)
     VALUES (?, ?, ?)`,
  ).run(seriesId, mangakaId, "writer_artist");

  // edition upsert
  const existingEdition = db
    .prepare("SELECT id FROM editions WHERE series_id = ? AND type = ?")
    .get(seriesId, editionType) as { id: number } | undefined;
  let editionId: number;
  if (existingEdition) {
    editionId = existingEdition.id;
    if (rec.publisher) {
      db.prepare(
        `UPDATE editions SET imprint = COALESCE(imprint, ?) WHERE id = ?`,
      ).run(rec.publisher, editionId);
    }
  } else {
    const info = db
      .prepare(
        `INSERT INTO editions (series_id, type, label, imprint)
         VALUES (?, ?, ?, ?)`,
      )
      .run(seriesId, editionType, EDITION_LABELS[editionType], rec.publisher);
    editionId = Number(info.lastInsertRowid);
  }

  // volume upsert
  const number = extractVolumeNumber(rec.title) ?? 0; // 0 はガイドブック等の特殊ケース
  const isExtra = number === 0 ? 1 : 0;
  db.prepare(
    `INSERT INTO volumes (edition_id, isbn13, number, is_extra, release_date)
     VALUES (?, ?, ?, ?, ?)
     ON CONFLICT(isbn13) DO UPDATE SET
       edition_id   = excluded.edition_id,
       number       = excluded.number,
       is_extra     = excluded.is_extra,
       release_date = COALESCE(volumes.release_date, excluded.release_date)`,
  ).run(editionId, rec.isbn13, number, isExtra, rec.issued);

  return { seriesId, editionId, isbn: rec.isbn13 };
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

  // C3 + C4 fix: 作家名と alt_names を CQL でエスケープして OR 結合。
  // alt_names が多い作家 (CLAMP 等) は将来分割クエリが必要だが、
  // とりあえずまとめて 1 クエリ。
  const altNames = csvRow?.alt_names ?? [];
  const allNames = [name, ...altNames];
  const creatorClause = buildCreatorClause(allNames);
  const query = `${creatorClause} AND ndc="726"`;
  console.log(`[ndl] query: ${query}`);

  let total = 0;
  let fetched = 0;
  let inserted = 0;
  let firstReq = true;

  for (let page = 0; page < args.maxPages; page++) {
    const startRecord = page * PAGE_SIZE + 1;
    if (!firstReq) await sleep(REQUEST_INTERVAL_MS);
    firstReq = false;

    process.stdout.write(`[ndl] page ${page + 1} start=${startRecord}... `);
    const xml = await call(query, startRecord);
    fs.writeFileSync(
      path.join(RAW_DIR, `${qid ?? `name-${name}`}-p${page + 1}.xml`),
      xml,
      "utf8",
    );
    const { total: tot, recs } = parseRecords(xml);
    total = tot;
    fetched += recs.length;
    console.log(
      `${recs.length} records (total reported: ${total})`,
    );

    tx(db, () => {
      for (const rec of recs) {
        try {
          upsertVolume(db, mangakaId, { qid, name }, rec);
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

    if (fetched >= total || recs.length === 0) break;
  }

  console.log("\n=== fetch:ndl summary ===");
  console.log(`  作家      : ${name} (${qid ?? "no-qid"})`);
  console.log(`  total reported: ${total}`);
  console.log(`  fetched   : ${fetched}`);
  console.log(`  upserted  : ${inserted} volumes`);

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

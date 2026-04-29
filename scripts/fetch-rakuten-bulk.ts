/**
 * mangaka.csv の全作家について楽天ブックスAPIをループして、
 * 結果を `.cache/rakuten/<qid>.json` に作家単位で保存する。
 *
 * 個別の `fetch-rakuten.ts` は (slug, title, author) ピンポイント用で、
 * こちらは網羅クロール用の上流。後続の `group-into-series.ts`（未着手）が
 * `.cache/rakuten/*.json` を読んでシリーズ集約 → YAML 草稿を吐く想定。
 *
 * 使い方:
 *   npm run fetch:rakuten:bulk                        # 全件（has_adult_credit=true は除外）
 *   npm run fetch:rakuten:bulk -- --limit 20          # 先頭 20 名だけ（動作確認用）
 *   npm run fetch:rakuten:bulk -- --start Q193300     # この QID から再開
 *   npm run fetch:rakuten:bulk -- --no-resume         # 既存キャッシュを無視して全件再取得
 *
 * 楽天 API レート制限: 1 req/sec / アプリID。安全側で 1.1s スリープ。
 * `--limit N` 無しで全件回すと 6000+ × ページ数 = 数時間〜半日のクロール。
 *
 * Amazon アソシエイト規約により、サイト掲載対象から成年向けは完全除外する。
 * このスクリプト段階で:
 *   1. mangaka.csv の has_adult_credit=true は最初から呼ばない
 *   2. booksGenreId=001001（漫画ルート）でリクエスト
 *   3. レスポンスのうち ADULT_GENRE_PREFIXES に該当するアイテムは捨てる
 */
import "./_env";
import fs from "node:fs";
import path from "node:path";

const ENDPOINT =
  "https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404";

const HITS = 30; // 楽天 API の 1 ページ最大値
const REQUEST_INTERVAL_MS = 1100;
const MAX_RETRIES = 4;
const MAX_PAGES_DEFAULT = 10; // 1作家あたり最大 30×10=300 件まで

// レディースコミック等の成年向けジャンル接頭辞（取得後にここで弾く）
const ADULT_GENRE_PREFIXES = [
  "001001012", // レディースコミック
  "001001014", // ティーンズラブコミック
];

const CACHE_DIR = path.join(process.cwd(), ".cache", "rakuten");
const CSV_PATH = path.join(process.cwd(), "data", "seed", "mangaka.csv");

type RakutenItem = {
  title?: string;
  subTitle?: string;
  seriesName?: string;
  seriesNameKana?: string;
  author?: string;
  authorKana?: string;
  publisherName?: string;
  isbn?: string;
  salesDate?: string;
  largeImageUrl?: string;
  mediumImageUrl?: string;
  smallImageUrl?: string;
  itemCaption?: string;
  booksGenreId?: string;
};

// formatVersion=2: フラット配列。{ Item: ... } 入れ子は v=1 の形式。
type RakutenResponse = {
  Items: RakutenItem[];
  count: number;
  page: number;
  pageCount: number;
};

type CachedAuthor = {
  qid: string;
  name: string;
  fetched_at: string;
  query_author: string;
  total_count: number;
  pages_fetched: number;
  dropped_adult: number;
  items: RakutenItem[];
};

type ParsedArgs = {
  limit: number | null;
  startQid: string | null;
  noResume: boolean;
  maxPages: number;
};

function parseArgs(argv: string[]): ParsedArgs {
  const out: ParsedArgs = {
    limit: null,
    startQid: null,
    noResume: false,
    maxPages: MAX_PAGES_DEFAULT,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = argv[i + 1];
    if (a === "--limit" && next) {
      out.limit = Number(next);
      i++;
    } else if (a === "--start" && next) {
      out.startQid = next;
      i++;
    } else if (a === "--max-pages" && next) {
      out.maxPages = Number(next);
      i++;
    } else if (a === "--no-resume") {
      out.noResume = true;
    }
  }
  return out;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

type CsvRow = {
  qid: string;
  name: string;
  has_adult_credit: string;
};

/**
 * 簡易 CSV パーサ。fetch-mangaka.ts の出力フォーマット
 *   qid,name,birth_year,death_year,alt_names,has_adult_credit
 * を前提に、ダブルクオート囲みのカンマ・改行を扱う。
 */
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
        } else {
          inQuotes = false;
        }
      } else {
        field += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      cur.push(field);
      field = "";
    } else if (ch === "\n") {
      cur.push(field);
      rows.push(cur);
      cur = [];
      field = "";
    } else if (ch === "\r") {
      // ignore
    } else {
      field += ch;
    }
  }
  if (field.length > 0 || cur.length > 0) {
    cur.push(field);
    rows.push(cur);
  }
  if (rows.length === 0) return [];
  const header = rows[0];
  const idxQid = header.indexOf("qid");
  const idxName = header.indexOf("name");
  const idxAdult = header.indexOf("has_adult_credit");
  if (idxQid < 0 || idxName < 0 || idxAdult < 0) {
    throw new Error(
      `mangaka.csv に想定の列が見つからない: ${header.join(",")}`,
    );
  }
  const out: CsvRow[] = [];
  for (let r = 1; r < rows.length; r++) {
    const row = rows[r];
    if (row.length === 1 && row[0] === "") continue;
    out.push({
      qid: row[idxQid] ?? "",
      name: row[idxName] ?? "",
      has_adult_credit: row[idxAdult] ?? "false",
    });
  }
  return out;
}

function refererAndOrigin(): { referer: string; origin: string } {
  const referer = process.env.RAKUTEN_REFERER ?? "http://localhost/";
  let origin = "http://localhost";
  try {
    const u = new URL(referer);
    origin = `${u.protocol}//${u.host}`;
  } catch {
    // ignore
  }
  return { referer, origin };
}

async function callOnce(
  appId: string,
  accessKey: string,
  author: string,
  page: number,
): Promise<RakutenResponse> {
  const url = new URL(ENDPOINT);
  url.searchParams.set("applicationId", appId);
  url.searchParams.set("accessKey", accessKey); // 2026 新仕様で必須
  url.searchParams.set("format", "json");
  url.searchParams.set("formatVersion", "2");
  url.searchParams.set("author", author);
  url.searchParams.set("hits", String(HITS));
  url.searchParams.set("page", String(page));
  url.searchParams.set("booksGenreId", "001001");

  const { referer, origin } = refererAndOrigin();

  const res = await fetch(url, {
    headers: {
      Referer: referer,
      Origin: origin, // 新仕様で必須化された
      "User-Agent": "MANGAL-DataFetch/0.1",
      Accept: "application/json",
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Rakuten HTTP ${res.status}: ${body.slice(0, 300)}`);
  }
  return (await res.json()) as RakutenResponse;
}

async function call(
  appId: string,
  accessKey: string,
  author: string,
  page: number,
): Promise<RakutenResponse> {
  let lastErr: unknown;
  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await callOnce(appId, accessKey, author, page);
    } catch (err) {
      lastErr = err;
      const msg = err instanceof Error ? err.message : String(err);
      const retriable =
        /HTTP (429|5\d\d)/.test(msg) ||
        /timeout|ETIMEDOUT|ECONNRESET|fetch failed/i.test(msg);
      if (!retriable || attempt === MAX_RETRIES) break;
      const delay = 2000 * 2 ** (attempt - 1);
      console.warn(
        `    attempt ${attempt} failed: ${msg}; retrying in ${delay}ms`,
      );
      await sleep(delay);
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error(String(lastErr));
}

function isAdult(item: RakutenItem): boolean {
  const id = item.booksGenreId ?? "";
  return ADULT_GENRE_PREFIXES.some((p) => id.startsWith(p));
}

async function fetchAuthor(
  appId: string,
  accessKey: string,
  row: CsvRow,
  maxPages: number,
): Promise<CachedAuthor> {
  const items: RakutenItem[] = [];
  let droppedAdult = 0;
  let totalCount = 0;
  let pageCount = 1;
  let pagesFetched = 0;

  for (let page = 1; page <= Math.min(maxPages, pageCount); page++) {
    if (page > 1) await sleep(REQUEST_INTERVAL_MS);
    const resp = await call(appId, accessKey, row.name, page);
    pageCount = resp.pageCount;
    totalCount = resp.count;
    pagesFetched = page;
    for (const item of resp.Items) {
      if (isAdult(item)) {
        droppedAdult++;
        continue;
      }
      items.push(item);
    }
    if (page >= pageCount) break;
  }

  return {
    qid: row.qid,
    name: row.name,
    fetched_at: new Date().toISOString(),
    query_author: row.name,
    total_count: totalCount,
    pages_fetched: pagesFetched,
    dropped_adult: droppedAdult,
    items,
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));

  const appId = process.env.RAKUTEN_APP_ID;
  const accessKey = process.env.RAKUTEN_ACCESS_KEY;
  if (!appId || !accessKey) {
    console.error(
      "環境変数 RAKUTEN_APP_ID と RAKUTEN_ACCESS_KEY の両方が必要です。\n" +
        "  楽天デベロッパーズ → アプリ詳細 で UUID 形式の applicationId と\n" +
        "  アクセスキーを取得して .env.local に設定してください。\n" +
        "  2026年2月の API 仕様変更により旧 applicationId 単独認証は廃止。",
    );
    process.exit(1);
  }

  if (!fs.existsSync(CSV_PATH)) {
    console.error(
      `${CSV_PATH} が見つかりません。先に \`npm run fetch:mangaka\` を実行してください。`,
    );
    process.exit(1);
  }

  fs.mkdirSync(CACHE_DIR, { recursive: true });

  const csvText = fs.readFileSync(CSV_PATH, "utf8");
  const allRows = parseCsv(csvText);
  const candidates = allRows.filter(
    (r) => r.qid && r.name && r.has_adult_credit !== "true",
  );
  const skippedAdult = allRows.length - candidates.length;

  console.log(
    `[bulk] 候補 ${candidates.length} 名 / 全 ${allRows.length} 名 (除外: 成年向けクレジット ${skippedAdult})`,
  );

  let queue = candidates;
  if (args.startQid) {
    const idx = queue.findIndex((r) => r.qid === args.startQid);
    if (idx < 0) {
      console.error(`--start ${args.startQid} がリストに存在しません。`);
      process.exit(1);
    }
    queue = queue.slice(idx);
    console.log(`[bulk] --start ${args.startQid} → ${queue.length} 名から開始`);
  }
  if (args.limit !== null) {
    queue = queue.slice(0, args.limit);
    console.log(`[bulk] --limit ${args.limit} → ${queue.length} 名に制限`);
  }

  let processed = 0;
  let skippedCache = 0;
  let totalItems = 0;
  let firstQuery = true;

  for (const row of queue) {
    const cachePath = path.join(CACHE_DIR, `${row.qid}.json`);
    if (!args.noResume && fs.existsSync(cachePath)) {
      skippedCache++;
      continue;
    }

    if (!firstQuery) await sleep(REQUEST_INTERVAL_MS);
    firstQuery = false;

    process.stdout.write(`[${processed + skippedCache + 1}/${queue.length}] ${row.qid} ${row.name} ... `);
    try {
      const cached = await fetchAuthor(appId, accessKey, row, args.maxPages);
      fs.writeFileSync(cachePath, JSON.stringify(cached, null, 2), "utf8");
      processed++;
      totalItems += cached.items.length;
      console.log(
        `${cached.items.length} items (${cached.pages_fetched}p, total=${cached.total_count}${cached.dropped_adult ? `, adult=-${cached.dropped_adult}` : ""})`,
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.log(`FAILED: ${msg}`);
      // 失敗は飛ばして続行。再実行で resume される。
      continue;
    }
  }

  console.log("\n=== bulk fetch summary ===");
  console.log(`  処理: ${processed} 名`);
  console.log(`  スキップ (キャッシュ済み): ${skippedCache} 名`);
  console.log(`  取得アイテム合計: ${totalItems}`);
  console.log(`  キャッシュ位置: ${CACHE_DIR}`);
}

main().catch((err) => {
  console.error("[fatal]", err);
  process.exit(1);
});

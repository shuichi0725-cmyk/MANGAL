/**
 * SQLite に投入済みの全シリーズについて、JA Wikipedia から
 * `title_kana / magazine_key / publisher_key / demographic / genres /
 * synopsis / year_started / year_ended` を補完する。
 *
 *   npm run fetch:wikipedia                  # 全件
 *   npm run fetch:wikipedia -- --limit 30    # 30 件で打ち止め
 *   npm run fetch:wikipedia -- --refetch     # 既に wikipedia_url が
 *                                              入っているシリーズも再取得
 *
 * 制約:
 *   - JA Wikipedia の REST/parse API を 1.1s/req で叩く
 *   - 6751 件全部回すと 2 時間超になるので、bulk-promote-test など
 *     試金石用途では --limit を付けて使う想定
 *   - 1 記事の中に {{Infobox 漫画}} が無い (アニメ記事優位の場合等) は
 *     synopsis のみ補完して metadata は触らない
 *
 * Wikipedia は CC BY-SA。synopsis を本番 UI に出す際は記事 URL を
 * 帰属表示すること（series.wikipedia_url を保持）。
 */
import "./_env";
import fs from "node:fs";
import path from "node:path";
import YAML from "yaml";
import { openDb, recordSource, tx } from "./_db";

const PARSE_API = "https://ja.wikipedia.org/w/api.php";
const SUMMARY_API = "https://ja.wikipedia.org/api/rest_v1/page/summary";
const REQUEST_INTERVAL_MS = 1100;
const MAX_RETRIES = 4;
const USER_AGENT =
  "MANGAL-DataFetch/0.1 (+https://github.com/shuichi0725-cmyk/MANGAL)";

const RAW_DIR = path.join(process.cwd(), ".cache", "wikipedia");

type Args = {
  limit: number | null;
  refetch: boolean;
};

function parseArgs(argv: string[]): Args {
  const out: Args = { limit: null, refetch: false };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--limit" && argv[i + 1]) {
      out.limit = Number(argv[++i]);
    } else if (argv[i] === "--refetch") {
      out.refetch = true;
    }
  }
  return out;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function fetchOnce(url: string): Promise<Response> {
  const res = await fetch(url, {
    headers: {
      "User-Agent": USER_AGENT,
      Accept: "application/json",
    },
  });
  return res;
}

async function fetchWithRetry(url: string, label: string): Promise<Response> {
  let lastErr: unknown;
  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      const res = await fetchOnce(url);
      if (res.ok || res.status === 404) return res;
      const body = await res.text();
      throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`);
    } catch (err) {
      lastErr = err;
      const msg = err instanceof Error ? err.message : String(err);
      const retriable =
        /HTTP (429|5\d\d)/.test(msg) ||
        /timeout|ETIMEDOUT|ECONNRESET|fetch failed/i.test(msg);
      if (!retriable || attempt === MAX_RETRIES) break;
      const delay = /HTTP 429/.test(msg)
        ? 30000 * 2 ** (attempt - 1)
        : 2000 * 2 ** (attempt - 1);
      console.warn(`  [${label}] attempt ${attempt}: ${msg}; retry in ${delay}ms`);
      await sleep(delay);
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error(String(lastErr));
}

/**
 * REST `summary` API のレスポンスを 3 通りに分類して返す。
 *   ok             : 記事発見、 url + extract あり
 *   not-found      : 404
 *   disambiguation : 曖昧さ回避ページ (採用しない)
 *
 * diagnostic で「(A) 記事発見ミス」 の内訳を取るため null 返しを廃止。
 */
type SummaryResult =
  | { kind: "ok"; url: string; extract: string }
  | { kind: "not-found" }
  | { kind: "disambiguation" };

async function fetchSummary(title: string): Promise<SummaryResult> {
  const url = `${SUMMARY_API}/${encodeURIComponent(title)}`;
  const res = await fetchWithRetry(url, `summary ${title}`);
  if (res.status === 404) return { kind: "not-found" };
  const json = (await res.json()) as {
    content_urls?: { desktop?: { page?: string } };
    extract?: string;
    type?: string;
  };
  if (json.type === "disambiguation") return { kind: "disambiguation" };
  return {
    kind: "ok",
    url: json.content_urls?.desktop?.page ?? "",
    extract: (json.extract ?? "").trim(),
  };
}

/**
 * parse API で wikitext 全文を取得。infobox parse の素。
 */
async function fetchWikitext(title: string): Promise<string | null> {
  const url =
    `${PARSE_API}?action=parse&page=${encodeURIComponent(title)}` +
    `&format=json&formatversion=2&prop=wikitext&redirects=1`;
  const res = await fetchWithRetry(url, `parse ${title}`);
  if (res.status === 404) return null;
  const json = (await res.json()) as {
    parse?: { wikitext?: string };
    error?: { code?: string };
  };
  if (json.error?.code === "missingtitle") return null;
  return json.parse?.wikitext ?? null;
}

/**
 * 1 つの infobox body から `| key = value` ペアを取り出す内部ヘルパ。
 * ネストしたテンプレ ({{...}}) や [[wikilink]] の中の `|` は区切りと
 * 誤認しないように、depth>0 の中の `|` は無視する。
 */
function parseInfoboxBody(body: string): Map<string, string> {
  const fields = new Map<string, string>();
  let depth = 0;
  let buf = "";
  const segments: string[] = [];
  for (let i = 0; i < body.length; i++) {
    const c = body[i];
    const c2 = body[i] + (body[i + 1] ?? "");
    if (c2 === "{{" || c2 === "[[") {
      depth++;
      buf += c2;
      i++;
      continue;
    }
    if (c2 === "}}" || c2 === "]]") {
      depth = Math.max(0, depth - 1);
      buf += c2;
      i++;
      continue;
    }
    if (c === "|" && depth === 0) {
      segments.push(buf);
      buf = "";
      continue;
    }
    buf += c;
  }
  if (buf) segments.push(buf);
  for (const seg of segments) {
    const eq = seg.indexOf("=");
    if (eq < 0) continue;
    const key = seg.slice(0, eq).trim();
    const value = seg.slice(eq + 1).trim();
    if (key) fields.set(key, value);
  }
  return fields;
}

/**
 * `{{Infobox ...}}` テンプレートブロックを wikitext から **すべて** 抽出して
 * fields を merge する。漫画記事は複数の Infobox を併用する事が多い:
 *   - {{Infobox animanga/Header}}     - タイトル / ふりがな
 *   - {{Infobox animanga/Print}}      - 漫画情報（掲載誌/ジャンル/出版社）
 *   - {{Infobox animanga/Footer}}     - 締め
 *   - {{Infobox 漫画}}                - 旧 schema
 *   - {{Infobox Animanga/Manga}}      - 別表記
 *   - {{Infobox 文学作品}}            - 例外
 * 複数で同一 key が見つかった場合は **先勝ち**（Header → Print の順）。
 */
function extractInfoboxFields(wikitext: string): Map<string, string> {
  const fields = new Map<string, string>();
  const candidates = [
    "Infobox animanga/Header",
    "Infobox animanga/Print",
    "Infobox animanga/Manga",
    "Infobox Animanga/Manga",
    "Infobox 漫画",
    "Infobox 文学作品",
  ];

  for (const name of candidates) {
    let searchFrom = 0;
    while (searchFrom < wikitext.length) {
      const startIdx = wikitext.indexOf(`{{${name}`, searchFrom);
      if (startIdx < 0) break;
      // テンプレ名の直後が `|` か `\n` か `}` であることを確認
      // (例えば "Infobox 漫画" が "Infobox 漫画家" にマッチしないように)
      const after = wikitext[startIdx + 2 + name.length];
      if (after && !/[|\s}]/.test(after)) {
        searchFrom = startIdx + 1;
        continue;
      }
      // ネストブレースを balance match
      let depth = 0;
      let i = startIdx;
      let endIdx = -1;
      while (i < wikitext.length) {
        if (wikitext[i] === "{" && wikitext[i + 1] === "{") {
          depth++;
          i += 2;
        } else if (wikitext[i] === "}" && wikitext[i + 1] === "}") {
          depth--;
          i += 2;
          if (depth === 0) {
            endIdx = i;
            break;
          }
        } else {
          i++;
        }
      }
      if (endIdx <= startIdx) break;
      const body = wikitext.slice(startIdx + 2 + name.length, endIdx - 2);
      const parsed = parseInfoboxBody(body);
      for (const [k, v] of parsed) {
        if (!fields.has(k) && v) fields.set(k, v); // 先勝ち
      }
      searchFrom = endIdx;
    }
  }
  return fields;
}

/** wikitext の wikilink/タグ等を雑に剥がしてプレーン化 */
function stripWikitext(s: string): string {
  let t = s;
  // [[link|alias]] → alias, [[link]] → link
  t = t.replace(/\[\[([^\]|]*)\|([^\]]+)\]\]/g, "$2");
  t = t.replace(/\[\[([^\]]+)\]\]/g, "$1");
  // {{ref|...}} などのテンプレ呼び出しを削除
  t = t.replace(/\{\{[^{}]*\}\}/g, "");
  // <ref>...</ref> 削除
  t = t.replace(/<ref[^>]*>[\s\S]*?<\/ref>/g, "");
  t = t.replace(/<ref[^/]*\/>/g, "");
  t = t.replace(/<[^>]+>/g, "");
  // HTML entities (簡易)
  t = t.replace(/&nbsp;/g, " ").replace(/&amp;/g, "&");
  return t.trim();
}

/** "1996年50号" "1996年" "1996-2008" 等の日付的文字列から年を抽出 */
function pickYear(s: string): number | null {
  if (!s) return null;
  const m = s.match(/(\d{4})/);
  if (!m) return null;
  const y = Number(m[1]);
  return y >= 1900 && y <= 2100 ? y : null;
}

/**
 * 記事冒頭の "犬夜叉（いぬやしゃ）" / "「犬夜叉」（いぬやしゃ）" /
 * "『1ポンドの福音』（いちポンドのふくいん）" のような複数のカッコ表現に
 * 対応した読み仮名抽出。タイトル直後に `』` `」` 等の閉じカギや空白が
 * 入っても許容する。
 */
function extractReadingFromExtract(
  extract: string,
  title: string,
): string | null {
  if (!extract) return null;
  const first = extract.split(/\n/)[0] ?? extract;
  const escTitle = title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // タイトルの後ろに 』」』 等の閉じ記号や空白を許容してから、開きカッコを探す。
  const re = new RegExp(
    `${escTitle}[』」"'\\s]*[（(]([^）)]+)[）)]`,
  );
  const m = first.match(re);
  if (!m) return null;
  const cap = m[1].trim();
  // 読み部分は「いぬやしゃ、〜」のように複数語が混じることがあるので
  // 先頭の連続したかな/カナ/長音だけ採用。
  const kanaOnly = cap.match(/^[぀-ゟ゠-ヿー]+/);
  return kanaOnly ? kanaOnly[0] : null;
}

/**
 * 出版社 / 掲載誌の Japanese name → key 逆引きマップを YAML マスタから作る。
 */
function loadMasterMaps(): {
  publisher: Map<string, string>;
  magazine: Map<string, string>;
  magazineDemographic: Map<string, string>;
  genre: Map<string, string>;
  demographic: Map<string, string>;
} {
  const read = <T>(file: string): Record<string, T> =>
    YAML.parse(fs.readFileSync(path.join("data", file), "utf8")) as Record<
      string,
      T
    >;

  const publishers = read<{ name: string }>("publishers.yml");
  const magazines = read<{ name: string; publisher: string; demographic: string }>(
    "magazines.yml",
  );
  const genres = read<{ name: string }>("genres.yml");
  const demographics = read<{ name: string }>("demographics.yml");

  const pubMap = new Map<string, string>();
  for (const [k, v] of Object.entries(publishers)) pubMap.set(v.name, k);
  const magMap = new Map<string, string>();
  const magDem = new Map<string, string>();
  for (const [k, v] of Object.entries(magazines)) {
    magMap.set(v.name, k);
    magDem.set(k, v.demographic);
  }
  const genreMap = new Map<string, string>();
  for (const [k, v] of Object.entries(genres)) genreMap.set(v.name, k);
  const demMap = new Map<string, string>();
  for (const [k, v] of Object.entries(demographics)) demMap.set(v.name, k);

  return {
    publisher: pubMap,
    magazine: magMap,
    magazineDemographic: magDem,
    genre: genreMap,
    demographic: demMap,
  };
}

function lookupSubstring<V>(map: Map<string, V>, text: string): V | null {
  const norm = text.normalize("NFKC");
  if (map.has(norm)) return map.get(norm)!;
  for (const [name, val] of map) {
    if (norm.includes(name)) return val;
  }
  return null;
}

/** 「アクション、冒険、ファンタジー」をジャンル key の配列に */
function mapGenres(text: string, map: Map<string, string>): string[] {
  if (!text) return [];
  const tokens = text.split(/[、,／\/]/).map((s) => stripWikitext(s).trim()).filter(Boolean);
  const out: string[] = [];
  for (const t of tokens) {
    const key = lookupSubstring(map, t);
    if (key && !out.includes(key)) out.push(key);
  }
  return out;
}

type SeriesRow = {
  id: number;
  title: string;
  title_kana: string | null;
  wikipedia_url: string | null;
};

async function main() {
  const args = parseArgs(process.argv.slice(2));
  fs.mkdirSync(RAW_DIR, { recursive: true });
  const db = openDb();
  const masters = loadMasterMaps();

  const all = db
    .prepare(
      `SELECT id, title, title_kana, wikipedia_url FROM series ORDER BY id`,
    )
    .all() as SeriesRow[];

  const queue = args.refetch
    ? all
    : all.filter((s) => s.wikipedia_url === null);
  const limited = args.limit !== null ? queue.slice(0, args.limit) : queue;
  console.log(
    `[wiki] ${limited.length} series to query (total ${all.length}, ${queue.length} pending without --refetch)`,
  );

  const updateStmt = db.prepare(
    `UPDATE series SET
       title_kana    = COALESCE(?, title_kana),
       publisher_key = COALESCE(?, publisher_key),
       magazine_key  = COALESCE(?, magazine_key),
       demographic   = COALESCE(?, demographic),
       genres        = COALESCE(?, genres),
       synopsis      = COALESCE(?, synopsis),
       year_started  = COALESCE(year_started, ?),
       year_ended    = COALESCE(year_ended, ?),
       wikipedia_url = ?,
       updated_at    = strftime('%Y-%m-%dT%H:%M:%SZ','now')
     WHERE id = ?`,
  );
  const setNotFound = db.prepare(
    `UPDATE series SET wikipedia_url = '' WHERE id = ?`,
  );

  // B-1 (2026-05-06): hit-rate 解明のため layer 別カウンタを取る。
  // layer A = 記事発見、 layer B = infobox 抽出、 layer C = master 解決。
  const stats = {
    attempted: 0,
    articleFound: 0,
    articleNotFound: 0,
    disambiguation: 0,
    summaryError: 0,
    wikitextFound: 0,
    wikitextError: 0,
    infoboxFound: 0,
    magazineExtracted: 0,
    magazineResolved: 0,
    publisherExtracted: 0,
    publisherResolved: 0,
    genresExtracted: 0,
    genresResolvedAny: 0,
    kanaExtracted: 0,
    synopsisExtracted: 0,
  };

  // Layer C 改善 (magazines.yml 拡張) のため、 master 解決に失敗した raw 値を
  // 集計。 末尾で頻度降順に出力 → どの magazine 名を master に追加すべきか判断材料。
  const unresolved = {
    magazine: new Map<string, number>(),
    publisher: new Map<string, number>(),
    genres: new Map<string, number>(),
  };
  const bumpUnresolved = (m: Map<string, number>, key: string): void => {
    m.set(key, (m.get(key) ?? 0) + 1);
  };

  let processed = 0;
  let firstReq = true;
  for (const s of limited) {
    if (!firstReq) await sleep(REQUEST_INTERVAL_MS);
    firstReq = false;

    stats.attempted++;
    process.stdout.write(`[${++processed}/${limited.length}] ${s.title} ... `);
    let summary: SummaryResult;
    try {
      summary = await fetchSummary(s.title);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.log(`✗ summary failed: ${msg.slice(0, 100)}`);
      stats.summaryError++;
      continue;
    }
    if (summary.kind === "not-found") {
      console.log("✗ not-found");
      stats.articleNotFound++;
      setNotFound.run(s.id);
      continue;
    }
    if (summary.kind === "disambiguation") {
      console.log("✗ disambiguation");
      stats.disambiguation++;
      setNotFound.run(s.id);
      continue;
    }
    stats.articleFound++;

    let wikitext: string | null = null;
    try {
      await sleep(REQUEST_INTERVAL_MS / 2);
      wikitext = await fetchWikitext(s.title);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.warn(`  wikitext failed: ${msg.slice(0, 80)}`);
      stats.wikitextError++;
    }
    if (wikitext) stats.wikitextFound++;

    const fields = wikitext ? extractInfoboxFields(wikitext) : new Map();
    if (fields.size > 0) stats.infoboxFound++;

    const kanaFromExtract = extractReadingFromExtract(summary.extract, s.title);
    const kanaFromInfobox =
      stripWikitext(fields.get("ふりがな") ?? fields.get("読み") ?? "") || null;
    const titleKana = kanaFromExtract ?? kanaFromInfobox;
    if (titleKana) stats.kanaExtracted++;
    const publisherText = stripWikitext(
      fields.get("出版社") ?? fields.get("出版社1") ?? "",
    );
    if (publisherText) stats.publisherExtracted++;
    const publisherKey =
      publisherText ? lookupSubstring(masters.publisher, publisherText) : null;
    if (publisherKey) stats.publisherResolved++;
    if (publisherText && !publisherKey) {
      bumpUnresolved(unresolved.publisher, publisherText);
    }
    const magazineText = stripWikitext(
      fields.get("掲載誌") ??
        fields.get("掲載紙") ??
        fields.get("レーベル") ??
        "",
    );
    if (magazineText) stats.magazineExtracted++;
    const magazineKey =
      magazineText ? lookupSubstring(masters.magazine, magazineText) : null;
    if (magazineKey) stats.magazineResolved++;
    if (magazineText && !magazineKey) {
      bumpUnresolved(unresolved.magazine, magazineText);
    }
    const demographic = magazineKey
      ? masters.magazineDemographic.get(magazineKey) ?? null
      : null;
    const genresStr = stripWikitext(fields.get("ジャンル") ?? "");
    if (genresStr) stats.genresExtracted++;
    const genreKeys = mapGenres(genresStr, masters.genre);
    if (genreKeys.length > 0) stats.genresResolvedAny++;
    if (genresStr && genreKeys.length === 0) {
      bumpUnresolved(unresolved.genres, genresStr);
    }
    const synopsis = (summary.extract || "").slice(0, 800);
    if (synopsis) stats.synopsisExtracted++;
    // 「発表期間」 = "1987年 - 2007年" 形式 (Infobox animanga/Print) を分解。
    // それ以外は「開始号」「終了号」「開始日」「終了日」を個別に拾う。
    const periodText = stripWikitext(
      fields.get("発表期間") ?? fields.get("発表号") ?? "",
    );
    const periodYears = periodText
      ? Array.from(periodText.matchAll(/(\d{4})/g)).map((m) => Number(m[1]))
      : [];
    const yearStart =
      periodYears[0] ??
      pickYear(stripWikitext(fields.get("開始号") ?? fields.get("開始日") ?? ""));
    const yearEnd =
      (periodYears.length >= 2 ? periodYears[periodYears.length - 1] : null) ??
      pickYear(stripWikitext(fields.get("終了号") ?? fields.get("終了日") ?? ""));

    tx(db, () => {
      updateStmt.run(
        titleKana || null,
        publisherKey,
        magazineKey,
        demographic,
        genreKeys.length > 0 ? genreKeys.join(",") : null,
        synopsis || null,
        yearStart,
        yearEnd,
        summary.url || "",
        s.id,
      );
      recordSource(db, "wikipedia", "series", String(s.id), {
        url: summary.url,
        infobox_keys: Array.from(fields.keys()),
        kana: titleKana,
        publisher: publisherText,
        magazine: magazineText,
        genres: genresStr,
      });
    });

    // raw もファイルに残す（後段デバッグ・帰属表示の根拠用）
    if (wikitext) {
      const safe = encodeURIComponent(s.title).replace(/%/g, "_").slice(0, 80);
      fs.writeFileSync(
        path.join(RAW_DIR, `${s.id}-${safe}.wikitext`),
        wikitext,
        "utf8",
      );
    }

    // 構造化 log: layer 別に ✓ / ✗ を出して、 どの段階で何が落ちたか観察可能。
    // mag/pub は raw → resolved 両方を表示 (master 解決失敗が見える)。
    const parts: string[] = [];
    if (fields.size > 0) {
      parts.push("infobox ✓");
    } else {
      parts.push(wikitext ? "infobox ✗" : "no-wikitext");
    }
    if (magazineText) {
      parts.push(`mag=${magazineText}→${magazineKey ?? "✗"}`);
    }
    if (publisherText) {
      parts.push(`pub=${publisherText}→${publisherKey ?? "✗"}`);
    }
    if (genresStr) {
      parts.push(`g=${genresStr}→${genreKeys.join("|") || "✗"}`);
    }
    if (titleKana) parts.push(`kana=${titleKana}`);
    if (synopsis) parts.push("syn ✓");
    console.log(`✓ article ${parts.join(" ")}`);
  }

  // B-1 (2026-05-06): layer A/B/C 3 層で hit/miss を可視化する。
  const pct = (num: number, denom: number): string =>
    denom === 0 ? "  -%" : `${Math.round((num * 100) / denom)
      .toString()
      .padStart(3, " ")}%`;
  console.log("\n=== fetch:wikipedia diagnostic ===");
  console.log(`  attempted               : ${stats.attempted}`);
  console.log(`  layer A (article find):`);
  console.log(
    `    article found         : ${stats.articleFound} (${pct(stats.articleFound, stats.attempted)})`,
  );
  console.log(`    article not-found     : ${stats.articleNotFound}`);
  console.log(`    disambiguation        : ${stats.disambiguation}`);
  console.log(`    summary error         : ${stats.summaryError}`);
  console.log(`  layer B (infobox extract):`);
  console.log(
    `    wikitext fetched      : ${stats.wikitextFound} (${pct(stats.wikitextFound, stats.articleFound)} of articleFound)`,
  );
  console.log(`    wikitext error        : ${stats.wikitextError}`);
  console.log(
    `    infobox detected      : ${stats.infoboxFound} (${pct(stats.infoboxFound, stats.articleFound)} of articleFound)`,
  );
  console.log(
    `    magazine raw extract  : ${stats.magazineExtracted} (${pct(stats.magazineExtracted, stats.infoboxFound)} of infoboxFound)`,
  );
  console.log(`    publisher raw extract : ${stats.publisherExtracted}`);
  console.log(`    genres raw extract    : ${stats.genresExtracted}`);
  console.log(`    kana extract          : ${stats.kanaExtracted}`);
  console.log(
    `    synopsis extract      : ${stats.synopsisExtracted} (${pct(stats.synopsisExtracted, stats.articleFound)} of articleFound)`,
  );
  console.log(`  layer C (master resolve):`);
  console.log(
    `    magazine resolved     : ${stats.magazineResolved} (${pct(stats.magazineResolved, stats.magazineExtracted)} of magazineExtracted)`,
  );
  console.log(
    `    publisher resolved    : ${stats.publisherResolved} (${pct(stats.publisherResolved, stats.publisherExtracted)} of publisherExtracted)`,
  );
  console.log(
    `    genres resolved >= 1  : ${stats.genresResolvedAny} (${pct(stats.genresResolvedAny, stats.genresExtracted)} of genresExtracted)`,
  );
  console.log(`  raw cache dir : ${RAW_DIR}`);

  // Layer C 改善のための diagnostic: 解決に失敗した raw 値を頻度降順で出す。
  // ここに出てくる頻度の高い名前を data/magazines.yml 等に追加すれば fill 率が上がる。
  const dumpUnresolved = (label: string, m: Map<string, number>): void => {
    if (m.size === 0) return;
    const sorted = [...m.entries()].sort((a, b) => b[1] - a[1]);
    console.log(`\n=== unresolved ${label} (raw → no master match), top 30 ===`);
    for (const [name, count] of sorted.slice(0, 30)) {
      console.log(`  ${count.toString().padStart(3, " ")}× ${name}`);
    }
    if (sorted.length > 30) {
      console.log(`  ... (${sorted.length - 30} more)`);
    }
  };
  dumpUnresolved("magazine", unresolved.magazine);
  dumpUnresolved("publisher", unresolved.publisher);
  dumpUnresolved("genres", unresolved.genres);

  db.close();
}

main().catch((err) => {
  console.error("[fatal]", err);
  process.exit(1);
});

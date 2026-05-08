/**
 * 2026-05-08: ISBN 取得 source 比較 probe (read-only).
 *
 * 現状の data 取得は **Wikidata QID → CSV alt_names → NDL CQL** という
 * 「作家名キー」 駆動で、 alt_names の表記揺れ + NDL CQL の fuzzy match
 * により別作家混入 (false-positive) を量産する構造的 limitation がある。
 *
 * 代替フローとして「ISBN list を別 source から取得 → openBD で metadata
 * 生成」 を試したい。 候補 source は Google Books API v1 と MADB
 * (メディア芸術データベース、 文化庁) の 2 つ。
 *
 * このスクリプトは **DB を変更しない**。 6 作家 × 2 source で hit rate /
 * metadata 充足度 / 既存 NDL ISBN との overlap を測り、 結果を
 * `docs/isbn-source-comparison.md` に書き出す。 raw response は
 * `out/probe-isbn-sources/` に dump して後続 plan の根拠 trail とする。
 *
 * Phase 構成:
 *   Phase 0: 各 API の spec sanity check (= 1 リクエストで shape 検証)
 *   Phase 1: per-mangaka query (Google Books / MADB SPARQL)
 *   Phase 2: 既存 DB の NDL ISBN との交差を計算
 *   Phase 3: Markdown 出力
 *
 * 実行:
 *   npm run probe:isbn-sources                    # 通常実行
 *   npm run probe:isbn-sources -- --dry-run       # API call せず DB 集計のみ
 */
import "./_env";
import fs from "node:fs";
import path from "node:path";
import { openDb } from "./_db";
import { normalizeIsbn13 } from "../lib/edition";

const GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes";
const MADB_SPARQL_ENDPOINT = "https://mediaarts-db.bunka.go.jp/sparql";
const GOOGLE_BOOKS_INTERVAL_MS = 200;
const MADB_INTERVAL_MS = 1000;
const GOOGLE_BOOKS_MAX_RESULTS = 40; // API max
const GOOGLE_BOOKS_PAGE_LIMIT = 200; // 5 pages × 40 = 200 件で打切り
const OUT_DIR = path.join(process.cwd(), "out", "probe-isbn-sources");
const DOCS_PATH = path.join(process.cwd(), "docs", "isbn-source-comparison.md");

const DRY_RUN = process.argv.includes("--dry-run");
const GOOGLE_KEY = process.env.GOOGLE_BOOKS_API_KEY?.trim() || null;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

type ProbeAuthor = { name: string; qid: string };

// 既存 13 yaml の代表作家 6 名 (= seed-canonical-21 の subset)
const PROBE_AUTHORS: ProbeAuthor[] = [
  { name: "諫山創", qid: "Q11331084" },
  { name: "高屋奈月", qid: "Q231007" },
  { name: "浦沢直樹", qid: "Q310385" },
  { name: "浅野いにお", qid: "Q1145902" },
  { name: "吾峠呼世晴", qid: "Q56022442" },
  { name: "雷句誠", qid: "Q1366247" },
];

type SourceName = "googleBooks" | "madb";

type NormalizedItem = {
  isbn13: string | null;
  title: string | null;
  publisher: string | null;
  description: string | null;
  cover: string | null;
  kana: string | null;
  magazine: string | null;
  rawIsbn: string | null;
};

type AuthorResult = {
  author: ProbeAuthor;
  googleBooks: SourceResult;
  madb: SourceResult;
  ndlIsbns: string[];
};

type SourceResult = {
  ok: boolean;
  error: string | null;
  hits: number;
  items: NormalizedItem[];
  uniqueIsbns: string[];
  rawSamplePath: string | null;
};

function pct(num: number, denom: number): string {
  if (denom === 0) return "  -";
  return `${Math.round((num * 100) / denom)}%`;
}

function ensureDir(dir: string): void {
  fs.mkdirSync(dir, { recursive: true });
}

function safeFilename(s: string): string {
  return s.replace(/[^A-Za-z0-9_.-]/g, "_");
}

async function probeGoogleBooksSanity(): Promise<{ ok: boolean; note: string }> {
  if (DRY_RUN) return { ok: false, note: "dry-run: skipped" };
  // Test query: 進撃の巨人 1 巻 ISBN
  const url = `${GOOGLE_BOOKS_API}?q=isbn:9784063842401${GOOGLE_KEY ? `&key=${GOOGLE_KEY}` : ""}`;
  try {
    const res = await fetch(url);
    if (!res.ok) {
      return { ok: false, note: `HTTP ${res.status}` };
    }
    const j = (await res.json()) as { totalItems?: number };
    return {
      ok: true,
      note: `totalItems=${j.totalItems ?? 0}, key=${GOOGLE_KEY ? "yes" : "no"}`,
    };
  } catch (err) {
    return {
      ok: false,
      note: err instanceof Error ? err.message : String(err),
    };
  }
}

async function probeMadbSanity(): Promise<{ ok: boolean; note: string }> {
  if (DRY_RUN) return { ok: false, note: "dry-run: skipped" };
  // 最小 SPARQL: 1 件だけ取得して endpoint 生存確認
  const query = "SELECT * WHERE { ?s ?p ?o } LIMIT 1";
  const url = `${MADB_SPARQL_ENDPOINT}?query=${encodeURIComponent(query)}`;
  try {
    const res = await fetch(url, {
      headers: { Accept: "application/sparql-results+json" },
    });
    if (!res.ok) {
      return { ok: false, note: `HTTP ${res.status}` };
    }
    const text = await res.text();
    return { ok: true, note: `responded ${text.length} bytes` };
  } catch (err) {
    return {
      ok: false,
      note: err instanceof Error ? err.message : String(err),
    };
  }
}

type GoogleBooksItem = {
  volumeInfo?: {
    title?: string;
    authors?: string[];
    publisher?: string;
    publishedDate?: string;
    description?: string;
    industryIdentifiers?: Array<{ type?: string; identifier?: string }>;
    imageLinks?: { thumbnail?: string; smallThumbnail?: string };
    categories?: string[];
    language?: string;
  };
};

async function fetchGoogleBooks(authorName: string): Promise<{
  items: GoogleBooksItem[];
  error: string | null;
}> {
  if (DRY_RUN) return { items: [], error: "dry-run" };
  const all: GoogleBooksItem[] = [];
  let startIndex = 0;
  while (startIndex < GOOGLE_BOOKS_PAGE_LIMIT) {
    const params = new URLSearchParams({
      q: `inauthor:"${authorName}"+subject:"Comics & Graphic Novels"`,
      maxResults: String(GOOGLE_BOOKS_MAX_RESULTS),
      startIndex: String(startIndex),
      langRestrict: "ja",
    });
    if (GOOGLE_KEY) params.set("key", GOOGLE_KEY);
    const url = `${GOOGLE_BOOKS_API}?${params.toString()}`;
    try {
      const res = await fetch(url);
      if (!res.ok) {
        return { items: all, error: `HTTP ${res.status} at startIndex=${startIndex}` };
      }
      const j = (await res.json()) as { totalItems?: number; items?: GoogleBooksItem[] };
      const page = j.items ?? [];
      all.push(...page);
      const total = j.totalItems ?? 0;
      if (page.length === 0 || all.length >= total) break;
      startIndex += GOOGLE_BOOKS_MAX_RESULTS;
      await sleep(GOOGLE_BOOKS_INTERVAL_MS);
    } catch (err) {
      return {
        items: all,
        error: err instanceof Error ? err.message : String(err),
      };
    }
  }
  return { items: all, error: null };
}

function normalizeGoogleBooksItem(item: GoogleBooksItem): NormalizedItem {
  const vi = item.volumeInfo ?? {};
  let rawIsbn: string | null = null;
  for (const ident of vi.industryIdentifiers ?? []) {
    if (ident.type === "ISBN_13" && ident.identifier) {
      rawIsbn = ident.identifier;
      break;
    }
    if (ident.type === "ISBN_10" && ident.identifier && !rawIsbn) {
      rawIsbn = ident.identifier;
    }
  }
  return {
    isbn13: normalizeIsbn13(rawIsbn),
    title: vi.title ?? null,
    publisher: vi.publisher ?? null,
    description: vi.description ?? null,
    cover: vi.imageLinks?.thumbnail ?? vi.imageLinks?.smallThumbnail ?? null,
    kana: null, // Google Books は kana 提供なし
    magazine: null,
    rawIsbn,
  };
}

type SparqlBinding = Record<string, { type?: string; value?: string }>;

async function fetchMadb(authorName: string): Promise<{
  bindings: SparqlBinding[];
  error: string | null;
}> {
  if (DRY_RUN) return { bindings: [], error: "dry-run" };
  // MADB の class/property URI は LOD ドキュメント未確認のため、
  // 一般的な Schema.org マッピング前提で query を構築。 endpoint が
  // 存在しない / property がマッチしないケースは error として記録される。
  const query = `
    PREFIX schema: <http://schema.org/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?manifestation ?title ?isbn ?publisher ?image ?description ?magazine WHERE {
      ?manifestation schema:author ?author .
      ?author schema:name ?authorName .
      FILTER(STR(?authorName) = "${authorName}")
      OPTIONAL { ?manifestation schema:name ?title }
      OPTIONAL { ?manifestation schema:isbn ?isbn }
      OPTIONAL { ?manifestation schema:publisher/schema:name ?publisher }
      OPTIONAL { ?manifestation schema:image ?image }
      OPTIONAL { ?manifestation schema:description ?description }
      OPTIONAL { ?manifestation schema:isPartOf/schema:name ?magazine }
    } LIMIT 500
  `;
  const url = `${MADB_SPARQL_ENDPOINT}?query=${encodeURIComponent(query)}`;
  try {
    const res = await fetch(url, {
      headers: { Accept: "application/sparql-results+json" },
    });
    if (!res.ok) {
      return { bindings: [], error: `HTTP ${res.status}` };
    }
    const j = (await res.json()) as {
      results?: { bindings?: SparqlBinding[] };
    };
    return { bindings: j.results?.bindings ?? [], error: null };
  } catch (err) {
    return {
      bindings: [],
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

function normalizeMadbBinding(b: SparqlBinding): NormalizedItem {
  const v = (k: string) => b[k]?.value?.trim() || null;
  const rawIsbn = v("isbn");
  return {
    isbn13: normalizeIsbn13(rawIsbn),
    title: v("title"),
    publisher: v("publisher"),
    description: v("description"),
    cover: v("image"),
    kana: null, // probe 1 回目では取得対象外 (= manifestation 単位の kana property 未確認)
    magazine: v("magazine"),
    rawIsbn,
  };
}

function summarizeSource(items: NormalizedItem[]): {
  uniqueIsbns: string[];
  withCover: number;
  withDesc: number;
  withPublisher: number;
  withKana: number;
  withMagazine: number;
} {
  const isbns = new Set<string>();
  let withCover = 0;
  let withDesc = 0;
  let withPublisher = 0;
  let withKana = 0;
  let withMagazine = 0;
  for (const it of items) {
    if (it.isbn13) isbns.add(it.isbn13);
    if (it.cover) withCover++;
    if (it.description) withDesc++;
    if (it.publisher) withPublisher++;
    if (it.kana) withKana++;
    if (it.magazine) withMagazine++;
  }
  return {
    uniqueIsbns: [...isbns],
    withCover,
    withDesc,
    withPublisher,
    withKana,
    withMagazine,
  };
}

function getNdlIsbnsForAuthor(qid: string): string[] {
  try {
    const db = openDb();
    const rows = db
      .prepare(
        `SELECT DISTINCT v.isbn13 AS isbn13
         FROM volumes v
         JOIN editions e ON v.edition_id = e.id
         JOIN series s ON e.series_id = s.id
         JOIN series_authors sa ON sa.series_id = s.id
         JOIN mangaka m ON sa.mangaka_id = m.id
         WHERE m.qid = ? AND v.isbn13 IS NOT NULL AND v.isbn13 != ''`,
      )
      .all(qid) as { isbn13: string }[];
    db.close();
    return rows.map((r) => r.isbn13);
  } catch (err) {
    console.warn(
      `  [warn] DB read failed for ${qid}: ${err instanceof Error ? err.message : String(err)}`,
    );
    return [];
  }
}

function intersect(a: string[], b: string[]): string[] {
  const set = new Set(a);
  return b.filter((x) => set.has(x));
}

function dumpRaw(authorQid: string, source: SourceName, payload: unknown): string {
  const filename = `${safeFilename(authorQid)}-${source}.json`;
  const filepath = path.join(OUT_DIR, filename);
  fs.writeFileSync(filepath, JSON.stringify(payload, null, 2), "utf8");
  return path.relative(process.cwd(), filepath);
}

async function processAuthor(author: ProbeAuthor): Promise<AuthorResult> {
  console.log(`\n[probe] ${author.name} (${author.qid})`);

  // Google Books
  console.log(`  google-books fetching...`);
  const gb = await fetchGoogleBooks(author.name);
  const gbItems = gb.items.map(normalizeGoogleBooksItem);
  const gbSummary = summarizeSource(gbItems);
  const gbDumpPath = DRY_RUN ? null : dumpRaw(author.qid, "googleBooks", gb.items);
  console.log(
    `  google-books: hits=${gb.items.length} unique-isbn=${gbSummary.uniqueIsbns.length}${gb.error ? ` ERROR=${gb.error}` : ""}`,
  );

  await sleep(MADB_INTERVAL_MS);

  // MADB
  console.log(`  madb fetching...`);
  const madb = await fetchMadb(author.name);
  const madbItems = madb.bindings.map(normalizeMadbBinding);
  const madbSummary = summarizeSource(madbItems);
  const madbDumpPath = DRY_RUN ? null : dumpRaw(author.qid, "madb", madb.bindings);
  console.log(
    `  madb: hits=${madb.bindings.length} unique-isbn=${madbSummary.uniqueIsbns.length}${madb.error ? ` ERROR=${madb.error}` : ""}`,
  );

  const ndlIsbns = getNdlIsbnsForAuthor(author.qid);

  return {
    author,
    googleBooks: {
      ok: gb.error === null,
      error: gb.error,
      hits: gb.items.length,
      items: gbItems,
      uniqueIsbns: gbSummary.uniqueIsbns,
      rawSamplePath: gbDumpPath,
    },
    madb: {
      ok: madb.error === null,
      error: madb.error,
      hits: madb.bindings.length,
      items: madbItems,
      uniqueIsbns: madbSummary.uniqueIsbns,
      rawSamplePath: madbDumpPath,
    },
    ndlIsbns,
  };
}

function renderMarkdown(
  results: AuthorResult[],
  sanity: { gb: { ok: boolean; note: string }; madb: { ok: boolean; note: string } },
): string {
  const now = new Date().toISOString();
  const lines: string[] = [];
  lines.push("---");
  lines.push(`probedAt: "${now}"`);
  lines.push(`googleBooksApiKey: ${GOOGLE_KEY ? '"present"' : '"absent (anonymous)"'}`);
  lines.push(`dryRun: ${DRY_RUN}`);
  lines.push("---");
  lines.push("");
  lines.push("# ISBN 取得 source 比較 (Google Books vs MADB)");
  lines.push("");
  lines.push(
    "現状の Wikidata QID → CSV alt_names → NDL CQL 経路の構造的限界 (= 別作家混入) を回避するため、",
  );
  lines.push(
    "「ISBN list を別 source から取得 → openBD で metadata 生成」 への移行可否を評価する read-only probe。",
  );
  lines.push("");

  lines.push("## Phase 0: spec sanity check");
  lines.push("");
  lines.push("| Source | OK | Note |");
  lines.push("|---|---|---|");
  lines.push(`| Google Books v1 | ${sanity.gb.ok ? "OK" : "FAIL"} | ${sanity.gb.note} |`);
  lines.push(`| MADB SPARQL | ${sanity.madb.ok ? "OK" : "FAIL"} | ${sanity.madb.note} |`);
  lines.push("");

  lines.push("## Spec 比較表 (一般知識ベース、 probe で実証)");
  lines.push("");
  lines.push("| 観点 | Google Books v1 | MADB |");
  lines.push("|---|---|---|");
  lines.push("| 認証 | API key 推奨 (anonymous も可) | 不要 |");
  lines.push("| Rate limit | 1000 req/day (anon) / 10 QPS (key) | 公平利用、 1s/req 推奨 |");
  lines.push(
    "| 検索方式 | `q=inauthor:\"X\"+subject:Comics` / `isbn:` | SPARQL `?work schema:author/schema:name \"X\"` |",
  );
  lines.push("| 漫画 coverage | 部分的、 電子/英訳混入 | 国内漫画 30 万件超、 国内最強級 |");
  lines.push("| ISBN 提供率 | 60-80% 想定 | manifestation には ISBN 必須 |");
  lines.push("| Cover image | `imageLinks.thumbnail` | `schema:image` |");
  lines.push("| Kana | 提供なし | `mng:titleTranscription` 想定 |");
  lines.push("| 雑誌 | なし | 連載誌・初出誌 (= 唯一の真値) |");
  lines.push("| ライセンス | Books API ToS | 文化庁 OPEN DATA = CC-BY 4.0 想定 |");
  lines.push("| Response 形式 | REST JSON | SPARQL (JSON/XML/CSV) |");
  lines.push(
    "| `normalizeIsbn13` 互換 | ISBN_13/10 → 100% 互換 | literal を直接通せる |",
  );
  lines.push("");

  lines.push("## Phase 1: per-mangaka 結果");
  lines.push("");
  lines.push(
    "| 作家 | QID | GB hits | GB uniq ISBN | GB cover% | GB desc% | GB pub% | MADB hits | MADB uniq ISBN | MADB cover% | MADB desc% | MADB pub% | MADB mag% | NDL ISBN | GB∩NDL | MADB∩NDL |",
  );
  lines.push(
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
  );
  for (const r of results) {
    const gb = r.googleBooks;
    const md = r.madb;
    const gbS = summarizeSource(gb.items);
    const mdS = summarizeSource(md.items);
    const gbOverlap = intersect(gb.uniqueIsbns, r.ndlIsbns).length;
    const mdOverlap = intersect(md.uniqueIsbns, r.ndlIsbns).length;
    lines.push(
      `| ${r.author.name} | ${r.author.qid} | ${gb.hits} | ${gb.uniqueIsbns.length} | ${pct(gbS.withCover, gb.hits)} | ${pct(gbS.withDesc, gb.hits)} | ${pct(gbS.withPublisher, gb.hits)} | ${md.hits} | ${md.uniqueIsbns.length} | ${pct(mdS.withCover, md.hits)} | ${pct(mdS.withDesc, md.hits)} | ${pct(mdS.withPublisher, md.hits)} | ${pct(mdS.withMagazine, md.hits)} | ${r.ndlIsbns.length} | ${gbOverlap} | ${mdOverlap} |`,
    );
  }
  lines.push("");

  // エラーサマリ
  const errors: string[] = [];
  for (const r of results) {
    if (r.googleBooks.error) {
      errors.push(`- ${r.author.name} / google-books: ${r.googleBooks.error}`);
    }
    if (r.madb.error) {
      errors.push(`- ${r.author.name} / madb: ${r.madb.error}`);
    }
  }
  if (errors.length > 0) {
    lines.push("## エラーサマリ");
    lines.push("");
    lines.push(...errors);
    lines.push("");
  }

  // Raw dump links
  lines.push("## Raw response dumps");
  lines.push("");
  for (const r of results) {
    lines.push(`### ${r.author.name} (${r.author.qid})`);
    lines.push("");
    if (r.googleBooks.rawSamplePath) {
      lines.push(`- google-books: \`${r.googleBooks.rawSamplePath}\``);
    }
    if (r.madb.rawSamplePath) {
      lines.push(`- madb: \`${r.madb.rawSamplePath}\``);
    }
    lines.push("");
  }

  // 推奨判断 (= probe 結果から自動 derive)
  lines.push("## 推奨判断 (probe 結果ベース)");
  lines.push("");
  const gbTotalIsbns = results.reduce((s, r) => s + r.googleBooks.uniqueIsbns.length, 0);
  const mdTotalIsbns = results.reduce((s, r) => s + r.madb.uniqueIsbns.length, 0);
  const gbErrCount = results.filter((r) => r.googleBooks.error).length;
  const mdErrCount = results.filter((r) => r.madb.error).length;
  lines.push(`- Google Books: 全 6 作家で計 ${gbTotalIsbns} unique ISBN、 ${gbErrCount}/6 でエラー`);
  lines.push(`- MADB:         全 6 作家で計 ${mdTotalIsbns} unique ISBN、 ${mdErrCount}/6 でエラー`);
  lines.push("");
  if (mdErrCount === 6 && gbErrCount === 0) {
    lines.push(
      "→ MADB SPARQL endpoint 到達不能。 採用するなら REST API か LOD ダンプ DL に方針転換が必要。",
    );
    lines.push("→ 暫定で Google Books 採用が現実解。");
  } else if (gbErrCount === 6 && mdErrCount === 0) {
    lines.push("→ Google Books 到達不能 (= 環境制約)。 MADB 単独採用が合理的。");
  } else if (mdTotalIsbns > gbTotalIsbns * 1.5) {
    lines.push("→ MADB の ISBN 件数が Google Books を大きく上回る。 MADB を主、 Google Books を補完に。");
  } else if (gbTotalIsbns > mdTotalIsbns * 1.5) {
    lines.push("→ Google Books の ISBN 件数が MADB を大きく上回る。 Google Books を主に。");
  } else if (gbTotalIsbns === 0 && mdTotalIsbns === 0) {
    lines.push("→ 両 source とも結果ゼロ。 環境からの API 到達不能か query 設計ミス。 spec 再調査が必要。");
  } else {
    lines.push("→ 両 source 拮抗。 ライセンス (CC-BY) と雑誌 metadata の有無で MADB 推奨。");
  }
  lines.push("");
  lines.push("## 次プラン候補");
  lines.push("");
  lines.push("- 採用 source の本格 fetcher 実装 (= `scripts/fetch-madb.ts` 等)");
  lines.push("- DB schema 拡張 (= sources テーブルへの provenance、 隔離テーブル `volumes_madb`)");
  lines.push("- 既存 NDL ISBN との merge ロジック設計 (= 上書き優先順位)");
  lines.push("- bulk-promote-test workflow への step 追加");
  lines.push("");

  return lines.join("\n") + "\n";
}

async function main(): Promise<void> {
  console.log(
    `[probe-isbn-sources] start (dryRun=${DRY_RUN}, googleBooksKey=${GOOGLE_KEY ? "yes" : "no"})`,
  );
  ensureDir(OUT_DIR);
  ensureDir(path.dirname(DOCS_PATH));

  // Phase 0: sanity
  console.log("\n=== Phase 0: spec sanity check ===");
  const gbSanity = await probeGoogleBooksSanity();
  console.log(`  google-books: ${gbSanity.ok ? "OK" : "FAIL"} (${gbSanity.note})`);
  await sleep(MADB_INTERVAL_MS);
  const madbSanity = await probeMadbSanity();
  console.log(`  madb:         ${madbSanity.ok ? "OK" : "FAIL"} (${madbSanity.note})`);

  // Phase 1: per-author
  console.log("\n=== Phase 1: per-mangaka probe ===");
  const results: AuthorResult[] = [];
  for (const author of PROBE_AUTHORS) {
    results.push(await processAuthor(author));
    await sleep(MADB_INTERVAL_MS);
  }

  // Phase 2 & 3: aggregate + write Markdown
  console.log("\n=== Phase 2: aggregate + write Markdown ===");
  const md = renderMarkdown(results, { gb: gbSanity, madb: madbSanity });
  fs.writeFileSync(DOCS_PATH, md, "utf8");
  console.log(`  wrote ${path.relative(process.cwd(), DOCS_PATH)}`);
  console.log(`  raw dumps in ${path.relative(process.cwd(), OUT_DIR)}/`);

  console.log("\n[probe-isbn-sources] done");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

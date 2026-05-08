/**
 * 2026-05-08: MADB (メディア芸術データベース) ISBN 取得 probe (read-only).
 *
 * 現状の data 取得は **Wikidata QID → CSV alt_names → NDL CQL** という
 * 「作家名キー」 駆動で、 alt_names の表記揺れ + NDL CQL の fuzzy match
 * により別作家混入 (false-positive) を量産する構造的 limitation がある。
 *
 * 代替フローとして「MADB から ISBN list を取得 → openBD で metadata 生成」
 * を試したい。 MADB は文化庁が提供する LOD で、 国内漫画 30 万件超を
 * 収録、 ライセンスは CC-BY 4.0 想定。 雑誌 (= 連載誌・初出誌) の
 * metadata を持つ唯一の真値ソースでもある。
 *
 * このスクリプトは **DB を変更しない**。 6 作家について MADB SPARQL に
 * query し、 hit rate / unique ISBN / metadata 充足度 / 既存 NDL ISBN
 * との overlap を測って `docs/madb-probe.md` に書き出す。 raw response
 * は `out/probe-madb/` に dump して後続 plan の根拠 trail とする。
 *
 * Phase 構成:
 *   Phase 0: SPARQL endpoint sanity check (= 1 リクエストで生存確認)
 *   Phase 1: per-mangaka query
 *   Phase 2: 既存 DB の NDL ISBN との交差を計算
 *   Phase 3: Markdown 出力
 *
 * 実行:
 *   npm run probe:madb                    # 通常実行
 *   npm run probe:madb -- --dry-run       # API call せず DB 集計のみ
 */
import "./_env";
import fs from "node:fs";
import path from "node:path";
import { openDb } from "./_db";
import { normalizeIsbn13 } from "../lib/edition";

// 2026-05-08: 正規 endpoint は artmuseums.go.jp 系 (= 旧 bunka.go.jp/sparql は
// DNS 解決失敗、 GH runner からも `fetch failed`)。 出典:
// https://lodc2022-culture-art.metadata.moe/docs/mediaartsdb/
const MADB_SPARQL_ENDPOINT = "https://mediaarts-db.artmuseums.go.jp/sparql";
const MADB_INTERVAL_MS = 1000;
const OUT_DIR = path.join(process.cwd(), "out", "probe-madb");
const DOCS_PATH = path.join(process.cwd(), "docs", "madb-probe.md");

const DRY_RUN = process.argv.includes("--dry-run");

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

type ProbeAuthor = { name: string; qid: string; surname: string };

// 既存 13 yaml の代表作家 6 名 (= seed-canonical-21 の subset)
// surname は表記揺れ発掘用の CONTAINS キー (= 全角空白入り「諫山 創」 や
// カナ「ゴトウゲ コヨハル」 を網羅的に拾う)。
// QID は data/seed/mangaka.csv の真値に合わせる (= 過去 hardcode は誤値で
// fetch-madb での mangaka resolve が失敗していた)。
const PROBE_AUTHORS: ProbeAuthor[] = [
  { name: "諫山創", surname: "諫山", qid: "Q3782468" },
  { name: "高屋奈月", surname: "高屋", qid: "Q241885" },
  { name: "浦沢直樹", surname: "浦沢", qid: "Q348436" },
  { name: "浅野いにお", surname: "浅野", qid: "Q600217" },
  { name: "吾峠呼世晴", surname: "吾峠", qid: "Q24865213" },
  { name: "雷句誠", surname: "雷句", qid: "Q972529" },
];

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
  ok: boolean;
  error: string | null;
  hits: number;
  items: NormalizedItem[];
  uniqueIsbns: string[];
  rawSamplePath: string | null;
  ndlIsbns: string[];
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

async function probeSanity(): Promise<{ ok: boolean; note: string }> {
  if (DRY_RUN) return { ok: false, note: "dry-run: skipped" };
  // 漫画単行本 (class:MangaBook) の総数を数えて endpoint 到達 + dataset
  // 規模を同時確認。 schema discovery で確定した URI prefix:
  //   /data/class#MangaBook  (= /ns/class# ではない)
  const query = `
    PREFIX class: <https://mediaarts-db.artmuseums.go.jp/data/class#>
    SELECT (COUNT(?m) AS ?n) WHERE { ?m a class:MangaBook }
  `;
  try {
    const res = await sparqlFetch(query);
    if (!res.ok) {
      return { ok: false, note: res.error ?? "unknown error" };
    }
    const n = res.bindings[0]?.["n"]?.value ?? "?";
    return { ok: true, note: `class:MangaBook count=${n}` };
  } catch (err) {
    return {
      ok: false,
      note: err instanceof Error ? err.message : String(err),
    };
  }
}

/**
 * Schema discovery: dataset 内の vocabulary を実地で探る。 GH workflow
 * log + raw dump に結果を吐いて、 真の class / property URI を特定する。
 *
 * 1. 全 RDF type の上位 50 (= どの class が漫画 manifestation か手掛り)
 * 2. 既知の漫画家名 literal "諫山創" を含む subject の (s, p) ペア
 *    (= 作家 entity の URI と name property の URI を一気に確定する)
 * 3. その作家 URI の outgoing predicate 全部 (= 作家 → 作品の link を発見)
 */
async function discoverSchema(): Promise<{
  topTypes: SparqlBinding[];
  authorMatches: SparqlBinding[];
  authorLinks: SparqlBinding[];
  creatorPatterns: { surname: string; bindings: SparqlBinding[] }[];
}> {
  if (DRY_RUN) {
    return {
      topTypes: [],
      authorMatches: [],
      authorLinks: [],
      creatorPatterns: [],
    };
  }

  // (1) 全 type の出現上位 50。 漫画 class の真名がここに入る想定。
  const topTypesQuery = `
    SELECT ?type (COUNT(?s) AS ?n) WHERE {
      ?s a ?type .
    } GROUP BY ?type ORDER BY DESC(?n) LIMIT 50
  `;
  const topTypes = await sparqlFetch(topTypesQuery);
  console.log(`  [schema] topTypes: ${topTypes.bindings.length} rows`);
  for (const b of topTypes.bindings.slice(0, 15)) {
    console.log(`    ${b["n"]?.value ?? "?"} × ${b["type"]?.value ?? "?"}`);
  }

  // (2) "諫山創" literal を持つ (s, p) ペア。 作家 entity の URI と
  //     name property URI を同時に取れる。 漢字を含むのでこれは
  //     ピンポイントで作家を当てに行く query。
  const authorMatchesQuery = `
    SELECT DISTINCT ?s ?p WHERE {
      ?s ?p ?o .
      FILTER(isLiteral(?o) && STR(?o) = "諫山創")
    } LIMIT 20
  `;
  const authorMatches = await sparqlFetch(authorMatchesQuery);
  console.log(`  [schema] authorMatches "諫山創": ${authorMatches.bindings.length} rows`);
  for (const b of authorMatches.bindings.slice(0, 10)) {
    console.log(
      `    s=${b["s"]?.value ?? "?"} p=${b["p"]?.value ?? "?"}`,
    );
  }

  // (3) (2) で 1 つでも author URI が取れたら、 その URI の outgoing
  //     predicate を列挙して、 「作家 → 作品」 の関係を発見する。
  let authorLinks: SparqlBinding[] = [];
  const firstAuthorUri = authorMatches.bindings[0]?.["s"]?.value;
  if (firstAuthorUri) {
    const authorLinksQuery = `
      SELECT DISTINCT ?p (COUNT(?o) AS ?n) WHERE {
        <${firstAuthorUri}> ?p ?o .
      } GROUP BY ?p ORDER BY DESC(?n) LIMIT 50
    `;
    const r = await sparqlFetch(authorLinksQuery);
    authorLinks = r.bindings;
    console.log(`  [schema] authorLinks for <${firstAuthorUri}>: ${r.bindings.length} rows`);
    for (const b of r.bindings.slice(0, 15)) {
      console.log(`    ${b["n"]?.value ?? "?"} × ${b["p"]?.value ?? "?"}`);
    }
  }

  // (4) 各作家の姓を含む schema:creator literal の全パターン。
  //     Phase 1 で hits=0 / 低件数だった作家の真の表記揺れを発掘する。
  //     例: "諫山創" 完全一致では 1 hit でも、 "諫山" CONTAINS で
  //     "諫山 創" / "諫山 創 (進撃の巨人)" 等の variant が出る想定。
  const creatorPatterns: { surname: string; bindings: SparqlBinding[] }[] = [];
  for (const author of PROBE_AUTHORS) {
    const q = `
      PREFIX schema: <https://schema.org/>
      PREFIX class: <https://mediaarts-db.artmuseums.go.jp/data/class#>
      SELECT ?creator (COUNT(?m) AS ?n) WHERE {
        ?m a class:MangaBook ; schema:creator ?creator .
        FILTER(CONTAINS(STR(?creator), "${author.surname}"))
      } GROUP BY ?creator ORDER BY DESC(?n) LIMIT 30
    `;
    const r = await sparqlFetch(q);
    creatorPatterns.push({ surname: author.surname, bindings: r.bindings });
    console.log(
      `  [schema] creatorPatterns "${author.surname}": ${r.bindings.length} variants`,
    );
    for (const b of r.bindings.slice(0, 8)) {
      console.log(
        `    ${b["n"]?.value ?? "?"} × "${b["creator"]?.value ?? "?"}"`,
      );
    }
    await sleep(500); // SPARQL endpoint への負荷分散
  }

  // raw dump (= artifact 経由でフル内容を回収できるように)
  fs.writeFileSync(
    path.join(OUT_DIR, "_schema-types.json"),
    JSON.stringify(topTypes.bindings, null, 2),
    "utf8",
  );
  fs.writeFileSync(
    path.join(OUT_DIR, "_schema-author-matches.json"),
    JSON.stringify(authorMatches.bindings, null, 2),
    "utf8",
  );
  fs.writeFileSync(
    path.join(OUT_DIR, "_schema-author-links.json"),
    JSON.stringify(authorLinks, null, 2),
    "utf8",
  );
  fs.writeFileSync(
    path.join(OUT_DIR, "_schema-creator-patterns.json"),
    JSON.stringify(creatorPatterns, null, 2),
    "utf8",
  );

  return {
    topTypes: topTypes.bindings,
    authorMatches: authorMatches.bindings,
    authorLinks,
    creatorPatterns,
  };
}

type SparqlBinding = Record<string, { type?: string; value?: string }>;

/**
 * SPARQL を POST で叩く共通関数。 GET は URL 長制限と CDN キャッシュで
 * 不安定なので、 LOD クライアントの慣行通り POST + form-urlencoded を使う。
 */
async function sparqlFetch(query: string): Promise<{
  ok: boolean;
  bindings: SparqlBinding[];
  error: string | null;
}> {
  try {
    const res = await fetch(MADB_SPARQL_ENDPOINT, {
      method: "POST",
      headers: {
        Accept: "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent":
          "MANGAL-MADBProbe/0.1 (+https://github.com/shuichi0725-cmyk/MANGAL)",
      },
      body: `query=${encodeURIComponent(query)}`,
    });
    if (!res.ok) {
      const body = (await res.text()).slice(0, 200);
      return {
        ok: false,
        bindings: [],
        error: `HTTP ${res.status}${body ? `: ${body.replace(/\s+/g, " ")}` : ""}`,
      };
    }
    const j = (await res.json()) as {
      results?: { bindings?: SparqlBinding[] };
    };
    return { ok: true, bindings: j.results?.bindings ?? [], error: null };
  } catch (err) {
    return {
      ok: false,
      bindings: [],
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

async function fetchMadb(authorName: string): Promise<{
  bindings: SparqlBinding[];
  error: string | null;
  queryUsed: string;
}> {
  if (DRY_RUN) return { bindings: [], error: "dry-run", queryUsed: "" };
  // MADB vocabulary (= schema discovery で確定):
  //   schema: prefix         → https://schema.org/  (← https に注意)
  //   class:MangaBook        → 漫画単行本 manifestation (397k 件)
  //   schema:creator         → 作家名 **literal** (= URI 参照ではない)
  //                            例: <id/M848951> schema:creator "諫山創"
  //                            STR() で言語タグ付き literal も吸収。
  //   prop:originalWorkCreator → 原作者 literal (= 必要なら UNION 追加)
  //   schema:isbn / schema:publisher / schema:image / schema:description /
  //     schema:isPartOf は全て https://schema.org/ namespace
  //   publisher / magazine も literal の可能性あり、 .value で吸収。
  // 作家名は STR() 経由で完全一致。 LIMIT 1000 で打切り。
  const query = `
    PREFIX schema: <https://schema.org/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX class: <https://mediaarts-db.artmuseums.go.jp/data/class#>
    SELECT DISTINCT ?manifestation ?title ?isbn ?publisher ?image ?description ?magazine ?creator WHERE {
      ?manifestation a class:MangaBook ;
                     schema:creator ?creator .
      # MADB の creator literal は "[原作]吾峠呼世晴" / "[著]諫山創" /
      # "[作画]<who>" のように役割タグが prefix されたケースが大半。
      # bare 名前 + "]" 直後 + 末尾 のいずれにマッチさせる REGEX で
      # 全パターンを吸収しつつ、 同名別人 ("諫山創 太郎" 等) は弾く。
      FILTER(REGEX(STR(?creator), "(^|\\\\])${authorName}$"))
      OPTIONAL { ?manifestation rdfs:label ?title }
      OPTIONAL { ?manifestation schema:isbn ?isbn }
      OPTIONAL { ?manifestation schema:publisher ?publisher }
      OPTIONAL { ?manifestation schema:image ?image }
      OPTIONAL { ?manifestation schema:description ?description }
      OPTIONAL { ?manifestation schema:isPartOf ?magazine }
    } LIMIT 1000
  `;
  const res = await sparqlFetch(query);
  return { bindings: res.bindings, error: res.error, queryUsed: query };
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

function dumpRaw(authorQid: string, payload: unknown): string {
  const filename = `${safeFilename(authorQid)}.json`;
  const filepath = path.join(OUT_DIR, filename);
  fs.writeFileSync(filepath, JSON.stringify(payload, null, 2), "utf8");
  return path.relative(process.cwd(), filepath);
}

async function processAuthor(author: ProbeAuthor): Promise<AuthorResult> {
  console.log(`\n[probe] ${author.name} (${author.qid})`);
  console.log(`  madb fetching...`);
  const madb = await fetchMadb(author.name);
  const items = madb.bindings.map(normalizeMadbBinding);
  const summary = summarizeSource(items);
  const dumpPath = DRY_RUN ? null : dumpRaw(author.qid, madb.bindings);
  console.log(
    `  madb: hits=${madb.bindings.length} unique-isbn=${summary.uniqueIsbns.length}${madb.error ? ` ERROR=${madb.error}` : ""}`,
  );
  const ndlIsbns = getNdlIsbnsForAuthor(author.qid);
  return {
    author,
    ok: madb.error === null,
    error: madb.error,
    hits: madb.bindings.length,
    items,
    uniqueIsbns: summary.uniqueIsbns,
    rawSamplePath: dumpPath,
    ndlIsbns,
  };
}

function renderMarkdown(
  results: AuthorResult[],
  sanity: { ok: boolean; note: string },
  discovery: {
    topTypes: SparqlBinding[];
    authorMatches: SparqlBinding[];
    authorLinks: SparqlBinding[];
    creatorPatterns: { surname: string; bindings: SparqlBinding[] }[];
  } | null,
): string {
  const now = new Date().toISOString();
  const lines: string[] = [];
  lines.push("---");
  lines.push(`probedAt: "${now}"`);
  lines.push(`endpoint: "${MADB_SPARQL_ENDPOINT}"`);
  lines.push(`dryRun: ${DRY_RUN}`);
  lines.push("---");
  lines.push("");
  lines.push("# MADB (メディア芸術データベース) ISBN 取得 probe");
  lines.push("");
  lines.push(
    "現状の Wikidata QID → CSV alt_names → NDL CQL 経路の構造的限界 (= 別作家混入) を回避するため、",
  );
  lines.push(
    "「MADB から ISBN list を取得 → openBD で metadata 生成」 への移行可否を評価する read-only probe。",
  );
  lines.push("");

  lines.push("## なぜ MADB 単独か");
  lines.push("");
  lines.push("- **ライセンス**: 文化庁 OPEN DATA = CC-BY 4.0 想定 (= 商用 OK / 再配布 OK)");
  lines.push("- **漫画 coverage**: 国内漫画 30 万件超、 国内最強級");
  lines.push(
    "- **雑誌 metadata**: 連載誌・初出誌の link 完備。 NDL にも openBD にも無い唯一の真値",
  );
  lines.push("- **kana**: `mng:titleTranscription` (タイトル) + 作家かな両方あり (想定)");
  lines.push("- **作家名検索の精度**: SPARQL の literal 完全一致で表記揺れを回避可能");
  lines.push("");

  lines.push("## Phase 0: SPARQL endpoint sanity check");
  lines.push("");
  lines.push("| OK | Note |");
  lines.push("|---|---|");
  lines.push(`| ${sanity.ok ? "OK" : "FAIL"} | ${sanity.note} |`);
  lines.push("");

  if (discovery) {
    lines.push("## Phase 0+: schema discovery");
    lines.push("");
    lines.push(
      "実 dataset に存在する vocabulary を SPARQL で発掘した結果。 真の class / property URI を特定するための最重要セクション。",
    );
    lines.push("");

    lines.push("### Top RDF types (上位 50)");
    lines.push("");
    lines.push("| count | type URI |");
    lines.push("|---|---|");
    for (const b of discovery.topTypes.slice(0, 50)) {
      lines.push(`| ${b["n"]?.value ?? "?"} | \`${b["type"]?.value ?? "?"}\` |`);
    }
    lines.push("");

    lines.push("### \"諫山創\" literal を持つ (s, p) ペア");
    lines.push("");
    lines.push("| subject (= 作家 entity URI) | predicate (= name property URI) |");
    lines.push("|---|---|");
    for (const b of discovery.authorMatches) {
      lines.push(`| \`${b["s"]?.value ?? "?"}\` | \`${b["p"]?.value ?? "?"}\` |`);
    }
    lines.push("");

    lines.push("### 作家 entity の outgoing predicates (= 作品への link)");
    lines.push("");
    lines.push("| count | predicate URI |");
    lines.push("|---|---|");
    for (const b of discovery.authorLinks.slice(0, 50)) {
      lines.push(`| ${b["n"]?.value ?? "?"} | \`${b["p"]?.value ?? "?"}\` |`);
    }
    lines.push("");

    lines.push("### 各作家の姓 CONTAINS で発掘した creator literal パターン (上位 30)");
    lines.push("");
    lines.push(
      "Phase 1 で hits=0 / 低件数だった作家の真の表記揺れを直接観察する。 表記が判明したら次回 commit で fetchMadb の filter を拡張する。",
    );
    lines.push("");
    for (const cp of discovery.creatorPatterns) {
      lines.push(`#### "${cp.surname}" を含む creator literal`);
      lines.push("");
      if (cp.bindings.length === 0) {
        lines.push("(該当なし)");
      } else {
        lines.push("| count | creator literal |");
        lines.push("|---|---|");
        for (const b of cp.bindings) {
          lines.push(
            `| ${b["n"]?.value ?? "?"} | \`${(b["creator"]?.value ?? "?").replace(/\|/g, "\\|")}\` |`,
          );
        }
      }
      lines.push("");
    }
  }

  lines.push("## Phase 1: per-mangaka 結果");
  lines.push("");
  lines.push(
    "| 作家 | QID | hits | uniq ISBN | cover% | desc% | pub% | mag% | NDL ISBN | MADB∩NDL |",
  );
  lines.push("|---|---|---|---|---|---|---|---|---|---|");
  for (const r of results) {
    const s = summarizeSource(r.items);
    const overlap = intersect(r.uniqueIsbns, r.ndlIsbns).length;
    lines.push(
      `| ${r.author.name} | ${r.author.qid} | ${r.hits} | ${r.uniqueIsbns.length} | ${pct(s.withCover, r.hits)} | ${pct(s.withDesc, r.hits)} | ${pct(s.withPublisher, r.hits)} | ${pct(s.withMagazine, r.hits)} | ${r.ndlIsbns.length} | ${overlap} |`,
    );
  }
  lines.push("");

  const errors = results.filter((r) => r.error).map((r) => `- ${r.author.name}: ${r.error}`);
  if (errors.length > 0) {
    lines.push("## エラーサマリ");
    lines.push("");
    lines.push(...errors);
    lines.push("");
  }

  lines.push("## Raw response dumps");
  lines.push("");
  for (const r of results) {
    if (r.rawSamplePath) {
      lines.push(`- ${r.author.name} (${r.author.qid}): \`${r.rawSamplePath}\``);
    }
  }
  lines.push("");

  // 推奨判断 (= probe 結果から自動 derive)
  lines.push("## 推奨判断 (probe 結果ベース)");
  lines.push("");
  const totalIsbns = results.reduce((s, r) => s + r.uniqueIsbns.length, 0);
  const errCount = results.filter((r) => r.error).length;
  lines.push(`- 全 6 作家で計 ${totalIsbns} unique ISBN、 ${errCount}/6 でエラー`);
  lines.push("");
  if (errCount === 6) {
    lines.push(
      "→ MADB SPARQL endpoint 到達不能。 endpoint URL の確認 (= `bunka.go.jp` か `artmuseums.go.jp` か) と、 LOD ダンプ DL 経由のフォールバック設計が必要。",
    );
  } else if (errCount > 0) {
    lines.push("→ 一部作家でエラー。 query 構造または rate-limit の調整が必要。");
  } else if (totalIsbns === 0) {
    lines.push(
      "→ endpoint には到達したが SPARQL query が hit しない。 `schema:author` 想定が外れている可能性大。 LOD vocabulary の実地調査が必要。",
    );
  } else {
    lines.push("→ MADB 採用が妥当。 本格 fetcher 実装 (= 次プラン) に進める。");
  }
  lines.push("");
  lines.push("## 次プラン候補");
  lines.push("");
  lines.push("- 本格 fetcher 実装 (= `scripts/fetch-madb.ts`)");
  lines.push("- DB schema 拡張 (= `sources` テーブルへの provenance、 隔離テーブル `volumes_madb`)");
  lines.push("- 既存 NDL ISBN との merge ロジック設計 (= 上書き優先順位)");
  lines.push("- bulk-promote-test workflow への step 追加");
  lines.push("");

  return lines.join("\n") + "\n";
}

async function main(): Promise<void> {
  console.log(`[probe-madb] start (dryRun=${DRY_RUN})`);
  ensureDir(OUT_DIR);
  ensureDir(path.dirname(DOCS_PATH));

  // Phase 0
  console.log("\n=== Phase 0: SPARQL endpoint sanity check ===");
  const sanity = await probeSanity();
  console.log(`  madb: ${sanity.ok ? "OK" : "FAIL"} (${sanity.note})`);

  // Phase 0+: schema discovery (= class:MangaBook count=0 だった場合に
  // 真の vocabulary を実地で発見するための調査 phase。 endpoint OK
  // なら必ず実行して log + raw dump を残す)
  let discovery: Awaited<ReturnType<typeof discoverSchema>> | null = null;
  if (sanity.ok) {
    console.log("\n=== Phase 0+: schema discovery ===");
    discovery = await discoverSchema();
  }

  // Phase 1
  console.log("\n=== Phase 1: per-mangaka probe ===");
  const results: AuthorResult[] = [];
  for (const author of PROBE_AUTHORS) {
    results.push(await processAuthor(author));
    await sleep(MADB_INTERVAL_MS);
  }

  // Phase 2 & 3
  console.log("\n=== Phase 2: aggregate + write Markdown ===");
  const md = renderMarkdown(results, sanity, discovery);
  fs.writeFileSync(DOCS_PATH, md, "utf8");
  console.log(`  wrote ${path.relative(process.cwd(), DOCS_PATH)}`);
  console.log(`  raw dumps in ${path.relative(process.cwd(), OUT_DIR)}/`);

  console.log("\n[probe-madb] done");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

/**
 * Wikidata SPARQL から日本の漫画家一覧を取得し、CSV に書き出す。
 *
 * 使い方（外部ネットワークが届く環境で）:
 *   npm run fetch:mangaka                # 全件取得
 *   npm run fetch:mangaka -- --limit 50  # テスト用に 50 件だけ
 *   npm run fetch:mangaka -- --query-only # SPARQL を表示するだけ
 *
 * 出力: data/seed/mangaka.csv
 *   columns: qid, name, birth_year, death_year, alt_names, has_adult_credit
 *
 * `has_adult_credit = true` のレコードは、楽天ブックス取得時に **必ず除外** すること。
 * Amazon アソシエイト規約で成年向けコンテンツの掲載は禁止されている。
 */
import fs from "node:fs";
import path from "node:path";

const ENDPOINT = "https://query.wikidata.org/sparql";
const USER_AGENT =
  "MANGAL-DataFetch/0.1 (https://github.com/shuichi0725-cmyk/mangal; contact: TODO)";

const PAGE_SIZE = 1000;
const ALT_BATCH_SIZE = 200;
const MAX_RETRIES = 4;

/**
 * mangaka 本体の取得クエリ（生没年のみ。altLabels は別クエリでバッチ取得）
 *
 * occupation (P106) は 2 種類を許可する:
 *   - Q191633   = mangaka / 漫画家（本命。手塚治虫・鳥山明など多数）
 *   - Q1114448  = 別表記の comics artist 系（一部の日本人漫画家もこちら）
 *
 * 国別の絞り込みとして以下も AND する:
 *   - 日本語 Wikipedia 記事がある (schema:isPartOf ja.wikipedia.org)
 *   - 国籍が日本 (P27 = Q17)
 *
 * altLabels の OPTIONAL を含めると Wikidata 側がタイムアウトしやすいので
 * QID リストを得たあとに別クエリでまとめて取得する。
 */
const QUERY_BASE = (limit: number, offset: number) => `
SELECT
  ?mangaka
  ?mangakaLabel
  (SAMPLE(?birth) AS ?birthYear)
  (SAMPLE(?death) AS ?deathYear)
WHERE {
  VALUES ?occ { wd:Q191633 wd:Q1114448 }
  ?article schema:about ?mangaka ;
           schema:isPartOf <https://ja.wikipedia.org/> .
  ?mangaka wdt:P31 wd:Q5 ;                # instance of: human
           wdt:P106 ?occ ;                 # occupation: mangaka or comics artist
           wdt:P27 wd:Q17 ;                # country of citizenship: Japan
           rdfs:label ?mangakaLabel .
  FILTER(LANG(?mangakaLabel) = "ja")
  OPTIONAL {
    ?mangaka wdt:P569 ?birthDate .
    BIND(YEAR(?birthDate) AS ?birth)
  }
  OPTIONAL {
    ?mangaka wdt:P570 ?deathDate .
    BIND(YEAR(?deathDate) AS ?death)
  }
}
GROUP BY ?mangaka ?mangakaLabel
ORDER BY ?mangaka
LIMIT ${limit} OFFSET ${offset}`;

/** 既知 QID 群の altLabel をまとめて取得 */
const QUERY_ALT_LABELS = (qids: string[]) => `
SELECT ?mangaka ?alt WHERE {
  VALUES ?mangaka { ${qids.map((q) => `wd:${q}`).join(" ")} }
  ?mangaka skos:altLabel ?alt .
  FILTER(LANG(?alt) = "ja")
}`;

/** hentai (Q172241) ジャンルの作品をクレジットされた mangaka を抽出 */
const QUERY_ADULT = `
SELECT DISTINCT ?mangaka WHERE {
  VALUES ?occ { wd:Q191633 wd:Q1114448 }
  ?mangaka wdt:P106 ?occ .
  ?work wdt:P50 ?mangaka ;
        wdt:P136 wd:Q172241 .
}`;

type Binding = Record<string, { value: string } | undefined>;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function sparqlOnce(query: string): Promise<Binding[]> {
  // 大きい SPARQL は POST + form body の方が安全（URL 長制限を避ける）
  const res = await fetch(ENDPOINT, {
    method: "POST",
    headers: {
      "User-Agent": USER_AGENT,
      Accept: "application/sparql-results+json",
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: `query=${encodeURIComponent(query)}`,
  });
  if (!res.ok) {
    const body = await res.text();
    const excerpt = body.length > 500 ? `${body.slice(0, 500)}…(truncated)` : body;
    throw new Error(`SPARQL HTTP ${res.status} ${res.statusText}: ${excerpt}`);
  }
  const json = (await res.json()) as { results: { bindings: Binding[] } };
  return json.results.bindings;
}

async function sparql(query: string, label: string): Promise<Binding[]> {
  let lastErr: unknown;
  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await sparqlOnce(query);
    } catch (err) {
      lastErr = err;
      const msg = err instanceof Error ? err.message : String(err);
      const retriable = /HTTP (429|5\d\d)/.test(msg) || /timeout|ETIMEDOUT|ECONNRESET|fetch failed/i.test(msg);
      if (!retriable || attempt === MAX_RETRIES) break;
      const delay = 2000 * 2 ** (attempt - 1); // 2s, 4s, 8s
      console.warn(`  [${label}] attempt ${attempt} failed: ${msg}`);
      console.warn(`  [${label}] retry in ${delay}ms…`);
      await sleep(delay);
    }
  }
  throw lastErr;
}

async function fetchMainPaged(totalLimit?: number): Promise<Binding[]> {
  const all: Binding[] = [];
  let offset = 0;
  while (true) {
    const remaining = totalLimit ? totalLimit - all.length : Infinity;
    if (remaining <= 0) break;
    const pageSize = Math.min(PAGE_SIZE, remaining);
    const query = QUERY_BASE(pageSize, offset);
    const page = await sparql(query, `main offset=${offset}`);
    console.log(`  - offset=${offset} → ${page.length} 件 (累計 ${all.length + page.length})`);
    all.push(...page);
    if (page.length < pageSize) break;
    offset += pageSize;
  }
  return all;
}

async function fetchAltLabels(qids: string[]): Promise<Map<string, string[]>> {
  const map = new Map<string, string[]>();
  for (let i = 0; i < qids.length; i += ALT_BATCH_SIZE) {
    const batch = qids.slice(i, i + ALT_BATCH_SIZE);
    const bindings = await sparql(
      QUERY_ALT_LABELS(batch),
      `alt batch ${i}-${i + batch.length}`,
    );
    for (const b of bindings) {
      const qidUrl = b.mangaka?.value ?? "";
      const qid = qidUrl.replace("http://www.wikidata.org/entity/", "");
      const alt = b.alt?.value ?? "";
      if (!qid || !alt) continue;
      const list = map.get(qid) ?? [];
      list.push(alt);
      map.set(qid, list);
    }
    console.log(`  - alt batch ${i}-${i + batch.length} 完了`);
  }
  return map;
}

type Row = {
  qid: string;
  name: string;
  birth_year: string;
  death_year: string;
  alt_names: string;
  has_adult_credit: string;
};

function csvEscape(s: string): string {
  if (s === "") return "";
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function parseArgs(argv: string[]): { limit?: number; queryOnly: boolean } {
  let limit: number | undefined;
  let queryOnly = false;
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--limit" && argv[i + 1]) {
      limit = Number(argv[++i]);
    } else if (argv[i] === "--query-only") {
      queryOnly = true;
    }
  }
  return { limit, queryOnly };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));

  if (args.queryOnly) {
    console.log("=== mangaka 取得クエリ (1ページ目) ===\n" + QUERY_BASE(PAGE_SIZE, 0));
    console.log("\n=== altLabels クエリ (例) ===\n" + QUERY_ALT_LABELS(["Q193300"]));
    console.log("\n=== hentai クレジット抽出クエリ ===\n" + QUERY_ADULT);
    return;
  }

  console.log("[1/3] Wikidata から mangaka 一覧を取得中…");
  const mainBindings = await fetchMainPaged(args.limit);
  console.log(`  → 合計 ${mainBindings.length} 件`);

  const qids = mainBindings
    .map((b) => b.mangaka?.value?.replace("http://www.wikidata.org/entity/", "") ?? "")
    .filter((q) => q.length > 0);

  console.log(`[2/3] altLabels を ${qids.length} 件分バッチ取得中…`);
  const altMap = await fetchAltLabels(qids);
  console.log(`  → ${altMap.size} 件に altLabel あり`);

  console.log("[3/3] hentai クレジットがある mangaka を抽出中…");
  const adultBindings = await sparql(QUERY_ADULT, "adult");
  const adultSet = new Set(
    adultBindings.map((b) => b.mangaka?.value).filter((v): v is string => !!v),
  );
  console.log(`  → ${adultSet.size} 件をブラックリストに登録`);

  const rows: Row[] = mainBindings.map((b) => {
    const qidUrl = b.mangaka?.value ?? "";
    const qid = qidUrl.replace("http://www.wikidata.org/entity/", "");
    const alts = altMap.get(qid) ?? [];
    return {
      qid,
      name: b.mangakaLabel?.value ?? "",
      birth_year: b.birthYear?.value ?? "",
      death_year: b.deathYear?.value ?? "",
      alt_names: [...new Set(alts)].join("|"),
      has_adult_credit: adultSet.has(qidUrl) ? "true" : "false",
    };
  });

  rows.sort((a, b) => a.name.localeCompare(b.name, "ja"));

  const outDir = path.join(process.cwd(), "data", "seed");
  fs.mkdirSync(outDir, { recursive: true });
  const outPath = path.join(outDir, "mangaka.csv");

  const header = "qid,name,birth_year,death_year,alt_names,has_adult_credit";
  const lines = [
    header,
    ...rows.map((r) =>
      [r.qid, r.name, r.birth_year, r.death_year, r.alt_names, r.has_adult_credit]
        .map(csvEscape)
        .join(","),
    ),
  ];
  fs.writeFileSync(outPath, lines.join("\n") + "\n", "utf8");

  const adultCount = rows.filter((r) => r.has_adult_credit === "true").length;
  console.log(`\n[wrote] ${outPath}`);
  console.log(`        total           : ${rows.length}`);
  console.log(`        with adult credit: ${adultCount} (取得時に除外対象)`);
  console.log(`        usable           : ${rows.length - adultCount}`);
}

main().catch((err) => {
  console.error("[fatal]", err);
  process.exit(1);
});

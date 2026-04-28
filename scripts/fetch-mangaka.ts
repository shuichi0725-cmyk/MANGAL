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

/**
 * mangaka 本体の取得クエリ（生没年・別名込み）
 *
 * occupation (P106) は 2 種類を許可する:
 *   - Q191633   = mangaka / 漫画家（本命。手塚治虫・鳥山明など多数）
 *   - Q1114448  = 別表記の comics artist 系（一部の日本人漫画家もこちら）
 *
 * 国別の絞り込みとして以下も AND する:
 *   - 日本語 Wikipedia 記事がある (schema:isPartOf ja.wikipedia.org)
 *   - 国籍が日本 (P27 = Q17)
 */
const QUERY_BASE = (limit?: number) => `
SELECT
  ?mangaka
  ?mangakaLabel
  (SAMPLE(?birth) AS ?birthYear)
  (SAMPLE(?death) AS ?deathYear)
  (GROUP_CONCAT(DISTINCT ?alt; separator="|") AS ?altNames)
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
  OPTIONAL {
    ?mangaka skos:altLabel ?alt .
    FILTER(LANG(?alt) = "ja")
  }
}
GROUP BY ?mangaka ?mangakaLabel
${limit ? `LIMIT ${limit}` : ""}`;

/** hentai (Q172241) ジャンルの作品をクレジットされた mangaka を抽出 */
const QUERY_ADULT = `
SELECT DISTINCT ?mangaka WHERE {
  VALUES ?occ { wd:Q191633 wd:Q1114448 }
  ?mangaka wdt:P106 ?occ .
  ?work wdt:P50 ?mangaka ;
        wdt:P136 wd:Q172241 .
}`;

type Binding = Record<string, { value: string } | undefined>;

async function sparql(query: string): Promise<Binding[]> {
  const url = `${ENDPOINT}?query=${encodeURIComponent(query)}&format=json`;
  const res = await fetch(url, {
    headers: {
      "User-Agent": USER_AGENT,
      Accept: "application/sparql-results+json",
    },
  });
  if (!res.ok) {
    throw new Error(`SPARQL HTTP ${res.status}: ${await res.text()}`);
  }
  const json = (await res.json()) as { results: { bindings: Binding[] } };
  return json.results.bindings;
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
    console.log("=== mangaka 取得クエリ ===\n" + QUERY_BASE(args.limit));
    console.log("\n=== hentai クレジット抽出クエリ ===\n" + QUERY_ADULT);
    return;
  }

  console.log("[1/2] Wikidata から mangaka 一覧を取得中…");
  const mainBindings = await sparql(QUERY_BASE(args.limit));
  console.log(`  → ${mainBindings.length} 件`);

  console.log("[2/2] hentai クレジットがある mangaka を抽出中…");
  const adultBindings = await sparql(QUERY_ADULT);
  const adultSet = new Set(
    adultBindings.map((b) => b.mangaka?.value).filter((v): v is string => !!v),
  );
  console.log(`  → ${adultSet.size} 件をブラックリストに登録`);

  const rows: Row[] = mainBindings.map((b) => {
    const qidUrl = b.mangaka?.value ?? "";
    const qid = qidUrl.replace("http://www.wikidata.org/entity/", "");
    return {
      qid,
      name: b.mangakaLabel?.value ?? "",
      birth_year: b.birthYear?.value ?? "",
      death_year: b.deathYear?.value ?? "",
      alt_names: b.altNames?.value ?? "",
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
  console.error(err);
  process.exit(1);
});

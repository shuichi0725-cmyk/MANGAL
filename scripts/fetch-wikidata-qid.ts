/**
 * B3.2: 各 manga yaml から Wikidata の QID を取得して書き戻す。
 *
 * 戦略 (= ハイブリッド):
 *   Step 1: wikipedia_url が yaml にあれば、 タイトル抽出 → Wikidata の sitelink
 *           lookup で 1 発で QID 取得 (= 高精度)
 *   Step 2: 無ければ wbsearchentities で title 検索 → 候補をbatchで wbgetentities
 *           で取得 → P31 (instance of) が manga 系 + P50 (author) が我々の著者と
 *           一致するものを選ぶ。 author 一致した = high confidence、 一致しないが
 *           manga 確認できた = low confidence
 *
 * 既に wikidata_qid を持つ yaml はスキップ (idempotent、 --force で上書き)。
 *
 *   npm run fetch:wikidata:qid                  # 全件 dry-run (= 実 yaml 編集なし)
 *   npm run fetch:wikidata:qid -- --apply       # 実際に yaml に書き込み
 *   npm run fetch:wikidata:qid -- --slug X      # 1 件のみ (debug 用)
 *   npm run fetch:wikidata:qid -- --apply --force  # 既存 QID も上書き
 */
import "./_env";
import fs from "node:fs";
import path from "node:path";
import YAML from "yaml";
import { MangaSchema, type Manga } from "../lib/schema";

const WIKIDATA_API = "https://www.wikidata.org/w/api.php";
const REQUEST_INTERVAL_MS = 1100;
const USER_AGENT =
  "MANGAL-WikidataQid/0.1 (+https://github.com/shuichi0725-cmyk/MANGAL)";

/**
 * P31 (instance of) で manga と判定する QID 集合。 Wikidata 上の漫画関連
 * クラスは複数あるので broad に集める。 検証用 (= 候補 entity の P31 が
 * これらのいずれかなら manga 系とみなす)。
 */
const MANGA_INSTANCE_QIDS = new Set([
  "Q838795", // manga
  "Q14406742", // manga series
  "Q1004", // comics (broad parent)
  "Q21198342", // comic book series
  "Q747381", // light novel — manga adaptation の元になりやすい
  "Q571", // book (super-broad fallback)
  "Q47461344", // written work
  "Q386724", // work
]);

type Args = {
  dryRun: boolean;
  apply: boolean;
  force: boolean;
  slug: string | null;
  skipSlugs: Set<string>;
};

function parseArgs(argv: string[]): Args {
  const out: Args = {
    dryRun: true,
    apply: false,
    force: false,
    slug: null,
    skipSlugs: new Set(),
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--apply") {
      out.apply = true;
      out.dryRun = false;
    } else if (a === "--dry-run") {
      out.dryRun = true;
      out.apply = false;
    } else if (a === "--force") out.force = true;
    else if (a === "--slug" && argv[i + 1]) out.slug = argv[++i];
    else if (a === "--skip-slugs" && argv[i + 1]) {
      const list = argv[++i].split(",").map((x) => x.trim()).filter(Boolean);
      for (const s of list) out.skipSlugs.add(s);
    }
  }
  return out;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function wikidataApi(params: Record<string, string>): Promise<unknown> {
  const url = new URL(WIKIDATA_API);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  url.searchParams.set("format", "json");
  url.searchParams.set("origin", "*");
  const res = await fetch(url.toString(), {
    headers: { "User-Agent": USER_AGENT, Accept: "application/json" },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Wikidata HTTP ${res.status}: ${body.slice(0, 200)}`);
  }
  return res.json();
}

type SearchResult = { id: string; label: string; description?: string };

async function searchEntities(query: string): Promise<SearchResult[]> {
  const json = (await wikidataApi({
    action: "wbsearchentities",
    search: query,
    language: "ja",
    type: "item",
    limit: "20",
  })) as { search?: SearchResult[] };
  return json.search ?? [];
}

type EntityClaim = {
  mainsnak?: {
    datavalue?: { value?: { id?: string } };
  };
};

type Entity = {
  labels?: Record<string, { value?: string }>;
  aliases?: Record<string, { value?: string }[]>;
  claims?: Record<string, EntityClaim[]>;
  sitelinks?: Record<string, { title?: string }>;
};

async function getEntities(qids: string[]): Promise<Record<string, Entity>> {
  if (qids.length === 0) return {};
  const json = (await wikidataApi({
    action: "wbgetentities",
    ids: qids.join("|"),
    languages: "ja|en|fr|de|it|pt",
    props: "labels|aliases|claims|sitelinks",
  })) as { entities?: Record<string, Entity> };
  return json.entities ?? {};
}

function isMangaInstance(entity: Entity): boolean {
  const p31 = entity.claims?.P31 ?? [];
  for (const claim of p31) {
    const id = claim.mainsnak?.datavalue?.value?.id;
    if (id && MANGA_INSTANCE_QIDS.has(id)) return true;
  }
  return false;
}

/** P31 のラベルを取得 (debug 用) */
function p31Labels(entity: Entity): string[] {
  const p31 = entity.claims?.P31 ?? [];
  return p31
    .map((c) => c.mainsnak?.datavalue?.value?.id)
    .filter((x): x is string => Boolean(x));
}

async function authorMatches(
  entity: Entity,
  expectedAuthors: string[],
): Promise<{ matched: boolean; wikidataAuthors: string[] }> {
  const p50 = entity.claims?.P50 ?? [];
  const authorQids = p50
    .map((c) => c.mainsnak?.datavalue?.value?.id)
    .filter((x): x is string => Boolean(x));
  if (authorQids.length === 0) return { matched: false, wikidataAuthors: [] };

  await sleep(REQUEST_INTERVAL_MS);
  const authorEntities = await getEntities(authorQids);
  const wikidataAuthors: string[] = [];
  for (const aqid of authorQids) {
    const ae = authorEntities[aqid];
    if (!ae) continue;
    const ja = ae.labels?.ja?.value;
    if (ja) wikidataAuthors.push(ja);
    const aliases = ae.aliases?.ja ?? [];
    for (const al of aliases) {
      if (al.value) wikidataAuthors.push(al.value);
    }
  }

  const matched = expectedAuthors.some((name) => wikidataAuthors.includes(name));
  return { matched, wikidataAuthors };
}

type FindResult = {
  qid: string;
  confidence: "high" | "low";
  rationale: string;
} | null;

async function findQid(manga: Manga): Promise<FindResult> {
  // Step 1: Wikipedia URL → QID via sitelink lookup
  if (manga.wikipedia_url) {
    const m = manga.wikipedia_url.match(/\/wiki\/([^?#]+)$/);
    if (m) {
      const articleTitle = decodeURIComponent(m[1].replace(/_/g, " "));
      try {
        const json = (await wikidataApi({
          action: "wbgetentities",
          sites: "jawiki",
          titles: articleTitle,
          languages: "ja",
          props: "info",
        })) as { entities?: Record<string, { id?: string; missing?: string }> };
        const entities = json.entities ?? {};
        for (const e of Object.values(entities)) {
          if (e.id && !e.missing && /^Q\d+$/.test(e.id)) {
            return {
              qid: e.id,
              confidence: "high",
              rationale: `wikipedia_url sitelink → ${e.id}`,
            };
          }
        }
      } catch (err) {
        // fall through to search
        console.warn(
          `  [warn] sitelink lookup failed: ${(err as Error).message.slice(0, 80)}`,
        );
      }
      await sleep(REQUEST_INTERVAL_MS);
    }
  }

  // Step 2: title search (= title 単独でまず試す)
  const expectedAuthors = manga.authors.map((a) => a.name);
  const queries = [manga.title];
  // 短い / 一般的 title の場合は title+著者 で再検索 (= "NANA" 単独だと同名異作品が
  // top10 を埋めるので manga が埋もれる)
  if (expectedAuthors.length > 0) {
    queries.push(`${manga.title} ${expectedAuthors[0]}`);
  }

  const seenIds = new Set<string>();
  const allCandidates: SearchResult[] = [];
  let firstSearch = true;
  for (const q of queries) {
    if (!firstSearch) await sleep(REQUEST_INTERVAL_MS);
    firstSearch = false;
    const results = await searchEntities(q);
    for (const r of results) {
      if (!seenIds.has(r.id)) {
        seenIds.add(r.id);
        allCandidates.push(r);
      }
    }
  }
  if (allCandidates.length === 0) return null;

  await sleep(REQUEST_INTERVAL_MS);
  const entityData = await getEntities(allCandidates.map((c) => c.id));

  // Pass 1: title match + author match → high confidence
  for (const c of allCandidates) {
    const e = entityData[c.id];
    if (!e || !isMangaInstance(e)) continue;
    const { matched, wikidataAuthors } = await authorMatches(e, expectedAuthors);
    if (matched) {
      return {
        qid: c.id,
        confidence: "high",
        rationale: `title=${c.label} P31=manga P50 ⊃ {${wikidataAuthors.slice(0, 2).join(",")}}`,
      };
    }
  }

  // Pass 2: title match + manga instance, no author match → low confidence
  for (const c of allCandidates) {
    const e = entityData[c.id];
    if (!e || !isMangaInstance(e)) continue;
    return {
      qid: c.id,
      confidence: "low",
      rationale: `title=${c.label} P31=${p31Labels(e).join(",")} (no author match)`,
    };
  }

  return null;
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  console.log(
    `[fetch:wikidata-qid] mode=${args.apply ? "APPLY" : "DRY-RUN"}` +
      (args.force ? " (force=true)" : "") +
      (args.slug ? ` slug=${args.slug}` : ""),
  );

  const dir = path.join(process.cwd(), "data", "manga");
  const files = fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".yml") && !f.startsWith("_"))
    .filter((f) => !args.slug || f === `${args.slug}.yml`);

  const stats = {
    total: files.length,
    skippedExisting: 0,
    foundHigh: 0,
    foundLow: 0,
    notFound: 0,
    written: 0,
    errors: 0,
  };

  let firstReq = true;
  for (const file of files) {
    const filepath = path.join(dir, file);
    const text = fs.readFileSync(filepath, "utf8");
    let manga: Manga;
    try {
      manga = MangaSchema.parse(YAML.parse(text));
    } catch (err) {
      console.warn(`[invalid] ${file}: ${(err as Error).message.slice(0, 80)}`);
      stats.errors++;
      continue;
    }

    if (manga.wikidata_qid && !args.force) {
      console.log(`[skip-existing] ${manga.slug} (qid=${manga.wikidata_qid})`);
      stats.skippedExisting++;
      continue;
    }

    if (args.skipSlugs.has(manga.slug)) {
      console.log(`[skip-list] ${manga.slug} (--skip-slugs に含まれる)`);
      stats.skippedExisting++;
      continue;
    }

    if (!firstReq) await sleep(REQUEST_INTERVAL_MS);
    firstReq = false;

    process.stdout.write(`[${manga.slug}] ${manga.title} ... `);
    let result: FindResult = null;
    try {
      result = await findQid(manga);
    } catch (err) {
      console.log(`✗ error: ${(err as Error).message.slice(0, 80)}`);
      stats.errors++;
      continue;
    }

    if (!result) {
      console.log("✗ not-found");
      stats.notFound++;
      continue;
    }

    const tag = result.confidence === "high" ? "✓" : "?";
    console.log(`${tag} ${result.qid} [${result.confidence}] ${result.rationale}`);
    if (result.confidence === "high") stats.foundHigh++;
    else stats.foundLow++;

    if (args.apply) {
      // Insert wikidata_qid right before "editions:" line.
      const newLine = `wikidata_qid: ${result.qid}\n`;
      let updated: string;
      if (manga.wikidata_qid) {
        // Replace existing line (--force path)
        updated = text.replace(/^wikidata_qid:[^\n]*\n/m, newLine);
      } else {
        // Insert before "editions:" line
        updated = text.replace(/^editions:/m, `${newLine}editions:`);
      }
      if (updated === text) {
        console.warn(`  [no-anchor] ${manga.slug}: editions: が見つからず`);
        continue;
      }
      fs.writeFileSync(filepath, updated);
      stats.written++;
    }
  }

  console.log(`\n=== fetch:wikidata-qid summary ===`);
  console.log(`  total scanned        : ${stats.total}`);
  console.log(`  skipped (existing)   : ${stats.skippedExisting}`);
  console.log(`  found (high conf)    : ${stats.foundHigh}`);
  console.log(`  found (low conf)     : ${stats.foundLow}`);
  console.log(`  not-found            : ${stats.notFound}`);
  console.log(`  errors               : ${stats.errors}`);
  if (args.apply) {
    console.log(`  yaml written         : ${stats.written}`);
  } else {
    console.log(`  (dry-run、 yaml は変更されていません)`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

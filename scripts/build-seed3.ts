/**
 * 種3 (= series-supplement.yml) を AI 一括補完で生成する。
 *
 * 入力: 既存 DB (= 種2 由来 series/editions/volumes/sources)
 * 出力: data/seeds/series-supplement.yml
 *
 * 各 series で以下を Haiku 4.5 (= claude-haiku-4-5) に問合せ、 JSON で受け取る:
 *   slug, magazine, demographic, genres, synopsis, status, anime_adapted, awards
 *
 * 起動例:
 *   npm run seed:build3                                   # 全 series
 *   npm run seed:build3 -- --seed-file data/seed/e2e-21.txt  # 21 mangaka 限定
 *   npm run seed:build3 -- --diff-mode                     # 既存 entry skip
 *   npm run seed:build3 -- --concurrency 50                # 並列度
 *   npm run seed:build3 -- --dry-run                       # API call せず stub 出力
 *
 * 環境変数:
 *   ANTHROPIC_API_KEY (= 必須、 .env.local に置く)
 *   SEED3_MODEL       (= 既定 claude-haiku-4-5、 上書き用)
 */
import "./_env";
import fs from "node:fs";
import path from "node:path";
import Anthropic from "@anthropic-ai/sdk";
import { openDb } from "./_db";
import {
  Seed3FileSchema,
  Seed3EntrySchema,
  loadSeed3,
  seed3Key,
  writeSeed3,
  type Seed3Entry,
  type Seed3File,
} from "../lib/seed3";
import { baseTitle as toBaseTitle } from "../lib/edition";
import yaml from "yaml";

const DEFAULT_PATH = "data/seeds/series-supplement.yml";
const DEFAULT_MODEL = process.env.SEED3_MODEL ?? "claude-haiku-4-5";

type Args = {
  outPath: string;
  seedFile: string | null;
  diffMode: boolean;
  slugs: string[];
  limit: number | null;
  concurrency: number;
  dryRun: boolean;
};

function parseArgs(argv: string[]): Args {
  const a: Args = {
    outPath: DEFAULT_PATH,
    seedFile: null,
    diffMode: false,
    slugs: [],
    limit: null,
    concurrency: 20,
    dryRun: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const x = argv[i];
    if (x === "--out") a.outPath = argv[++i];
    else if (x === "--seed-file") a.seedFile = argv[++i];
    else if (x === "--diff-mode") a.diffMode = true;
    else if (x === "--slugs") a.slugs = argv[++i].split(",").filter(Boolean);
    else if (x === "--limit") a.limit = parseInt(argv[++i], 10);
    else if (x === "--concurrency") a.concurrency = parseInt(argv[++i], 10);
    else if (x === "--dry-run") a.dryRun = true;
  }
  return a;
}

function loadSeedQids(seedFile: string): Set<string> {
  const text = fs.readFileSync(seedFile, "utf8");
  const qids = new Set<string>();
  for (const line of text.split(/\r?\n/)) {
    const m = line.match(/Q\d+/);
    if (m) qids.add(m[0]);
  }
  return qids;
}

type SeriesContext = {
  qid: string | null;
  baseTitle: string;
  title: string;
  authorName: string;
  publisher: string | null;
  imprint: string | null;
  yearStarted: number | null;
  yearEnded: number | null;
  volumeCount: number;
  sampleTitles: string[];
};

const VALID_GENRES = new Set([
  "action", "adventure", "fantasy", "sci-fi", "mystery", "horror",
  "gag", "comedy", "romcom", "romance", "drama", "slice-of-life",
  "school", "sports", "historical", "samurai", "mecha", "yokai",
  "gourmet", "4-koma", "essay", "isekai", "bl", "suspense", "music",
]);

const VALID_DEMOGRAPHICS = new Set([
  "shounen", "shoujo", "seinen", "josei", "kodomo", "other",
]);

function loadValidMagazineKeys(): Set<string> {
  const text = fs.readFileSync("data/magazines.yml", "utf8");
  const keys = new Set<string>();
  for (const line of text.split("\n")) {
    const m = line.match(/^([a-z0-9-]+):/);
    if (m) keys.add(m[1]);
  }
  return keys;
}

const SYSTEM_PROMPT = `あなたは漫画作品のメタデータ補完アシスタント。
漫画 1 作品の情報を受け取り、 以下 8 fields を JSON で返す:
  slug          - 半角英数 + ハイフンのみの URL slug (= 例 "shingeki-no-kyojin")
  magazine      - 連載誌の master key (= 後述 enum) または null
  demographic   - "shounen" | "shoujo" | "seinen" | "josei" | "kodomo" | "other"
  genres        - genre key の array、 **3-8 個 推奨** (短編 / アンソロジー / 1-shot は 1-3 個でも OK)、 後述 enum のみ
  synopsis      - 80-200 字の独自要約 (= 「物語」 / 「主人公」 / 「世界観」 を簡潔に)
  status        - "ongoing" | "completed" | "hiatus"
  anime_adapted - true | false (= TVアニメ / 劇場版アニメ 1 つでも作られたら true)
  awards        - 主要受賞歴の array of string、 不明 / 無ければ []

【ルール】
- 知らない作品 (= 与えられた title から 内容判別不能) の場合、 すべての fields を null / 空 にして返す:
    {"slug": null, "magazine": null, "demographic": null, "genres": [], "synopsis": "", "status": null, "anime_adapted": false, "awards": []}
- 確信が無い field は推測せず null / "" / [] に。 幻覚厳禁。
- year_ended ≥ 2025 の作品で、 完結確定情報を知らない場合は status="ongoing" に。
- adult / 成人向け作品は普通に補完して良い (= 表示は別 filter で制御)。
- genres は **作品の本質を 3-8 個** で表現。 長編メジャー作品ほど多角的タグを (= action+adventure+fantasy+drama 等)、 短編 / 1-shot は 1-3 個に。 26 keys から無理に水増しせず、 該当しないなら少なくて OK。
- 出力は JSON のみ、 前置き / コードブロック / 解説 一切なし。`;

const VALID_GENRE_ARRAY = [
  "action", "adventure", "fantasy", "sci-fi", "mystery", "horror",
  "gag", "comedy", "romcom", "romance", "drama", "slice-of-life",
  "school", "sports", "historical", "samurai", "mecha", "yokai",
  "gourmet", "4-koma", "essay", "isekai", "bl", "suspense", "music",
];

function buildUserPrompt(ctx: SeriesContext, magazineKeys: Set<string>): string {
  const yearRange = ctx.yearStarted
    ? `${ctx.yearStarted}${ctx.yearEnded ? `-${ctx.yearEnded}` : "-現在"}`
    : "不明";
  return `【作品】 「${ctx.baseTitle}」
著者: ${ctx.authorName}${ctx.qid ? ` (Wikidata: ${ctx.qid})` : ""}
出版社: ${ctx.publisher ?? "不明"}
レーベル: ${ctx.imprint ?? "不明"}
発刊年: ${yearRange}
巻数: ${ctx.volumeCount}
収録タイトルサンプル: ${ctx.sampleTitles.slice(0, 3).join(" / ")}

【genres 候補 (= 1-4 個 選択)】
${VALID_GENRE_ARRAY.join(" / ")}

【magazine 候補 (= 1 個 選択 or null)】
${[...magazineKeys].slice(0, 50).join(" / ")} ... (= ${magazineKeys.size} 個から選択。 不明 / 不在は null)

JSON のみ返してください。`;
}

function sanitizeEntry(
  raw: unknown,
  ctx: SeriesContext,
  magazineKeys: Set<string>,
): Seed3Entry | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;

  // genres: filter to valid keys only、 上限 8 個
  const rawGenres = Array.isArray(r.genres) ? r.genres : [];
  const genres = rawGenres
    .filter((g): g is string => typeof g === "string" && VALID_GENRES.has(g))
    .slice(0, 8);

  // magazine: must be in master keys, null otherwise
  const rawMag = r.magazine;
  const magazine =
    typeof rawMag === "string" && magazineKeys.has(rawMag) ? rawMag : null;

  // demographic
  const rawDem = r.demographic;
  const demographic =
    typeof rawDem === "string" && VALID_DEMOGRAPHICS.has(rawDem)
      ? (rawDem as "shounen" | "shoujo" | "seinen" | "josei" | "kodomo" | "other")
      : undefined;

  // status
  const rawSt = r.status;
  const status =
    rawSt === "ongoing" || rawSt === "completed" || rawSt === "hiatus"
      ? rawSt
      : undefined;

  // slug
  const rawSlug = r.slug;
  const slug =
    typeof rawSlug === "string" && /^[a-z0-9-]+$/.test(rawSlug) && rawSlug.length >= 3
      ? rawSlug
      : undefined;

  // synopsis
  const synopsis = typeof r.synopsis === "string" ? r.synopsis : "";

  // anime_adapted
  const anime_adapted = typeof r.anime_adapted === "boolean" ? r.anime_adapted : undefined;

  // awards
  const awards =
    Array.isArray(r.awards)
      ? r.awards.filter((a): a is string => typeof a === "string").slice(0, 10)
      : undefined;

  // 空 entry (= AI 「知らない」 表明) は skip
  const isEmpty =
    !slug && !magazine && !demographic && genres.length === 0 && !synopsis && !status;
  if (isEmpty) return null;

  const entry: Seed3Entry = {
    key: seed3Key(ctx.qid, ctx.baseTitle),
    ...(slug ? { slug } : {}),
    ...(magazine !== null ? { magazine } : { magazine: null }),
    ...(demographic ? { demographic } : {}),
    ...(genres.length > 0 ? { genres } : {}),
    ...(synopsis ? { synopsis } : {}),
    ...(status ? { status } : {}),
    ...(anime_adapted !== undefined ? { anime_adapted } : {}),
    ...(awards && awards.length > 0 ? { awards } : {}),
  };
  return Seed3EntrySchema.parse(entry);
}

async function callAi(
  client: Anthropic,
  ctx: SeriesContext,
  magazineKeys: Set<string>,
): Promise<Seed3Entry | null> {
  const userPrompt = buildUserPrompt(ctx, magazineKeys);
  let attempt = 0;
  const maxAttempts = 4;
  while (attempt < maxAttempts) {
    try {
      const res = await client.messages.create({
        model: DEFAULT_MODEL,
        max_tokens: 800,
        temperature: 0.3,
        system: SYSTEM_PROMPT,
        messages: [{ role: "user", content: userPrompt }],
      });
      const txt = res.content
        .filter((b) => b.type === "text")
        .map((b) => (b as { type: "text"; text: string }).text)
        .join("");
      // try to extract JSON if AI wrapped in code block or prose
      const jsonStart = txt.indexOf("{");
      const jsonEnd = txt.lastIndexOf("}");
      if (jsonStart < 0 || jsonEnd < 0) {
        console.warn(`[seed3] non-JSON output for ${ctx.baseTitle}: ${txt.slice(0, 100)}`);
        return null;
      }
      const json = JSON.parse(txt.slice(jsonStart, jsonEnd + 1));
      return sanitizeEntry(json, ctx, magazineKeys);
    } catch (err: any) {
      attempt++;
      const msg = err?.message ?? String(err);
      if (msg.includes("429") || msg.includes("rate") || msg.includes("overloaded")) {
        const delay = 2000 * attempt;
        console.warn(`[seed3] rate-limited on ${ctx.baseTitle}, retry ${attempt}/${maxAttempts} after ${delay}ms`);
        await new Promise((r) => setTimeout(r, delay));
      } else {
        console.warn(`[seed3] error for ${ctx.baseTitle} (attempt ${attempt}/${maxAttempts}): ${msg.slice(0, 200)}`);
        if (attempt >= maxAttempts) return null;
        await new Promise((r) => setTimeout(r, 1000 * attempt));
      }
    }
  }
  return null;
}

async function processWithConcurrency<T, R>(
  items: T[],
  concurrency: number,
  fn: (item: T, idx: number) => Promise<R>,
): Promise<R[]> {
  const results: R[] = new Array(items.length);
  let next = 0;
  const workers = Array.from({ length: concurrency }, async () => {
    while (true) {
      const i = next++;
      if (i >= items.length) return;
      results[i] = await fn(items[i], i);
    }
  });
  await Promise.all(workers);
  return results;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!args.dryRun && !apiKey) {
    console.error("ANTHROPIC_API_KEY が未設定。 .env.local に置くか --dry-run で実行してください。");
    process.exit(1);
  }
  const client = new Anthropic({ apiKey });
  const db = openDb();
  const magazineKeys = loadValidMagazineKeys();
  console.log(`[seed3] ${magazineKeys.size} valid magazine keys loaded`);

  // 既存 entries (= diff mode 用)
  const existing = loadSeed3(args.outPath);
  console.log(`[seed3] ${existing.size} existing entries in ${args.outPath}`);

  // series 抽出
  let where = "";
  const params: any[] = [];
  if (args.seedFile) {
    const qids = loadSeedQids(args.seedFile);
    const ph = Array.from(qids, () => "?").join(",");
    where = `WHERE s.id IN (
      SELECT DISTINCT sa.series_id FROM series_authors sa
      JOIN mangaka m ON m.id = sa.mangaka_id
      WHERE m.qid IN (${ph})
    )`;
    params.push(...qids);
  }
  const seriesRows = db.prepare(`
    SELECT s.id, s.qid, s.title, s.title_kana,
           s.year_started, s.year_ended,
           s.publisher_key
    FROM series s
    ${where}
    ORDER BY s.id
  `).all(...params) as any[];

  const authorStmt = db.prepare(`
    SELECT m.qid, m.name FROM series_authors sa
    JOIN mangaka m ON m.id = sa.mangaka_id
    WHERE sa.series_id = ?
    ORDER BY CASE sa.role
      WHEN 'writer_artist' THEN 0 WHEN 'writer' THEN 1
      WHEN 'artist' THEN 2 WHEN 'original_author' THEN 3 ELSE 4
    END, m.id LIMIT 1
  `);
  const editionStmt = db.prepare(`
    SELECT e.imprint,
           (SELECT COUNT(*) FROM volumes v WHERE v.edition_id = e.id) AS vol_count
    FROM editions e WHERE e.series_id = ?
    ORDER BY CASE e.type
      WHEN 'standard' THEN 0 WHEN 'kanzenban' THEN 1
      WHEN 'shinsoban' THEN 2 WHEN 'aizoban' THEN 3
      WHEN 'wideban' THEN 4 WHEN 'bunkobon' THEN 5
      WHEN 'renewal' THEN 6 WHEN 'anime' THEN 7
      WHEN 'other' THEN 8 ELSE 99
    END LIMIT 1
  `);
  const sampleVolStmt = db.prepare(`
    SELECT json_extract(src.raw_json, '$.title') AS title
    FROM volumes v
    JOIN editions e ON e.id = v.edition_id
    JOIN sources src ON src.source_name = 'madb'
                     AND src.ref_table = 'volumes'
                     AND src.ref_id = v.isbn13
    WHERE e.series_id = ? AND v.is_extra = 0
    LIMIT 3
  `);

  // SeriesContext 構築 + 種3 key で diff filter
  const contexts: SeriesContext[] = [];
  for (const row of seriesRows) {
    const author = authorStmt.get(row.id) as { qid: string; name: string } | undefined;
    const edition = editionStmt.get(row.id) as
      | { imprint: string | null; vol_count: number }
      | undefined;
    if (!author) continue;
    const baseTitle = toBaseTitle(row.title);
    const key = seed3Key(row.qid ?? author.qid, baseTitle);
    if (args.diffMode && existing.has(key)) continue;
    const sampleVols = sampleVolStmt.all(row.id) as { title: string }[];
    contexts.push({
      qid: row.qid ?? author.qid,
      baseTitle,
      title: row.title,
      authorName: author.name,
      publisher: row.publisher_key,
      imprint: edition?.imprint ?? null,
      yearStarted: row.year_started,
      yearEnded: row.year_ended,
      volumeCount: edition?.vol_count ?? 0,
      sampleTitles: sampleVols.map((s) => s.title).filter(Boolean),
    });
  }

  // slugs filter (= force re-gen)
  let target = contexts;
  if (args.slugs.length > 0) {
    const slugSet = new Set(args.slugs);
    target = contexts.filter((c) => slugSet.has(c.baseTitle) || slugSet.has(c.qid ?? ""));
  }
  if (args.limit) target = target.slice(0, args.limit);

  console.log(`[seed3] target series: ${target.length} (= ${contexts.length} candidates, filtered)`);
  if (args.dryRun) {
    console.log(`[seed3] --dry-run: 最初 3 件のプロンプト sample`);
    for (const ctx of target.slice(0, 3)) {
      console.log("---");
      console.log(buildUserPrompt(ctx, magazineKeys));
    }
    console.log(`\n[seed3] dry-run end. 全 ${target.length} 件処理予定 (≈ ${Math.ceil(target.length * 700 / 1000000 * 1)} 円相当 @ Haiku 4.5)`);
    return;
  }

  // 並列実行
  const startTs = Date.now();
  let okCount = 0;
  let nullCount = 0;
  const results = await processWithConcurrency(target, args.concurrency, async (ctx, i) => {
    if (i % 25 === 0) {
      console.log(`[seed3] ... ${i}/${target.length} processed`);
    }
    const entry = await callAi(client, ctx, magazineKeys);
    if (entry) okCount++;
    else nullCount++;
    return entry;
  });
  const elapsedSec = Math.round((Date.now() - startTs) / 1000);

  // existing と merge
  const merged = new Map<string, Seed3Entry>(existing);
  for (const entry of results) {
    if (entry) merged.set(entry.key, entry);
  }

  const file: Seed3File = {
    schema_version: 1,
    generated_at: new Date().toISOString(),
    generator: DEFAULT_MODEL,
    series: [...merged.values()].sort((a, b) => a.key.localeCompare(b.key)),
  };
  writeSeed3(file, args.outPath);

  console.log(`\n=== seed3 build summary ===`);
  console.log(`  target          : ${target.length}`);
  console.log(`  ok (= filled)   : ${okCount}`);
  console.log(`  null (= 不明)    : ${nullCount}`);
  console.log(`  total in file   : ${merged.size}`);
  console.log(`  elapsed         : ${elapsedSec}s`);
  console.log(`  output          : ${args.outPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

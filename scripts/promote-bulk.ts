/**
 * SQLite に投入済みの全シリーズを一括で `data/manga/_drafts/<slug>.yml` に
 * 草稿として書き出す（Level A bulk promote）。各 YAML は MangaSchema 構造に
 * 適合させた上で Zod 検証を通すが、master 検証 (publisher/magazine/genre keys
 * の存在チェック) は loadData 側で行うため、ここでは shape のみ確認する。
 *
 * 出力先は data/manga/_drafts/ (gitignored)。loadData は data/manga/*.yml の
 * トップレベル `.yml` ファイルしか拾わないため、_drafts に何件あっても build
 * は壊れない。レビュー後に手動で _drafts → data/manga/ に昇格させる前提。
 *
 *   npm run promote:bulk                      # 全件
 *   npm run promote:bulk -- --limit 100       # 100 件で打ち止め
 *   npm run promote:bulk -- --min-volumes 3   # 3 巻以上のシリーズのみ
 *   npm run promote:bulk -- --include-adult   # adult_score >= 3 も draft 化
 *   npm run promote:bulk -- --dry-run         # 書かずにサマリだけ
 *   npm run promote:bulk -- --force           # 既存 draft を上書き
 *
 * 既知の placeholder（必ず人手レビューで埋める）:
 *   - publisher: imprint 文字列が data/publishers.yml の name と一致した場合
 *     のみ key を埋める。それ以外は "TODO_publisher"。
 *   - magazine: 常に null（NDL からは取れない、Wikipedia 連携が Level B）
 *   - demographic: 常に "shounen"（誤りの確率が高い）
 *   - genres: 常に ["TODO_genre"]（loadData が即落とすので _drafts の中だけ）
 *   - synopsis: 常に ""（Wikipedia 連携が Level B）
 */
import "./_env";
import fs from "node:fs";
import path from "node:path";
import YAML from "yaml";
import { openDb, tx, type DB } from "./_db";
import { MangaSchema } from "../lib/schema";
import {
  EDITION_LABELS,
  slugFromTitle,
  type EditionType,
} from "../lib/edition";
import { computeAdultScore } from "../lib/adult-score";
import { readKanaFromTitle } from "../lib/kana";

type Args = {
  outDir: string;
  limit: number | null;
  minVolumes: number;
  includeAdult: boolean;
  dryRun: boolean;
  force: boolean;
};

function parseArgs(argv: string[]): Args {
  const out: Args = {
    outDir: path.join("data", "manga", "_drafts"),
    limit: null,
    minVolumes: 1,
    includeAdult: false,
    dryRun: false,
    force: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = argv[i + 1];
    if (a === "--out-dir" && next) {
      out.outDir = next;
      i++;
    } else if (a === "--limit" && next) {
      out.limit = Number(next);
      i++;
    } else if (a === "--min-volumes" && next) {
      out.minVolumes = Number(next);
      i++;
    } else if (a === "--include-adult") {
      out.includeAdult = true;
    } else if (a === "--dry-run") {
      out.dryRun = true;
    } else if (a === "--force") {
      out.force = true;
    }
  }
  return out;
}

/**
 * data/publishers.yml を読んで「imprint 文字列 → publisher key」の reverse map
 * を作る。NDL の dcterms:publisher は「小学館」「集英社」のような出版社名で
 * 入ることが多く、それを我々のキーに対応付ける。完全一致と「imprint が key
 * の name を含む」両方をフォールバックでサポート。
 */
function loadPublisherMap(): Map<string, string> {
  const p = path.join(process.cwd(), "data", "publishers.yml");
  const text = fs.readFileSync(p, "utf8");
  const yaml = YAML.parse(text) as Record<string, { name: string }>;
  const m = new Map<string, string>();
  for (const [key, val] of Object.entries(yaml)) {
    if (val?.name) m.set(val.name.normalize("NFKC"), key);
  }
  return m;
}

function resolvePublisherKey(
  imprintCandidates: string[],
  pubMap: Map<string, string>,
): string {
  for (const im of imprintCandidates) {
    if (!im) continue;
    const norm = im.normalize("NFKC");
    if (pubMap.has(norm)) return pubMap.get(norm)!;
    // substring match: "小学館コミックス" → shogakukan, etc.
    for (const [name, key] of pubMap) {
      if (norm.includes(name)) return key;
    }
  }
  return "TODO_publisher";
}

/** Fix C: adult_publishers を SQLite から読んで Set を返す */
function loadAdultPublisherSet(db: DB): Set<string> {
  const rows = db
    .prepare("SELECT name FROM adult_publishers")
    .all() as { name: string }[];
  return new Set(rows.map((r) => r.name));
}

/** Fix C: adult_mangaka_known を SQLite から読んで Set を返す (normalize 済み) */
function loadAdultMangakaSet(db: DB): Set<string> {
  const rows = db
    .prepare("SELECT name FROM adult_mangaka_known")
    .all() as { name: string }[];
  return new Set(rows.map((r) => r.name));
}

/** Tier 2: adult_imprints を SQLite から読んで Set を返す (NFKC 正規化済 imprint 名) */
function loadAdultImprintSet(db: DB): Set<string> {
  const rows = db
    .prepare("SELECT imprint FROM adult_imprints")
    .all() as { imprint: string }[];
  return new Set(rows.map((r) => r.imprint));
}

type SeriesRow = {
  id: number;
  series_key: string;
  qid: string | null;
  title: string;
  title_kana: string | null;
  year_started: number | null;
  year_ended: number | null;
  // B-1: Wikipedia 連携で埋まる列。NULL ならまだ未取得 or 未ヒット。
  publisher_key: string | null;
  magazine_key: string | null;
  demographic: string | null;
  genres: string | null;     // CSV
  synopsis: string | null;
  status: string | null;
  wikipedia_url: string | null;
};

type EditionRow = {
  id: number;
  type: string;
  label: string;
  imprint: string | null;
  year_started: number | null;
  year_ended: number | null;
};

type VolumeRow = {
  number: number;
  isbn13: string;
  release_date: string | null;
  cover_url: string | null;
  asin: string | null;
};

function buildEditionsForSeries(db: DB, seriesId: number) {
  const editions = db
    .prepare(
      `SELECT id, type, label, imprint, year_started, year_ended
       FROM editions
       WHERE series_id = ?
       ORDER BY COALESCE(year_started, 9999), type`,
    )
    .all(seriesId) as EditionRow[];

  const result = editions.map((e) => {
    const vols = db
      .prepare(
        `SELECT number, isbn13, release_date, cover_url, asin
         FROM volumes
         WHERE edition_id = ? AND is_extra = 0 AND number >= 1
         ORDER BY number, isbn13`,
      )
      .all(e.id) as VolumeRow[];

    // 同一 (edition, number) の ISBN 重複は最初の 1 件採用
    const seen = new Set<number>();
    const uniqueVols = vols.filter((v) => {
      if (seen.has(v.number)) return false;
      seen.add(v.number);
      return true;
    });

    return {
      type: e.type as EditionType,
      label: e.label,
      ...(e.imprint ? { imprint: e.imprint } : {}),
      ...(e.year_started !== null ? { year_started: e.year_started } : {}),
      ...(e.year_ended !== null ? { year_ended: e.year_ended } : {}),
      volumes: uniqueVols.map((v) => ({
        number: v.number,
        asin: v.asin,
        isbn13: v.isbn13,
        cover_url: v.cover_url,
        release_date: v.release_date,
      })),
    };
  });

  return result.filter((e) => e.volumes.length > 0);
}

/**
 * シリーズの base slug を決める（衝突 suffix 抜き）。優先順:
 *   1. NDL 由来の title_kana (dcndl:titleTranscription) → toRomaji
 *   2. kuromoji で漢字→カナ変換した結果 → toRomaji（kanji 残存なら無効）
 *   3. title をそのまま処理した結果（Latin/かなのみ向け、3 文字未満は無効）
 *   4. `series-<id>` フォールバック
 *
 * Step 1 と Step 2 は「kana ヒント明示」で slugFromTitle を呼び、内部の
 * 「kana が空なら title 直接」フォールバックを発火させない。これで
 * "半妖の夜叉姫" のようにかな部分だけ拾って "no" 等の断片 slug ができるのを
 * 防ぐ。Step 3 は明示的に title-only にして、結果が短すぎれば series-N へ。
 *
 * 短さ閾値は 3 字。"ai"（藍）"go"（碁）のような単語タイトルも極稀にあるが、
 * 量産 draft 段階では「短すぎる slug」は人手レビューで series-N から正名へ
 * 上書きしてもらう方針が安全。
 */
const SLUG_MIN_LENGTH = 3;

async function deriveBaseSlug(series: SeriesRow): Promise<string> {
  // Step 1: NDL 由来 kana（kana が無ければスキップ）
  if (series.title_kana && series.title_kana.trim()) {
    const s = slugFromTitle(series.title, { kana: series.title_kana });
    if (s) return s;
  }

  // Step 2: kuromoji 形態素解析。kanji が混じったまま残っていたら信頼性低 →
  // 採用せずに次の段へ（たとえば「半妖」が辞書に無くて未変換のままのケース）
  const morph = await readKanaFromTitle(series.title);
  const morphHasKanji = /[㐀-鿿]/.test(morph);
  if (morph && morph !== series.title && !morphHasKanji) {
    const s = slugFromTitle(series.title, { kana: morph });
    if (s) return s;
  }

  // Step 3: タイトル直接（Latin/かなのみが拾える）。短すぎる場合は不採用。
  const direct = slugFromTitle(series.title);
  if (direct && direct.length >= SLUG_MIN_LENGTH) return direct;

  // Step 4: series-id フォールバック
  return `series-${series.id}`;
}

function applyCollisionSuffix(base: string, taken: Set<string>): string {
  if (!taken.has(base)) {
    taken.add(base);
    return base;
  }
  let suffix = 2;
  while (taken.has(`${base}-${suffix}`)) suffix++;
  const out = `${base}-${suffix}`;
  taken.add(out);
  return out;
}

function existingSlugs(): Set<string> {
  const s = new Set<string>();
  const dirs = [
    path.join("data", "manga"),
    path.join("data", "manga", "_drafts"),
  ];
  for (const d of dirs) {
    if (!fs.existsSync(d)) continue;
    for (const f of fs.readdirSync(d)) {
      if (f.endsWith(".yml")) s.add(f.slice(0, -4));
      else if (f.endsWith(".yaml")) s.add(f.slice(0, -5));
    }
  }
  return s;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const db = openDb();
  const pubMap = loadPublisherMap();
  fs.mkdirSync(args.outDir, { recursive: true });

  // 1 シリーズに 1 行ずつ。primary author は writer_artist > writer >
  // artist > original_author の優先順、最初の 1 名を採用する。
  const seriesRows = db
    .prepare(
      `SELECT s.id, s.series_key, s.qid, s.title, s.title_kana,
              s.year_started, s.year_ended, s.status,
              s.publisher_key, s.magazine_key, s.demographic,
              s.genres, s.synopsis, s.wikipedia_url
       FROM series s
       ORDER BY s.id`,
    )
    .all() as SeriesRow[];

  const authorStmt = db.prepare(
    `SELECT m.id AS mid, m.qid, m.name, m.has_adult_credit, sa.role
     FROM series_authors sa
     JOIN mangaka m ON m.id = sa.mangaka_id
     WHERE sa.series_id = ?
     ORDER BY
       CASE sa.role
         WHEN 'writer_artist'    THEN 0
         WHEN 'writer'           THEN 1
         WHEN 'artist'           THEN 2
         WHEN 'original_author'  THEN 3
         ELSE 4
       END,
       m.id
     LIMIT 1`,
  );

  const taken = existingSlugs();

  // Fix C: 既知の adult publishers / mangaka をメモリにキャッシュ。
  // テーブルが空なら空 Set を返す（fetch:adult-lists 未実行でも壊れない）。
  // Tier 2: adult_imprints も同様。 seed:adult-imprints 未実行でも壊れない。
  const knownAdultPublishers = loadAdultPublisherSet(db);
  const knownAdultMangaka = loadAdultMangakaSet(db);
  const knownAdultImprints = loadAdultImprintSet(db);
  console.log(
    `[adult] known publishers: ${knownAdultPublishers.size}, known mangaka: ${knownAdultMangaka.size}, known imprints: ${knownAdultImprints.size}`,
  );

  const updateScore = db.prepare(
    `UPDATE series SET adult_score = ? WHERE id = ?`,
  );
  const insertSignal = db.prepare(
    `INSERT OR REPLACE INTO adult_signals (series_id, signal, weight, evidence)
     VALUES (?, ?, ?, ?)`,
  );

  const stats = {
    total: seriesRows.length,
    written: 0,
    skippedAdult: 0,
    skippedFew: 0,
    skippedNoAuthor: 0,
    skippedExisting: 0,
    skippedInvalid: 0,
  };

  for (const row of seriesRows) {
    if (args.limit !== null && stats.written >= args.limit) break;

    const author = authorStmt.get(row.id) as
      | {
          mid: number;
          qid: string;
          name: string;
          has_adult_credit: number;
          role: string;
        }
      | undefined;
    if (!author) {
      stats.skippedNoAuthor++;
      continue;
    }

    // editions を先に取り出して imprint を集める (adult score にも、後段の YAML
    // 構築にも使う)。
    const editions = buildEditionsForSeries(db, row.id);

    // adult-score 計算用の imprint は editions テーブルから直接拾う。
    // buildEditionsForSeries は「volumes が 0 件の edition を捨てる」フィルタを
    // 持っているので、adult imprint を持つ edition の volumes が全部 is_extra=1
    // / number<1 だった場合にその imprint を見落とす。adult 判定は
    // 「draft を出すかどうか」より広いカバレッジで判断する必要があるので、
    // 全 imprint を adult 判定にだけ与える。
    const imprintsForAdultScore = (
      db
        .prepare(
          `SELECT DISTINCT imprint FROM editions
           WHERE series_id = ? AND imprint IS NOT NULL AND imprint != ''`,
        )
        .all(row.id) as { imprint: string }[]
    ).map((r) => r.imprint);

    // YAML への publisher 解決には buildEditions 後の (= volumes ありの) imprint を使う
    const imprintCandidatesPre = editions
      .map((e) => (e as { imprint?: string }).imprint ?? "")
      .filter(Boolean);

    // Fix C: 多層 adult score を計算 → series.adult_score と adult_signals に書き込み
    const { score: adultScore, signals: adultSignals } = computeAdultScore({
      hasWikidataCredit: author.has_adult_credit === 1,
      authorName: author.name,
      imprints: imprintsForAdultScore,
      knownAdultMangaka,
      knownAdultPublishers,
      knownAdultImprints,
    });
    if (adultScore > 0) {
      tx(db, () => {
        updateScore.run(adultScore, row.id);
        for (const sig of adultSignals) {
          insertSignal.run(row.id, sig.signal, sig.weight, sig.evidence);
        }
      });
    }

    if (adultScore >= 3 && !args.includeAdult) {
      stats.skippedAdult++;
      continue;
    }

    // editions は adult-score 計算時に取得済み（imprintCandidatesPre と同じ）
    const totalVols = editions.reduce((sum, e) => sum + e.volumes.length, 0);
    if (totalVols < args.minVolumes) {
      stats.skippedFew++;
      continue;
    }

    // base slug は kana/title 由来。衝突回避の "-2" suffix は別途付ける
    // ことで title_romaji にゴミ ("inuyasha 2" など) が混入するのを防ぐ。
    const baseSlug = await deriveBaseSlug(row);
    const slug = applyCollisionSuffix(baseSlug, taken);
    const outPath = path.join(args.outDir, `${slug}.yml`);
    if (!args.force && fs.existsSync(outPath)) {
      stats.skippedExisting++;
      continue;
    }

    // B-1: Wikipedia から publisher_key が取れていれば最優先で採用、無ければ
    // imprint 文字列 → publishers.yml の name 逆引き、最後に "TODO_publisher"。
    const publisherKey =
      row.publisher_key ?? resolvePublisherKey(imprintCandidatesPre, pubMap);

    // year_started / year_ended は standard 優先 → 無ければ最古
    const standardEdition =
      editions.find((e) => e.type === "standard") ?? editions[0];
    const yearStarted =
      (standardEdition && "year_started" in standardEdition
        ? (standardEdition as { year_started?: number }).year_started
        : null) ??
      row.year_started ??
      null;
    const yearEnded =
      (standardEdition && "year_ended" in standardEdition
        ? (standardEdition as { year_ended?: number }).year_ended
        : null) ??
      row.year_ended ??
      null;

    // title_romaji は base slug（衝突 suffix を含まない）の `-` を空白に戻したもの。
    // collision suffix を含む slug を使うと "inuyasha 2" のように巻数表記に見えてしまう。
    const titleRomaji = baseSlug.replace(/-/g, " ");

    // B-1: Wikipedia 由来データがあれば優先採用。無ければ placeholder。
    const wikiGenres = row.genres
      ? row.genres
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean)
      : [];
    const genres = wikiGenres.length > 0 ? wikiGenres : ["TODO_genre"];
    const demographic = row.demographic ?? "shounen";
    const synopsis = row.synopsis ?? "";

    const manga = {
      slug,
      title: row.title,
      title_kana: row.title_kana ?? "TODO_kana",
      title_romaji: titleRomaji || "TODO_romaji",
      year_started: yearStarted ?? 2000,
      year_ended: yearEnded ?? null,
      status:
        (row.status as "ongoing" | "completed" | "hiatus" | null) ??
        (yearEnded ? ("completed" as const) : ("ongoing" as const)),
      authors: [{ name: author.name, role: "writer_artist" as const }],
      original_authors: [],
      publisher: publisherKey,
      magazine: row.magazine_key ?? null,
      demographic,
      genres,
      synopsis,
      ...(row.wikipedia_url ? { wikipedia_url: row.wikipedia_url } : {}),
      editions,
    };

    const result = MangaSchema.safeParse(manga);
    if (!result.success) {
      stats.skippedInvalid++;
      const issues = result.error.issues.slice(0, 3).map((i) =>
        `${i.path.join(".")}: ${i.message}`,
      );
      console.warn(
        `  [skip-invalid] #${row.id} ${row.title} → ${issues.join("; ")}`,
      );
      continue;
    }

    if (!args.dryRun) {
      const yamlText =
        `# Bulk-promoted draft from NDL pipeline by scripts/promote-bulk.ts\n` +
        `# Source mangaka: ${author.name} (${author.qid}); Source series: #${row.id}\n` +
        `# REVIEW REQUIRED: publisher (TODO_), magazine, demographic, genres, synopsis\n` +
        YAML.stringify(result.data);
      fs.writeFileSync(outPath, yamlText, "utf8");
    }
    stats.written++;
    if (stats.written % 100 === 0) {
      console.log(`  ... ${stats.written} drafts written`);
    }
  }

  console.log("\n=== promote-bulk summary ===");
  console.log(`  total series        : ${stats.total}`);
  console.log(`  drafts written      : ${stats.written}`);
  console.log(`  skipped (adult≥3)   : ${stats.skippedAdult}`);
  console.log(`  skipped (no author) : ${stats.skippedNoAuthor}`);
  console.log(
    `  skipped (vols < ${args.minVolumes})  : ${stats.skippedFew}`,
  );
  console.log(`  skipped (existing)  : ${stats.skippedExisting}`);
  console.log(`  skipped (invalid)   : ${stats.skippedInvalid}`);
  console.log(`  output dir          : ${args.outDir}`);
  if (args.dryRun) console.log(`  (dry-run: no files were actually written)`);

  db.close();
}

main().catch((err) => {
  console.error("[fatal]", err);
  process.exit(1);
});

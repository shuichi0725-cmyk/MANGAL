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
 * データソース対応:
 *   この script は series / editions / volumes テーブルのみを読むので、
 *   投入元 (= NDL / MADB / 両方) を問わず動作する。 schema v7 (= 3-state model)
 *   導入後は series テーブル自体が live state のみを保持するため、
 *   excluded / deleted な series は自然に対象外となる (= filter 不要)。
 *
 *   2026-05-08 以降、 主データソースは MADB JSON-LD に切り替わっている。
 *   MADB 由来データ + fetch:wikipedia 補完で以下が series テーブルへ直接入る:
 *     publisher_key  (MADB → splitMadbLiteral → publishers.yml master 解決、 ~78%)
 *     magazine_key   (Wikipedia infobox)
 *     title_kana     (Wikipedia / openBD)
 *     demographic / genres / synopsis (Wikipedia)
 *
 * 既知の placeholder（必ず人手レビューで埋める）:
 *   - publisher: 多くは MADB / Wikipedia で解決済。 残った imprint 文字列が
 *     publishers.yml と一致しない場合のみ "TODO_publisher"。
 *   - magazine:    fetch:wikipedia layer C 解決率次第。 NULL は許容。
 *   - demographic: Wikipedia 由来なら正しい値、 無ければ "shounen" 既定 (= 誤確率高)。
 *   - genres:     Wikipedia 由来なら正しい配列、 無ければ ["TODO_genre"] (= loadData が落とす)。
 *   - synopsis:   Wikipedia 由来なら抜粋、 無ければ ""。
 */
import "./_env";
import fs from "node:fs";
import path from "node:path";
import YAML from "yaml";
import { openDb, tx, type DB } from "./_db";
import { MangaSchema } from "../lib/schema";
import {
  EDITION_LABELS,
  EDITION_PRIORITY,
  classifyEditionFromImprint,
  slugFromTitle,
  type EditionType,
} from "../lib/edition";
import { computeAdultScore } from "../lib/adult-score";
import { readKanaFromTitle } from "../lib/kana";
import { loadSeed3, seed3Key, type Seed3Entry } from "../lib/seed3";

type Args = {
  outDir: string;
  limit: number | null;
  minVolumes: number;
  includeAdult: boolean;
  dryRun: boolean;
  force: boolean;
  /**
   * Wikidata QID list で series を絞り込むための seed file。 1 行 1 qid
   * (= "Q1993" 形式)、 # 始まりはコメント、 空行無視。 TSV/CSV の場合は
   * **行内に最初に出現する Q\d+ token** を qid として採用する (= 既存
   * `data/seed/verification-20.tsv` のような複数列フォーマットも accept)。
   */
  seedFile: string | null;
};

function parseArgs(argv: string[]): Args {
  const out: Args = {
    outDir: path.join("data", "manga", "_drafts"),
    limit: null,
    minVolumes: 1,
    includeAdult: false,
    dryRun: false,
    force: false,
    seedFile: null,
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
    } else if (a === "--seed-file" && next) {
      out.seedFile = next;
      i++;
    }
  }
  return out;
}

/**
 * seed file (= line-separated qid list) を読み込む。 各行から最初の Q\d+
 * token を抽出。 # コメント / 空行 / header 行 を無視。 重複 qid は dedup。
 *
 * accept する format 例:
 *   Q1993                           ← 単純な qid 列
 *   Q1993 諫山創 進撃の巨人          ← space 区切りの行
 *   美味しんぼ\t...\tQ11615162\t... ← TSV (= verification-20.tsv 形式)
 *   # コメント                        ← 無視
 */
function loadSeedQids(seedFile: string): Set<string> {
  const raw = fs.readFileSync(seedFile, "utf8");
  const out = new Set<string>();
  for (const line of raw.split(/\r?\n/)) {
    const t = line.trim();
    if (!t || t.startsWith("#")) continue;
    const m = t.match(/Q\d+/);
    if (m) out.add(m[0]);
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

type VolumeRow = {
  number: number;
  isbn13: string;
  release_date: string | null;
  cover_url: string | null;
  asin: string | null;
};

/**
 * vol number 列に欠番があれば返す (= 「巻が抜ける」 ユーザ最悪ケースの可視化)。
 *   detectVolumeGaps([1,2,3,5]) === [4]
 *   detectVolumeGaps([2,3])     === [1]   (= 1 が抜けてる扱い、 max まで埋める)
 *   detectVolumeGaps([1,2,3])   === []
 *
 * 補完は行わない (= MADB の欠番が原因で promote 側では補完不能)。 警告のみ。
 */
function detectVolumeGaps(numbers: number[]): number[] {
  if (numbers.length === 0) return [];
  const present = new Set(numbers);
  const max = Math.max(...numbers);
  const missing: number[] = [];
  for (let i = 1; i <= max; i++) if (!present.has(i)) missing.push(i);
  return missing;
}

type VolumeWithImprint = VolumeRow & {
  perRecImprint: string;
  derivedType: EditionType;
};

type BuiltEdition = {
  type: EditionType;
  label: string;
  imprint?: string;
  year_started?: number;
  year_ended?: number;
  volumes: {
    number: number;
    asin: string | null;
    isbn13: string;
    cover_url: string | null;
    release_date: string | null;
  }[];
};

function buildEditionsForSeries(
  db: DB,
  seriesId: number,
): {
  editions: BuiltEdition[];
  gaps: { editionType: string; missing: number[] }[];
} {
  // 5 軸改善: DB の editions テーブル (= fetch-madb 段で title 由来分類した結果) を
  // 信用せず、 全 volumes を sources.raw_json (= MADB per-record imprint) で
  // 再分類して virtual edition を組み直す。
  //
  // 動機: fetch-madb は title="うる星やつら" だけを見て classifyEdition() するため、
  // ワイド版/文庫/アニメ版/通常版が同じ standard edition に詰め込まれる。 DB の
  // edition.imprint は最後/最初に見た 1 値しか持たず実態と乖離する。 MADB raw の
  // imprint (= 単行本レーベル) こそ真値。
  const rows = db
    .prepare(
      `SELECT v.number, v.isbn13, v.release_date, v.cover_url, v.asin,
              e.imprint AS db_imprint,
              src.raw_json AS raw_madb
       FROM volumes v
       JOIN editions e ON v.edition_id = e.id
       LEFT JOIN sources src ON src.source_name = 'madb'
                             AND src.ref_table = 'volumes'
                             AND src.ref_id = v.isbn13
       WHERE e.series_id = ? AND v.is_extra = 0 AND v.number >= 1`,
    )
    .all(seriesId) as (VolumeRow & {
      db_imprint: string | null;
      raw_madb: string | null;
    })[];

  // 各 volume を per-record imprint で再分類
  const enriched: VolumeWithImprint[] = rows.map((r) => {
    let perRecImprint = r.db_imprint ?? "";
    if (r.raw_madb) {
      try {
        const raw = JSON.parse(r.raw_madb) as { imprint?: string };
        if (raw.imprint && typeof raw.imprint === "string") {
          perRecImprint = raw.imprint;
        }
      } catch {
        // raw_json が壊れていれば db_imprint fallback
      }
    }
    return {
      number: r.number,
      isbn13: r.isbn13,
      release_date: r.release_date,
      cover_url: r.cover_url,
      asin: r.asin,
      perRecImprint,
      derivedType: classifyEditionFromImprint(perRecImprint),
    };
  });

  // edition type で grouping
  const groups = new Map<EditionType, VolumeWithImprint[]>();
  for (const v of enriched) {
    const list = groups.get(v.derivedType);
    if (list) list.push(v);
    else groups.set(v.derivedType, [v]);
  }

  const built: BuiltEdition[] = [];
  const gaps: { editionType: string; missing: number[] }[] = [];

  for (const [type, list] of groups) {
    // group 内で最頻 imprint を採用 (= 表記揺れの中で代表 1 つを選ぶ)
    const impCount = new Map<string, number>();
    for (const v of list) {
      if (!v.perRecImprint) continue;
      impCount.set(v.perRecImprint, (impCount.get(v.perRecImprint) ?? 0) + 1);
    }
    const topImprint =
      [...impCount.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "";

    // sort: number → release_date 昇順 → ISBN tie-break
    const sorted = [...list].sort((a, b) => {
      if (a.number !== b.number) return a.number - b.number;
      const ad = a.release_date ?? "9999-99-99";
      const bd = b.release_date ?? "9999-99-99";
      if (ad !== bd) return ad < bd ? -1 : 1;
      const ac = a.cover_url == null ? 1 : 0;
      const bc = b.cover_url == null ? 1 : 0;
      if (ac !== bc) return ac - bc;
      return a.isbn13 < b.isbn13 ? -1 : 1;
    });

    // 同 number は先頭 1 件 (= release_date 最古) を primary に採用
    const seen = new Set<number>();
    const unique = sorted.filter((v) => {
      if (seen.has(v.number)) return false;
      seen.add(v.number);
      return true;
    });
    if (unique.length === 0) continue;

    // 軸 4: year_started/ended を primary set min/max で再計算 (= DB の
    // editions.year_started/ended は混入 ISBN を含むので信用しない)
    const years = unique
      .map((v) => v.release_date)
      .filter((d): d is string => Boolean(d))
      .map((d) => parseInt(d.slice(0, 4), 10))
      .filter((y) => !Number.isNaN(y) && y >= 1900 && y <= 2100);
    const yearStarted = years.length > 0 ? Math.min(...years) : null;
    const yearEnded = years.length > 0 ? Math.max(...years) : null;

    const numbers = unique.map((v) => v.number);
    const missing = detectVolumeGaps(numbers);
    if (missing.length > 0) gaps.push({ editionType: type, missing });

    built.push({
      type,
      label: EDITION_LABELS[type],
      ...(topImprint ? { imprint: topImprint } : {}),
      ...(yearStarted !== null ? { year_started: yearStarted } : {}),
      ...(yearEnded !== null ? { year_ended: yearEnded } : {}),
      volumes: unique.map((v) => ({
        number: v.number,
        asin: v.asin,
        isbn13: v.isbn13,
        cover_url: v.cover_url,
        release_date: v.release_date,
      })),
    });
  }

  // EDITION_PRIORITY 順で sort (= standard → kanzenban → … → anime → other)
  built.sort((a, b) => {
    const pa = EDITION_PRIORITY[a.type] ?? 99;
    const pb = EDITION_PRIORITY[b.type] ?? 99;
    if (pa !== pb) return pa - pb;
    return (a.year_started ?? 9999) - (b.year_started ?? 9999);
  });

  return {
    editions: built.filter((e) => e.volumes.length > 0),
    gaps,
  };
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
  // --seed-file 指定時は mangaka.qid IN (...) で series を絞り込む。
  let seriesRows: SeriesRow[];
  if (args.seedFile) {
    const qids = loadSeedQids(args.seedFile);
    if (qids.size === 0) {
      throw new Error(`seed file ${args.seedFile} contains no qids`);
    }
    const placeholders = Array.from(qids, () => "?").join(",");
    seriesRows = db
      .prepare(
        `SELECT s.id, s.series_key, s.qid, s.title, s.title_kana,
                s.year_started, s.year_ended, s.status,
                s.publisher_key, s.magazine_key, s.demographic,
                s.genres, s.synopsis, s.wikipedia_url
         FROM series s
         WHERE s.id IN (
           SELECT DISTINCT sa.series_id
           FROM series_authors sa
           JOIN mangaka m ON m.id = sa.mangaka_id
           WHERE m.qid IN (${placeholders})
         )
         ORDER BY s.id`,
      )
      .all(...qids) as SeriesRow[];
    console.log(
      `[seed-file] ${args.seedFile} → ${qids.size} qids → ${seriesRows.length} series matched`,
    );
  } else {
    seriesRows = db
      .prepare(
        `SELECT s.id, s.series_key, s.qid, s.title, s.title_kana,
                s.year_started, s.year_ended, s.status,
                s.publisher_key, s.magazine_key, s.demographic,
                s.genres, s.synopsis, s.wikipedia_url
         FROM series s
         ORDER BY s.id`,
      )
      .all() as SeriesRow[];
  }

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

  // Per-series provenance を sources テーブルから引いて header comment に
  // 「どのデータソース由来か」 を記録する (= レビュー時に NDL/MADB を区別したい)。
  const sourcesStmt = db.prepare(
    `SELECT DISTINCT source_name FROM sources
     WHERE ref_table = 'volumes' AND ref_id IN (
       SELECT v.isbn13 FROM volumes v JOIN editions e ON e.id = v.edition_id
       WHERE e.series_id = ?
     )
     ORDER BY source_name`,
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

  // 種3 (= series-supplement.yml) を読み込み。 magazine / demographic / genres /
  // synopsis / status / slug を AI 補完済 entry で 上書きする。 entry 不在 series
  // は従来通り Wikipedia row.* / placeholder fallback。
  const seed3 = loadSeed3();
  console.log(`[seed3] loaded ${seed3.size} entries from data/seeds/series-supplement.yml`);

  // データソース別の volumes 件数 (= MADB 主導か NDL 主導かを把握するため)。
  const sourcesSummary = db
    .prepare(
      `SELECT source_name, COUNT(*) AS n
       FROM sources
       WHERE ref_table = 'volumes'
       GROUP BY source_name
       ORDER BY n DESC`,
    )
    .all() as { source_name: string; n: number }[];
  console.log(
    `[sources] volumes by source: ${sourcesSummary.map((s) => `${s.source_name}=${s.n}`).join(", ")}`,
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
    /** detectVolumeGaps が non-empty を返した series 数 (= 巻番号に欠番がある) */
    seriesWithGaps: 0,
    /** 警告 sample (= 最初の N 件、 user の目視確認用) */
    gapSamples: [] as string[],
  };
  const GAP_SAMPLE_LIMIT = 8;

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
    // 構築にも使う)。 buildEditionsForSeries は EDITION_PRIORITY 順にソート済。
    const { editions, gaps: editionGaps } = buildEditionsForSeries(db, row.id);

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

    // 種3 entry の lookup (= qid + baseTitle 複合 key)。 series.title は
    // fetch-madb 段で既に baseTitle 化されているので そのまま key 構築可能。
    const s3 = seed3.get(seed3Key(row.qid ?? author.qid, row.title));

    // B-1: Wikipedia 由来データがあれば優先採用。無ければ placeholder。
    const wikiGenres = row.genres
      ? row.genres
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean)
      : [];
    // 優先順: 種3 (= AI 補完) > Wikipedia (= row.*) > placeholder
    const genres =
      s3?.genres && s3.genres.length > 0
        ? s3.genres
        : wikiGenres.length > 0
          ? wikiGenres
          : ["TODO_genre"];
    const demographic = s3?.demographic ?? row.demographic ?? "shounen";
    const synopsis = s3?.synopsis ?? row.synopsis ?? "";
    const magazine = s3?.magazine ?? row.magazine_key ?? null;
    // status: 種3 > DB row.status (= Wikipedia 由来) > year_ended-based default
    // ただし year_ended >= 2025 で 種3/row.status 両方無いなら ongoing 安全側に
    const recentEnd = yearEnded != null && yearEnded >= 2025;
    const status: "ongoing" | "completed" | "hiatus" =
      s3?.status ??
      (row.status as "ongoing" | "completed" | "hiatus" | null) ??
      (recentEnd ? "ongoing" : yearEnded ? "completed" : "ongoing");

    const manga = {
      slug,
      title: row.title,
      title_kana: row.title_kana ?? "TODO_kana",
      title_romaji: titleRomaji || "TODO_romaji",
      year_started: yearStarted ?? 2000,
      year_ended: yearEnded ?? null,
      status,
      authors: [{ name: author.name, role: "writer_artist" as const }],
      original_authors: [],
      publisher: publisherKey,
      magazine,
      demographic,
      genres,
      synopsis,
      ...(s3?.anime_adapted !== undefined ? { anime_adapted: s3.anime_adapted } : {}),
      ...(s3?.awards && s3.awards.length > 0 ? { awards: s3.awards } : {}),
      ...(s3?.alternative_titles ? { alternative_titles: s3.alternative_titles } : {}),
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
      const provenance = (sourcesStmt.all(row.id) as { source_name: string }[])
        .map((r) => r.source_name)
        .join(",") || "unknown";
      const todos: string[] = [];
      if (publisherKey === "TODO_publisher") todos.push("publisher");
      if (!row.magazine_key) todos.push("magazine");
      if (!row.demographic) todos.push("demographic");
      if (genres.includes("TODO_genre")) todos.push("genres");
      if (!row.synopsis) todos.push("synopsis");
      if (!row.title_kana) todos.push("title_kana");
      const reviewLine = todos.length > 0
        ? `# REVIEW REQUIRED: ${todos.join(", ")}\n`
        : `# (auto-promotable: no TODO placeholders)\n`;
      const yamlText =
        `# Bulk-promoted draft by scripts/promote-bulk.ts\n` +
        `# Sources: ${provenance}\n` +
        `# Source mangaka: ${author.name} (${author.qid}); Source series: #${row.id}\n` +
        reviewLine +
        YAML.stringify(result.data);
      fs.writeFileSync(outPath, yamlText, "utf8");
    }
    stats.written++;
    if (editionGaps.length > 0) {
      stats.seriesWithGaps++;
      if (stats.gapSamples.length < GAP_SAMPLE_LIMIT) {
        const detail = editionGaps
          .map(
            (g) =>
              `${g.editionType}=[${g.missing.slice(0, 8).join(",")}${g.missing.length > 8 ? ",..." : ""}]`,
          )
          .join(" ");
        stats.gapSamples.push(`#${row.id} ${row.title}: ${detail}`);
      }
    }
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
  console.log(`  series with vol gaps: ${stats.seriesWithGaps}`);
  console.log(`  output dir          : ${args.outDir}`);
  if (args.dryRun) console.log(`  (dry-run: no files were actually written)`);

  if (stats.gapSamples.length > 0) {
    console.log(`\n=== volume gap samples (= 巻番号の欠番、 修正は別 issue) ===`);
    for (const s of stats.gapSamples) console.log(`  ${s}`);
    if (stats.seriesWithGaps > stats.gapSamples.length) {
      console.log(
        `  ... and ${stats.seriesWithGaps - stats.gapSamples.length} more series with gaps`,
      );
    }
  }

  db.close();
}

main().catch((err) => {
  console.error("[fatal]", err);
  process.exit(1);
});

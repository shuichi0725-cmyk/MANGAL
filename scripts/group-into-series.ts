/**
 * `.cache/rakuten/*.json` (fetch-rakuten-bulk.ts の出力) を読み、
 * シリーズ単位で集約して `data/manga/_drafts/<slug>.yml` を吐く。
 *
 * 草稿には genres / publisher / demographic は TODO プレースホルダで入れる
 * （マスタキー必須なのでそのままでは loadData が落ちる仕様）。
 * 人手レビュー後に `data/manga/<slug>.yml` へ移動する想定。
 *
 * 使い方:
 *   npm run group:series                  # 全 cache を処理
 *   npm run group:series -- --limit 50    # 先頭 50 シリーズだけ生成
 *   npm run group:series -- --min-volumes 3
 *
 * シリーズキーの決定方針:
 *   1. item.seriesName が非空ならそれを正規化したものをキーにする
 *   2. seriesName が空のときは title から「(1)」「第3巻」等の巻表示を剥がしたものをキー化
 *
 * エディション分類は fetch-rakuten.ts と同じロジック（完全版/文庫版/...）。
 *
 * 1巻しか取れていないシリーズは規定で除外（artbook・読切・単発の混入が多いため）。
 */
import fs from "node:fs";
import path from "node:path";
import YAML from "yaml";
import { toRomaji } from "wanakana";

const CACHE_DIR = path.join(process.cwd(), ".cache", "rakuten");
const DRAFT_DIR = path.join(process.cwd(), "data", "manga", "_drafts");
const PUBLISHED_DIR = path.join(process.cwd(), "data", "manga");

type EditionType =
  | "standard"
  | "kanzenban"
  | "bunkobon"
  | "shinsoban"
  | "aizoban"
  | "wideban"
  | "renewal"
  | "other";

const EDITION_LABELS: Record<EditionType, string> = {
  standard: "通常版",
  kanzenban: "完全版",
  bunkobon: "文庫版",
  shinsoban: "新装版",
  aizoban: "愛蔵版",
  wideban: "ワイド版",
  renewal: "新装版（カバーリニューアル）",
  other: "その他",
};

const ORDER: EditionType[] = [
  "standard",
  "kanzenban",
  "shinsoban",
  "aizoban",
  "wideban",
  "bunkobon",
  "renewal",
  "other",
];

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
  booksGenreId?: string;
};

type CachedAuthor = {
  qid: string;
  name: string;
  items: RakutenItem[];
};

type Volume = {
  number: number;
  asin: null;
  isbn13: string | null;
  cover_url: string | null;
  release_date: string | null;
};

type EditionGroup = {
  type: EditionType;
  volumes: Map<number, Volume>;
  imprints: Set<string>;
  yearsStarted: number[];
  yearsEnded: number[];
};

type SeriesAcc = {
  key: string;
  displayTitle: string;
  titleKana: string | null;
  authors: Set<string>;
  authorsKana: Map<string, string>;
  publishers: Set<string>;
  editions: Map<EditionType, EditionGroup>;
  seenIsbn: Set<string>;
  fromMangakaQids: Set<string>;
};

type ParsedArgs = {
  limit: number | null;
  minVolumes: number;
  overwrite: boolean;
};

function parseArgs(argv: string[]): ParsedArgs {
  const out: ParsedArgs = { limit: null, minVolumes: 2, overwrite: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = argv[i + 1];
    if (a === "--limit" && next) {
      out.limit = Number(next);
      i++;
    } else if (a === "--min-volumes" && next) {
      out.minVolumes = Number(next);
      i++;
    } else if (a === "--overwrite") {
      out.overwrite = true;
    }
  }
  return out;
}

function classifyEdition(item: RakutenItem): EditionType {
  const text =
    `${item.title ?? ""} ${item.subTitle ?? ""} ${item.seriesName ?? ""}`.normalize(
      "NFKC",
    );
  if (/完全版/.test(text)) return "kanzenban";
  if (/愛蔵版/.test(text)) return "aizoban";
  if (/ワイド版/.test(text)) return "wideban";
  if (/新装版|リニューアル|カバー新装/.test(text)) return "shinsoban";
  if (/文庫/.test(text)) return "bunkobon";
  return "standard";
}

function extractVolumeNumber(item: RakutenItem): number | null {
  const candidates = [item.subTitle, item.title]
    .filter((s): s is string => Boolean(s))
    .map((s) => s.normalize("NFKC"));
  for (const text of candidates) {
    const m1 = text.match(/第\s*(\d{1,3})\s*巻/);
    if (m1) return Number(m1[1]);
    const m2 = text.match(/[（(](\d{1,3})[)）]/);
    if (m2) return Number(m2[1]);
    const m3 = text.match(/(\d{1,3})\s*$/);
    if (m3) return Number(m3[1]);
    const m4 = text.match(/\s(\d{1,3})\s/);
    if (m4) return Number(m4[1]);
  }
  return null;
}

function normalizeSalesDate(raw?: string): string | null {
  if (!raw) return null;
  const m = raw.match(/(\d{4})年(\d{1,2})月(?:(\d{1,2})日)?/);
  if (!m) return null;
  const y = m[1];
  const mo = m[2].padStart(2, "0");
  const d = m[3] ? m[3].padStart(2, "0") : null;
  return d ? `${y}-${mo}-${d}` : `${y}-${mo}`;
}

/**
 * シリーズキーの正規化:
 *  - NFKC、空白除去、小文字化
 *  - 巻表記（"(1)", "第3巻", "1" 末尾）を剥がす
 *  - 「完全版」「文庫版」「新装版」「愛蔵版」「ワイド版」を剥がす
 *    （同一作品を 1 シリーズに合流させるため）
 */
function seriesKeyFromTitle(title: string): string {
  let t = title.normalize("NFKC");
  t = t.replace(/[（(]\d{1,3}[)）]/g, "");
  t = t.replace(/第\s*\d{1,3}\s*巻/g, "");
  t = t.replace(/(完全版|文庫版|新装版|愛蔵版|ワイド版|カバーリニューアル|リニューアル)/g, "");
  t = t.replace(/[【〔（(].*?[】〕）)]/g, "");
  t = t.replace(/\s+/g, "");
  t = t.replace(/\d{1,3}\s*$/, "");
  return t.toLowerCase();
}

function seriesKeyFor(item: RakutenItem): { key: string; display: string } {
  const sn = (item.seriesName ?? "").trim();
  if (sn) {
    const key = sn.normalize("NFKC").replace(/\s+/g, "").toLowerCase();
    return { key, display: sn };
  }
  const title = item.title ?? "";
  const key = seriesKeyFromTitle(title);
  // 巻表示を剥がしたものを表示用にも使う
  const display = title
    .normalize("NFKC")
    .replace(/[（(]\d{1,3}[)）]/g, "")
    .replace(/第\s*\d{1,3}\s*巻/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return { key, display: display || title };
}

/**
 * 表示用シリーズ名から URL slug を生成。wanakana で romaji 化 → 英数字化。
 * 衝突した場合は呼び側でサフィックスを足す。
 */
function makeSlug(display: string): string {
  const romaji = toRomaji(display).toLowerCase();
  let slug = romaji
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  if (!slug) slug = "untitled";
  return slug.slice(0, 60);
}

function existingSlugSet(): Set<string> {
  if (!fs.existsSync(PUBLISHED_DIR)) return new Set();
  return new Set(
    fs
      .readdirSync(PUBLISHED_DIR)
      .filter((f) => f.endsWith(".yml") || f.endsWith(".yaml"))
      .map((f) => f.replace(/\.ya?ml$/, "")),
  );
}

function loadCaches(): CachedAuthor[] {
  if (!fs.existsSync(CACHE_DIR)) return [];
  return fs
    .readdirSync(CACHE_DIR)
    .filter((f) => f.endsWith(".json"))
    .map((f) =>
      JSON.parse(fs.readFileSync(path.join(CACHE_DIR, f), "utf8")) as CachedAuthor,
    );
}

function ingestItem(acc: SeriesAcc, item: RakutenItem, sourceQid: string) {
  const isbn = item.isbn?.trim();
  if (!isbn) return;
  if (acc.seenIsbn.has(isbn)) return;
  acc.seenIsbn.add(isbn);

  if (item.author) acc.authors.add(item.author);
  if (item.authorKana && item.author) {
    acc.authorsKana.set(item.author, item.authorKana);
  }
  if (item.publisherName) acc.publishers.add(item.publisherName);
  acc.fromMangakaQids.add(sourceQid);

  const num = extractVolumeNumber(item);
  if (num === null) return; // 巻数不明はスキップ

  const type = classifyEdition(item);
  let g = acc.editions.get(type);
  if (!g) {
    g = {
      type,
      volumes: new Map(),
      imprints: new Set(),
      yearsStarted: [],
      yearsEnded: [],
    };
    acc.editions.set(type, g);
  }
  if (item.publisherName) g.imprints.add(item.publisherName);
  const date = normalizeSalesDate(item.salesDate);
  if (date) {
    const y = Number(date.slice(0, 4));
    g.yearsStarted.push(y);
    g.yearsEnded.push(y);
  }
  g.volumes.set(num, {
    number: num,
    asin: null,
    isbn13: isbn,
    cover_url: item.largeImageUrl ?? null,
    release_date: date,
  });
}

function buildEditions(acc: SeriesAcc) {
  const editions: {
    type: EditionType;
    label: string;
    imprint?: string;
    year_started?: number;
    year_ended?: number;
    volumes: Volume[];
  }[] = [];
  for (const t of ORDER) {
    const g = acc.editions.get(t);
    if (!g) continue;
    const vols = Array.from(g.volumes.values()).sort(
      (a, b) => a.number - b.number,
    );
    editions.push({
      type: t,
      label: EDITION_LABELS[t],
      ...(g.imprints.size === 1
        ? { imprint: Array.from(g.imprints)[0] }
        : {}),
      ...(g.yearsStarted.length
        ? { year_started: Math.min(...g.yearsStarted) }
        : {}),
      ...(g.yearsEnded.length
        ? { year_ended: Math.max(...g.yearsEnded) }
        : {}),
      volumes: vols,
    });
  }
  return editions;
}

function totalVolumes(acc: SeriesAcc): number {
  let n = 0;
  for (const g of acc.editions.values()) n += g.volumes.size;
  return n;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));

  const caches = loadCaches();
  if (caches.length === 0) {
    console.error(
      `${CACHE_DIR} にキャッシュがありません。先に \`npm run fetch:rakuten:bulk\` を実行してください。`,
    );
    process.exit(1);
  }
  console.log(`[group] cache 読み込み: ${caches.length} 作家分`);

  const series = new Map<string, SeriesAcc>();
  let itemsSeen = 0;
  for (const c of caches) {
    for (const it of c.items) {
      itemsSeen++;
      const { key, display } = seriesKeyFor(it);
      if (!key) continue;
      let acc = series.get(key);
      if (!acc) {
        acc = {
          key,
          displayTitle: display,
          titleKana: it.seriesNameKana?.trim() || null,
          authors: new Set(),
          authorsKana: new Map(),
          publishers: new Set(),
          editions: new Map(),
          seenIsbn: new Set(),
          fromMangakaQids: new Set(),
        };
        series.set(key, acc);
      } else if (!acc.titleKana && it.seriesNameKana) {
        acc.titleKana = it.seriesNameKana.trim();
      }
      ingestItem(acc, it, c.qid);
    }
  }
  console.log(
    `[group] アイテム ${itemsSeen} 件 → シリーズ候補 ${series.size} 件`,
  );

  const occupiedSlugs = existingSlugSet();
  fs.mkdirSync(DRAFT_DIR, { recursive: true });
  const usedSlugs = new Set<string>(occupiedSlugs);

  let written = 0;
  let skippedFew = 0;
  let skippedExisting = 0;

  // 巻数の多いシリーズから処理（slug 衝突時に主要作品を優先するため）
  const ordered = Array.from(series.values()).sort(
    (a, b) => totalVolumes(b) - totalVolumes(a),
  );

  for (const acc of ordered) {
    if (args.limit !== null && written >= args.limit) break;

    const vols = totalVolumes(acc);
    if (vols < args.minVolumes) {
      skippedFew++;
      continue;
    }

    let slug = makeSlug(acc.displayTitle);
    if (occupiedSlugs.has(slug) && !args.overwrite) {
      // 既に手作業で確定済みの作品 → 触らない
      skippedExisting++;
      continue;
    }
    let suffix = 2;
    while (usedSlugs.has(slug)) {
      slug = `${makeSlug(acc.displayTitle)}-${suffix++}`;
    }
    usedSlugs.add(slug);

    const editions = buildEditions(acc);
    if (editions.length === 0) continue;

    const yearStarted = editions[0].year_started ?? 2000;
    const yearEnded = editions[0].year_ended ?? null;

    const draft = {
      slug,
      title: acc.displayTitle,
      title_kana: acc.titleKana ?? "TODO_kana",
      title_romaji: makeSlug(acc.displayTitle).replace(/-/g, " "),
      year_started: yearStarted,
      year_ended: yearEnded,
      status: yearEnded ? "completed" : "ongoing",
      authors: Array.from(acc.authors).map((name) => ({
        name,
        role: "writer_artist" as const,
      })),
      original_authors: [],
      publisher: "TODO_publisher_key",
      magazine: null,
      demographic: "shounen",
      genres: ["TODO_genre"],
      synopsis: "",
      editions,
    };

    const yamlText =
      `# 草稿: 楽天ブックスAPI で自動生成（要人手レビュー）\n` +
      `# Powered by 楽天ウェブサービス\n` +
      `# source mangaka qids: ${Array.from(acc.fromMangakaQids).join(", ")}\n` +
      YAML.stringify(draft);

    fs.writeFileSync(path.join(DRAFT_DIR, `${slug}.yml`), yamlText, "utf8");
    written++;
  }

  console.log("\n=== group summary ===");
  console.log(`  draft 書き出し: ${written} 本`);
  console.log(`  巻数 < ${args.minVolumes} で除外: ${skippedFew} 本`);
  console.log(`  既存 slug と衝突して見送り: ${skippedExisting} 本`);
  console.log(`  出力先: ${DRAFT_DIR}`);
}

main().catch((err) => {
  console.error("[fatal]", err);
  process.exit(1);
});

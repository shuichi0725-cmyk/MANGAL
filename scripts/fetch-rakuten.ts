/**
 * 楽天ブックスAPI（BooksBook/Search）でタイトル + 著者を検索し、
 * 結果をエディション（通常版・完全版・文庫版・新装版・愛蔵版・ワイド版・他）
 * ごとに分類した YAML 草稿を出力する。
 *
 * 使い方:
 *   npm run fetch:rakuten -- \
 *     --slug urusei-yatsura \
 *     --title "うる星やつら" \
 *     --author "高橋留美子" \
 *     [--out data/manga/_drafts/urusei-yatsura.yml] \
 *     [--max-pages 5]
 *
 * 出力 YAML はあくまで草稿なので、人手で確認した上で
 * `data/manga/<slug>.yml` に移動すること。
 *
 * 楽天ブックスAPI レート制限: 1 リクエスト/秒。
 * 取得した書誌データには「Powered by 楽天ウェブサービス」のクレジットを
 * UI 側で表示する。
 */
import "./_env";
import fs from "node:fs";
import path from "node:path";
import YAML from "yaml";

const ENDPOINT =
  "https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404";

const HITS = 30; // 1 ページあたり最大値
const REQUEST_INTERVAL_MS = 1100; // 1秒制限を満たすマージン
const MAX_RETRIES = 4;

// レディースコミック / ティーンズラブコミック など成年向けは除外。
const ADULT_GENRE_PREFIXES = [
  "001001012", // レディースコミック
  "001001014", // ティーンズラブコミック
];

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

type RakutenItem = {
  title: string;
  subTitle?: string;
  seriesName?: string;
  author?: string;
  publisherName?: string;
  isbn?: string;
  salesDate?: string;
  largeImageUrl?: string;
  mediumImageUrl?: string;
  booksGenreId?: string;
};

// formatVersion=2 ではフラット配列、=1 だと { Item: ... } 入れ子。
// このスクリプトは常に formatVersion=2 を要求しているのでフラットで受ける。
type RakutenResponse = {
  Items: RakutenItem[];
  count: number;
  page: number;
  pageCount: number;
};

type ParsedArgs = {
  slug: string;
  title: string;
  author: string;
  out: string | null;
  maxPages: number;
};

function parseArgs(argv: string[]): ParsedArgs {
  const out: ParsedArgs = {
    slug: "",
    title: "",
    author: "",
    out: null,
    maxPages: 5,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = argv[i + 1];
    if (a === "--slug" && next) {
      out.slug = next;
      i++;
    } else if (a === "--title" && next) {
      out.title = next;
      i++;
    } else if (a === "--author" && next) {
      out.author = next;
      i++;
    } else if (a === "--out" && next) {
      out.out = next;
      i++;
    } else if (a === "--max-pages" && next) {
      out.maxPages = Number(next);
      i++;
    }
  }
  return out;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function refererAndOrigin(): { referer: string; origin: string } {
  const referer = process.env.RAKUTEN_REFERER ?? "http://localhost/";
  let origin = "http://localhost";
  try {
    const u = new URL(referer);
    origin = `${u.protocol}//${u.host}`;
  } catch {
    // ignore: referer was not a valid URL; keep fallback origin
  }
  return { referer, origin };
}

async function callOnce(
  appId: string,
  accessKey: string,
  author: string,
  page: number,
): Promise<RakutenResponse> {
  const url = new URL(ENDPOINT);
  url.searchParams.set("applicationId", appId);
  url.searchParams.set("accessKey", accessKey); // 2026 新仕様: 二重認証で必須
  url.searchParams.set("format", "json");
  url.searchParams.set("formatVersion", "2");
  // title= は API 側のフィルタが新仕様で厳しく、エディション違い
  // （〔新装版〕完全版 文庫版 ワイド版 等）が漏れるため、ここでは
  // 送らず author のみで広く取り、後段の titleMatches() で絞る。
  url.searchParams.set("author", author);
  url.searchParams.set("hits", String(HITS));
  url.searchParams.set("page", String(page));
  url.searchParams.set("booksGenreId", "001001"); // 漫画（コミック）配下のみ

  const { referer, origin } = refererAndOrigin();

  const res = await fetch(url, {
    headers: {
      // Referer / Origin は楽天デベロッパーズの「許可されたWebサイト」に
      // 登録したドメインと一致している必要がある（不一致だと 403:
      // Host not in allowlist）。新仕様では Origin も必須化された。
      // デフォルトは localhost。GH Actions などからは
      // RAKUTEN_REFERER=https://github.com/ のように上書きする。
      Referer: referer,
      Origin: origin,
      "User-Agent": "MANGAL-DataFetch/0.1",
      Accept: "application/json",
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(
      `Rakuten HTTP ${res.status}: ${body.slice(0, 300)}`,
    );
  }
  return (await res.json()) as RakutenResponse;
}

async function call(
  appId: string,
  accessKey: string,
  author: string,
  page: number,
): Promise<RakutenResponse> {
  let lastErr: unknown;
  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await callOnce(appId, accessKey, author, page);
    } catch (err) {
      lastErr = err;
      const msg = err instanceof Error ? err.message : String(err);
      const retriable =
        /HTTP (429|5\d\d)/.test(msg) ||
        /timeout|ETIMEDOUT|ECONNRESET|fetch failed/i.test(msg);
      if (!retriable || attempt === MAX_RETRIES) break;
      const delay = 2000 * 2 ** (attempt - 1);
      console.warn(`  attempt ${attempt} failed: ${msg}; retrying in ${delay}ms`);
      await sleep(delay);
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error(String(lastErr));
}

function classifyEdition(item: RakutenItem): EditionType {
  const text =
    `${item.title} ${item.subTitle ?? ""} ${item.seriesName ?? ""}`.normalize(
      "NFKC",
    );
  if (/完全版/.test(text)) return "kanzenban";
  if (/愛蔵版/.test(text)) return "aizoban";
  if (/ワイド版/.test(text)) return "wideban";
  if (/新装版|リニューアル|カバー新装/.test(text)) return "shinsoban";
  if (/文庫/.test(text)) return "bunkobon";
  return "standard";
}

/**
 * タイトルから巻数を抽出。よくあるパターン:
 *   "うる星やつら 1"
 *   "うる星やつら（1）"
 *   "うる星やつら 第1巻"
 *   "うる星やつら 完全版 1"
 *   "うる星やつら〔新装版〕（1）"
 */
function extractVolumeNumber(item: RakutenItem): number | null {
  const candidates = [item.subTitle, item.title]
    .filter((s): s is string => Boolean(s))
    .map((s) => s.normalize("NFKC"));
  for (const text of candidates) {
    // 「第N巻」「全N巻」優先
    const m1 = text.match(/第\s*(\d{1,3})\s*巻/);
    if (m1) return Number(m1[1]);
    // (N) 括弧内の数字
    const m2 = text.match(/[（(](\d{1,3})[)）]/);
    if (m2) return Number(m2[1]);
    // 末尾の数字
    const m3 = text.match(/(\d{1,3})\s*$/);
    if (m3) return Number(m3[1]);
    // 中間の独立した数字
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

function isAdult(item: RakutenItem): boolean {
  const id = item.booksGenreId ?? "";
  return ADULT_GENRE_PREFIXES.some((p) => id.startsWith(p));
}

function titleMatches(item: RakutenItem, target: string): boolean {
  const norm = (s: string) => s.normalize("NFKC").replace(/\s+/g, "");
  const targetN = norm(target);
  const haystack = norm(`${item.title} ${item.subTitle ?? ""} ${item.seriesName ?? ""}`);
  return haystack.includes(targetN);
}

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

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.slug || !args.title || !args.author) {
    console.error(
      "Usage: npm run fetch:rakuten -- --slug <slug> --title <title> --author <author> [--out <path>] [--max-pages 5]",
    );
    process.exit(1);
  }

  const appId = process.env.RAKUTEN_APP_ID;
  const accessKey = process.env.RAKUTEN_ACCESS_KEY;
  if (!appId || !accessKey) {
    console.error(
      "環境変数 RAKUTEN_APP_ID と RAKUTEN_ACCESS_KEY の両方が必要です。\n" +
        "  楽天デベロッパーズ → アプリ詳細 で UUID 形式の applicationId と\n" +
        "  アクセスキーを取得し、.env.local（ローカル）または Repository\n" +
        "  Secret（GitHub Actions）に設定してください。\n" +
        "  2026年2月の API 仕様変更により旧 applicationId 単独認証は廃止。",
    );
    process.exit(1);
  }

  // 全ページ取得
  const allItems: RakutenItem[] = [];
  let pageCount = 1;
  for (let page = 1; page <= Math.min(args.maxPages, pageCount); page++) {
    if (page > 1) await sleep(REQUEST_INTERVAL_MS);
    console.log(`[fetch] page ${page}...`);
    const resp = await call(appId, accessKey, args.author, page);
    pageCount = resp.pageCount;
    for (const item of resp.Items) {
      allItems.push(item);
    }
    if (page >= pageCount) break;
  }
  console.log(`[fetch] ${allItems.length} items fetched (${pageCount} pages).`);

  // フィルタ + 分類
  const seenIsbn = new Set<string>();
  const groups = new Map<EditionType, EditionGroup>();
  let dropped = 0;
  let unnumbered = 0;

  for (const it of allItems) {
    if (isAdult(it)) {
      dropped++;
      continue;
    }
    if (!titleMatches(it, args.title)) {
      dropped++;
      continue;
    }
    const isbn = it.isbn?.trim();
    if (!isbn) {
      dropped++;
      continue;
    }
    if (seenIsbn.has(isbn)) continue;
    seenIsbn.add(isbn);

    const num = extractVolumeNumber(it);
    if (num === null) {
      unnumbered++;
      console.warn(`  [no-vol] ${it.title} / ${it.subTitle ?? ""}`);
      continue;
    }

    const type = classifyEdition(it);
    let g = groups.get(type);
    if (!g) {
      g = {
        type,
        volumes: new Map(),
        imprints: new Set(),
        yearsStarted: [],
        yearsEnded: [],
      };
      groups.set(type, g);
    }
    if (it.publisherName) g.imprints.add(it.publisherName);
    const date = normalizeSalesDate(it.salesDate);
    if (date) {
      const y = Number(date.slice(0, 4));
      g.yearsStarted.push(y);
      g.yearsEnded.push(y);
    }
    g.volumes.set(num, {
      number: num,
      asin: null,
      isbn13: isbn,
      cover_url: it.largeImageUrl ?? null,
      release_date: date,
    });
  }

  console.log(
    `[classify] ${groups.size} editions, dropped=${dropped}, unnumbered=${unnumbered}`,
  );

  // 一番情報の多い Item からメタを推定
  const firstStandard = allItems.find(
    (it) => titleMatches(it, args.title) && !isAdult(it),
  );

  type Edition = {
    type: EditionType;
    label: string;
    imprint: string | null;
    year_started: number | null;
    year_ended: number | null;
    volumes: Volume[];
  };

  const editions: Edition[] = [];
  // 表示順: standard → kanzenban → shinsoban → aizoban → wideban → bunkobon → renewal → other
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
  for (const t of ORDER) {
    const g = groups.get(t);
    if (!g) continue;
    const vols = Array.from(g.volumes.values()).sort((a, b) => a.number - b.number);
    editions.push({
      type: t,
      label: EDITION_LABELS[t],
      imprint:
        g.imprints.size === 1 ? Array.from(g.imprints)[0] : null,
      year_started: g.yearsStarted.length ? Math.min(...g.yearsStarted) : null,
      year_ended: g.yearsEnded.length ? Math.max(...g.yearsEnded) : null,
      volumes: vols,
    });
    console.log(
      `  - ${EDITION_LABELS[t]} ${vols.length} 巻 (${vols.map((v) => v.number).join(",")})`,
    );
  }

  if (editions.length === 0) {
    console.error("採用されたアイテムがありません。タイトル/著者の指定を見直してください。");
    process.exit(1);
  }

  // YAML 草稿を組み立てる
  const draft = {
    slug: args.slug,
    title: args.title,
    title_kana: "TODO_kana",
    title_romaji: "TODO_romaji",
    year_started: editions[0].year_started ?? 2000,
    year_ended: editions[0].year_ended ?? null,
    status: "completed" as const,
    authors: [{ name: args.author, role: "writer_artist" as const }],
    original_authors: [],
    publisher: "TODO_publisher_key",
    magazine: null as string | null,
    demographic: "shounen" as const,
    genres: ["TODO_genre"],
    synopsis: "",
    editions: editions.map((e) => ({
      type: e.type,
      label: e.label,
      ...(e.imprint ? { imprint: e.imprint } : {}),
      ...(e.year_started ? { year_started: e.year_started } : {}),
      ...(e.year_ended ? { year_ended: e.year_ended } : {}),
      volumes: e.volumes,
    })),
  };

  const yamlText =
    `# 草稿: 楽天ブックスAPI で自動生成（要人手レビュー）\n# Powered by 楽天ウェブサービス\n` +
    YAML.stringify(draft);

  if (args.out) {
    const outPath = path.resolve(args.out);
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, yamlText, "utf8");
    console.log(`\n[wrote] ${outPath}`);
  } else {
    process.stdout.write(yamlText);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

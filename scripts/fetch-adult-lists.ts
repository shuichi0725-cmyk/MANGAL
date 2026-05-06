/**
 * JA Wikipedia の 2 ページから「成人系出版社一覧」「成人向け漫画家一覧」を
 * 取得して SQLite に seed する。Fix C の adult_score 計算の前提データ。
 *
 *   npm run fetch:adult-lists                 # 通常実行 (前回 seed があれば差分追加)
 *   npm run fetch:adult-lists -- --refresh    # 既存テーブルを TRUNCATE して再 seed
 *
 * 出典:
 *   https://ja.wikipedia.org/wiki/成人向け漫画雑誌の一覧
 *   https://ja.wikipedia.org/wiki/日本の成人向け漫画家の一覧
 *
 * 両ページとも CC BY-SA。タイトル/出版社/作家名のリスト構造のみを取り込み、
 * 説明文や注釈は転載しない。
 *
 * 構造の前提:
 *   - 雑誌一覧ページは == <出版社名> == セクション直下に *  リスト形式で雑誌が並ぶ
 *   - 作家一覧ページは == <五十音 (あ行 / か行 / ...)> == 直下に * <作家名> 形式
 *   どちらも `prop=wikitext` で生 wikitext を取って regex で抽出する
 *   (formal HTML パースは過剰)
 */
import "./_env";
import fs from "node:fs";
import path from "node:path";
import { openDb, recordSource, tx, type DB } from "./_db";
import { normalizeCreatorName } from "../lib/edition";

const PARSE_API = "https://ja.wikipedia.org/w/api.php";
const REQUEST_INTERVAL_MS = 1100;
const MAX_RETRIES = 4;
const USER_AGENT =
  "MANGAL-DataFetch/0.1 (+https://github.com/shuichi0725-cmyk/MANGAL)";

const RAW_DIR = path.join(process.cwd(), ".cache", "wikipedia");

const ADULT_MAGAZINE_PAGE = "成人向け漫画雑誌の一覧";
const ADULT_MANGAKA_PAGE = "日本の成人向け漫画家の一覧";

type Args = { refresh: boolean };

function parseArgs(argv: string[]): Args {
  return { refresh: argv.includes("--refresh") };
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function fetchOnce(url: string): Promise<Response> {
  return fetch(url, {
    headers: {
      "User-Agent": USER_AGENT,
      Accept: "application/json",
    },
  });
}

async function fetchWithRetry(url: string, label: string): Promise<string> {
  let lastErr: unknown;
  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      const res = await fetchOnce(url);
      if (res.ok) return await res.text();
      const body = await res.text();
      throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`);
    } catch (err) {
      lastErr = err;
      const msg = err instanceof Error ? err.message : String(err);
      const retriable =
        /HTTP (429|5\d\d)/.test(msg) ||
        /timeout|ETIMEDOUT|ECONNRESET|fetch failed/i.test(msg);
      if (!retriable || attempt === MAX_RETRIES) break;
      const delay = /HTTP 429/.test(msg)
        ? 30000 * 2 ** (attempt - 1)
        : 2000 * 2 ** (attempt - 1);
      console.warn(`  [${label}] attempt ${attempt}: ${msg}; retry in ${delay}ms`);
      await sleep(delay);
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error(String(lastErr));
}

async function fetchPageWikitext(title: string): Promise<string> {
  const url =
    `${PARSE_API}?action=parse&page=${encodeURIComponent(title)}` +
    `&format=json&formatversion=2&prop=wikitext&redirects=1`;
  const text = await fetchWithRetry(url, `parse ${title}`);
  const json = JSON.parse(text) as {
    parse?: { wikitext?: string };
    error?: { code?: string };
  };
  if (json.error) throw new Error(`wiki: ${json.error.code ?? "unknown"}`);
  return json.parse?.wikitext ?? "";
}

/** wikitext の `[[link|alias]]` / `{{tmpl}}` / 装飾を雑に剥がしてプレーン化 */
function stripWikitext(s: string): string {
  let t = s;
  t = t.replace(/\[\[([^\]|]*)\|([^\]]+)\]\]/g, "$2");
  t = t.replace(/\[\[([^\]]+)\]\]/g, "$1");
  t = t.replace(/\{\{[^{}]*\}\}/g, "");
  t = t.replace(/<ref[^>]*>[\s\S]*?<\/ref>/g, "");
  t = t.replace(/<ref[^/]*\/>/g, "");
  t = t.replace(/<[^>]+>/g, "");
  t = t.replace(/'''([^']+)'''/g, "$1"); // bold
  t = t.replace(/''([^']+)''/g, "$1"); // italic
  return t.trim();
}

/**
 * `成人向け漫画雑誌の一覧` の wikitext から「セクション見出し = 出版社名」を抽出する。
 * `==<出版社名>==` 行（== H2 / === H3）を集める。誤抽出を抑えるため
 *   - 「出典」「脚注」「関連項目」「外部リンク」等の汎用見出しは無視
 *   - 1〜30 文字、CJK / Latin 混在許容
 * 特定の雑誌名は今は採用しない（後段で imprint と照合するのは出版社名で十分）。
 */
/**
 * Wikipedia 抽出から漏れた確実な成人系出版社 (manual seed)。
 * `成人向け漫画雑誌の一覧` の構造によっては section heading に出ず
 * 箇条書きや別ページに散らばっている場合があるので、ここで補完。
 *
 * 追加基準: 「成人系コミック / R-18 雑誌をメインで継続的に出版している」
 *   - 白夜書房      : 美少女系コミック・雑誌（メンズYOUNG, COMIC快楽天 旧版 等）
 *   - 久保書店      : QHコミック / 美少女系
 *   - フランス書院  : 主に R-18 ノベル + コミック
 *   - オークラ出版  : 成人向けコミック中心
 *   - 司書房        : ピアスコミックス（成人向け）
 *
 * 一般作品の方が圧倒的に多い出版社 (双葉社, 集英社系の青年誌, 講談社など) は
 * ここに入れない。レーベル単位で adult が混ざっている場合は manual override
 * (人手で `adult_publishers` を編集) で対応する想定。
 */
const MANUAL_ADULT_PUBLISHERS: ReadonlyArray<string> = [
  "白夜書房",
  "久保書店",
  "フランス書院",
  "オークラ出版",
  "司書房",
];

/**
 * Wikipedia の section heading regex で誤抽出される noise / 一般出版社の
 * deny list。これらが `adult_publishers` に紛れ込むと一般作品まで adult
 * 扱いされて false positive を量産するので明示除外する。
 *
 * 五十音見出し:   廃刊雑誌セクションが「あ行 / か行 / ...」でグルーピング
 * 一般メイン社:   双葉社・辰巳出版・リイド社等は一般作品の方が多数派なので、
 *                 imprint substring match で巻き込まないために除外する。
 *                 個別の adult レーベルが必要なら今後 manual seed に追加。
 */
const PUBLISHER_DENY_LIST: ReadonlySet<string> = new Set([
  // 五十音グルーピング見出し
  "あ行", "か行", "さ行", "た行", "な行", "は行", "ま行", "や行", "ら行", "わ行",
  "ア行", "カ行", "サ行", "タ行", "ナ行", "ハ行", "マ行", "ヤ行", "ラ行", "ワ行",
  // page 構造由来のノイズ
  "BookLive",
  "注釈",
  "発行中の雑誌の出版社別一覧",
  "廃刊雑誌の出版社別一覧",
  "出版社別一覧",
  "アンソロジーコミック",
  // 一般作品メインの出版社 (false positive 防止)
  "双葉社",
  "辰巳出版",
  "リイド社",
  "大都社",
  "メディアックス",
  "竹書房", // 一般 / アダルト両方 (一般の方が多数派)
  // Tier 1B (2026-05): adult-imprint dump (~250 entry) でゼロ件 / 0.x% 程度の
  // 大手 mainstream publisher。 publisher 単位 flag は不適切なので明示除外し、
  // adult sub-imprint があれば adult_imprints テーブル (Tier 2) で個別に拾う。
  "講談社",
  "白泉社",
  "集英社",
  "小学館",
  "秋田書店",
  "KADOKAWA",
  "角川書店",
  "学習研究社",
  "芳文社",
  "主婦と生活社",
  "祥伝社",
  "少年画報社",
  "太田出版",
  "宝島社",
  "光文社",
  "実業之日本社",
  "朝日ソノラマ",
  "ホビージャパン",
  "ジャイブ",
  "ワニブックス",
  "ポット出版",
  "ぶんか社", // adult imprint (サイベリア系) は adult_imprints で拾う、 BLACK 文庫等は mainstream
]);

/**
 * `成人向け漫画雑誌の一覧` の wikitext から「セクション見出し = 出版社名」を抽出する。
 * `==<出版社名>==` 行（== H2 / === H3）を集める。誤抽出を抑えるため
 *   - 「出典」「脚注」「関連項目」「外部リンク」等の汎用見出しは無視
 *   - 1〜30 文字、CJK / Latin 混在許容
 *   - PUBLISHER_DENY_LIST にあるものは除外
 * 特定の雑誌名は今は採用しない（後段で imprint と照合するのは出版社名で十分）。
 */
function extractAdultPublishers(wikitext: string): string[] {
  const out = new Set<string>();
  const SKIP_HEADINGS = new Set([
    "概要",
    "出典",
    "脚注",
    "関連項目",
    "外部リンク",
    "参考文献",
    "目次",
    "歴史",
    "現行誌",
    "休廃刊",
    "休廃刊雑誌",
    "現役",
    "廃刊・休刊",
    "休刊・廃刊雑誌",
  ]);
  // == 見出し == または === 見出し === にマッチ
  const re = /^={2,4}\s*([^=]+?)\s*={2,4}\s*$/gm;
  let m: RegExpExecArray | null;
  while ((m = re.exec(wikitext)) !== null) {
    const name = stripWikitext(m[1]).trim().normalize("NFKC");
    if (!name) continue;
    if (name.length < 2 || name.length > 30) continue;
    if (SKIP_HEADINGS.has(name)) continue;
    if (PUBLISHER_DENY_LIST.has(name)) continue;
    // 「現行誌」「廃刊」のような汎用キーワードを含むものはスキップ
    if (/^(現行|休|廃|現役|歴史|参考|外部|脚注|出典|関連)/.test(name)) continue;
    // 「○行」(五十音グループ) 形式の保険的フィルタ
    if (/^[あ-んア-ン]行$/.test(name)) continue;
    out.add(name);
  }
  return Array.from(out);
}

/**
 * `日本の成人向け漫画家の一覧` の wikitext から `*` リスト各行の作家名を抽出。
 * 形式例:
 *   * [[唯登詩樹]] (旧名義: 加藤雅基)
 *   * 黒咲練導
 *   * [[ねぐら☆なお]]
 * 抽出は `display` (元表記) と `normalized` (照合用) の 2 値ペアで返す。
 */
function extractAdultMangaka(
  wikitext: string,
): Array<{ display: string; normalized: string }> {
  const out: Array<{ display: string; normalized: string }> = [];
  const seen = new Set<string>();
  const lineRe = /^\*\s*(.+?)$/gm;
  let m: RegExpExecArray | null;
  while ((m = lineRe.exec(wikitext)) !== null) {
    const raw = m[1].trim();
    // メイン名は最初の [[...]] か、行頭の連続したテキスト
    let display: string | null = null;
    const linkMatch = raw.match(/^\[\[([^\]|]+)(?:\|[^\]]+)?\]\]/);
    if (linkMatch) {
      display = linkMatch[1];
    } else {
      // 平文。先頭から `(` `（` まで or 行末
      const plain = stripWikitext(raw).split(/[(（]/)[0].trim();
      if (plain) display = plain;
    }
    if (!display) continue;
    display = stripWikitext(display).trim();
    if (!display) continue;
    // 上限は parser ノイズ (引用文・複数名連結) を弾く。下限はあえて
    // 緩めにして、normalized 段階で 3 文字未満を弾く (「き い」 のように
    // raw は長くても normalize 後 2 文字になるケースを捕捉するため)。
    if (display.length > 40) continue;
    // ヘッダ行 (== あ行 == 等) や見出しっぽいテキストを弾く
    if (/^\d{4}年|^[#=]/.test(display)) continue;

    const normalized = normalizeCreatorName(display);
    if (!normalized || seen.has(normalized)) continue;
    // 正規化後 3 文字未満は別人作家との衝突リスクが極めて高い。
    // 例: Wikipedia 成人向け作家リスト の「きい」は、我々の DB の
    //     Q38276629 (堀田きいち、別名「きい」) と normalize 後完全一致し、
    //     君と僕。(集英社 Gangan) 等の mainstream 作品に
    //     wikipedia_adult_mangaka_list=2 を誤発火させる (50-name scaling
    //     test 2026-05-05 で観察)。 短名 (1-2 文字) は legitimate な
    //     adult-only 作家であっても data/seeds/adult-mangaka-supplement.yml
    //     の手動補完で救う前提とする。 publisher 側 (line 200) も length<2
    //     で同様のフィルタを入れている。
    if (normalized.length < 3) continue;
    seen.add(normalized);
    out.push({ display, normalized });
  }
  return out;
}

function persistPublishers(db: DB, names: string[]): number {
  const ins = db.prepare(
    `INSERT OR REPLACE INTO adult_publishers (name, source) VALUES (?, ?)`,
  );
  let n = 0;
  tx(db, () => {
    for (const name of names) {
      ins.run(name, "wikipedia_adult_magazines");
      n++;
    }
    // manual seed (Wikipedia 抽出から漏れた確実な成人系出版社) を追記
    for (const name of MANUAL_ADULT_PUBLISHERS) {
      ins.run(name, "manual_seed");
      n++;
    }
    recordSource(db, "wikipedia_adult_magazines", "adult_publishers", "all", {
      count: names.length,
      manual_seed: MANUAL_ADULT_PUBLISHERS.length,
    });
  });
  return n;
}

function persistMangaka(
  db: DB,
  rows: Array<{ display: string; normalized: string }>,
): number {
  const ins = db.prepare(
    `INSERT OR REPLACE INTO adult_mangaka_known (name, display, source) VALUES (?, ?, ?)`,
  );
  let n = 0;
  tx(db, () => {
    for (const r of rows) {
      ins.run(r.normalized, r.display, "wikipedia_adult_mangaka_list");
      n++;
    }
    recordSource(db, "wikipedia_adult_mangaka_list", "adult_mangaka_known", "all", {
      count: rows.length,
    });
  });
  return n;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  fs.mkdirSync(RAW_DIR, { recursive: true });
  const db = openDb();

  if (args.refresh) {
    db.exec(
      `DELETE FROM adult_publishers; DELETE FROM adult_mangaka_known;`,
    );
    console.log("[refresh] cleared adult_publishers / adult_mangaka_known");
  }

  // 1) 成人向け漫画雑誌の一覧 → 出版社名抽出
  console.log(`[wiki] fetching: ${ADULT_MAGAZINE_PAGE}`);
  const magText = await fetchPageWikitext(ADULT_MAGAZINE_PAGE);
  fs.writeFileSync(
    path.join(RAW_DIR, "adult_magazines_list.wikitext"),
    magText,
    "utf8",
  );
  const publishers = extractAdultPublishers(magText);
  console.log(`  extracted ${publishers.length} publisher headings`);

  await sleep(REQUEST_INTERVAL_MS);

  // 2) 日本の成人向け漫画家の一覧 → 作家名抽出
  console.log(`[wiki] fetching: ${ADULT_MANGAKA_PAGE}`);
  const mangakaText = await fetchPageWikitext(ADULT_MANGAKA_PAGE);
  fs.writeFileSync(
    path.join(RAW_DIR, "adult_mangaka_list.wikitext"),
    mangakaText,
    "utf8",
  );
  const mangaka = extractAdultMangaka(mangakaText);
  console.log(`  extracted ${mangaka.length} mangaka entries`);

  // 3) SQLite に書き込み
  const nPub = persistPublishers(db, publishers);
  const nMan = persistMangaka(db, mangaka);

  console.log("\n=== fetch:adult-lists summary ===");
  console.log(
    `  adult_publishers       : ${nPub} entries (${publishers.length} from wiki + ${MANUAL_ADULT_PUBLISHERS.length} manual seed)`,
  );
  console.log(`  adult_mangaka_known    : ${nMan} entries`);
  console.log(`  raw cache dir          : ${RAW_DIR}`);
  if (publishers.length > 0) {
    console.log(`  publishers sample      : ${publishers.slice(0, 8).join(", ")}`);
  }
  console.log(`  manual seed publishers : ${MANUAL_ADULT_PUBLISHERS.join(", ")}`);
  if (mangaka.length > 0) {
    console.log(
      `  mangaka sample         : ${mangaka.slice(0, 5).map((r) => r.display).join(", ")}`,
    );
  }

  db.close();
}

main().catch((err) => {
  console.error("[fatal]", err);
  process.exit(1);
});

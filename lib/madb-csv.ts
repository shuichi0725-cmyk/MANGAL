/**
 * MADB 公式 CSV (= cm101 マンガ単行本 全量、 cm104 差分) のパースと
 * 内部 record 変換、 多層 adult フィルタを担う純ライブラリ。
 *
 * 設計方針:
 *   - SPARQL 路線を廃止し、 公式 CSV の構造化 column を直接使う。
 *     既存 fetch-madb (SPARQL) で必要だった schema discovery / 完全版判定 /
 *     publisher literal 分割は CSV では不要 (= 各々 column が分離済)。
 *   - file は ≈70MB 想定 (cm101)。 Node.js の readline で 1 行ずつ
 *     parse し、 メモリは MadbCsvRow 配列に蓄積 (= ≈400k × 12 column)。
 *     一括 transaction で SQLite に投入する想定。
 *   - 改行入り field を MADB CSV は使わないことを実測確認 (= 行数 ==
 *     record 数)。 これに依存して line-based parser で OK。
 *   - 22 件存在する CSV escape (= `""` → `"`) は parser 側で吸収。
 *   - file 先頭に BOM (U+FEFF) が付与されている。 file 読み込み側で
 *     最初の行から strip する想定 (= parseCsvLine 自体は BOM 非対応)。
 *
 * adult フィルタ (= 4 層、 false-negative 抑制):
 *   1. レーティング column == "成年コミック"      ← MADB 公式 rating (= 確定)
 *   2. 概要 column に "成年コミック" 含む          ← rating 空でも abstract に書かれているケース
 *   3. 単行本レーベル が adult_imprints テーブル一致 ← 既存 Tier 2 シード流用
 *   4. 発行者名 が adult_publishers テーブル一致   ← 既存 Tier 1 シード流用
 *
 *   1 だけで cm104 内 216/216 = 100% 捕捉 (実測)。 2-4 は cm101 古い
 *   record の保険。
 */

/**
 * MADB CSV 51 列のうち、 import に使う 12 列を typed に取り出した形。
 * 列名は CSV header (= 日本語) に合わせ、 内部表現は英語化して
 * 既存 upsertVolume の MadbRec と接続しやすくする。
 */
export type MadbCsvRow = {
  /** column 1: "MADB ID" (= "M1110405" 形式) */
  madbId: string;
  /** column 2: "ISBN" (= 10/13 桁、 ハイフン入り混じり、 不正値もある) */
  isbn: string;
  /** column 3: "概要" (= "表現種別 : テキスト / ... / 成年コミック" 等の連結文字列) */
  summary: string;
  /** column 10: "公開年月日" (= "YYYY-MM-DD") */
  publishedAt: string;
  /** column 12: "作者名" (= "浅見朝志　＼＼　辻二十日" 共著は全角空白 + ＼＼ 区切り) */
  authorName: string;
  /** column 28: "タイトル" (= raw、 baseTitle 抽出元) */
  title: string;
  /** column 30: "タイトル（ヨミ）" */
  titleKana: string;
  /** column 34: "単行本レーベル" (= imprint、 例 "WANIMAGAZINE COMICS SPECIAL") */
  bookLabel: string;
  /** column 38: "発行者名" (= publisher、 例 "ワニマガジン社") */
  publisherName: string;
  /** column 45: "巻" (= volume number string、 数字以外のことも) */
  volumeNumber: string;
  /** column 49: "版表示" (= edition label、 "完全版" / "特装版" 等) */
  editionLabel: string;
  /** column 51: "レーティング" (= "成年コミック" or empty) */
  rating: string;
};

/** 1-indexed の CSV column 位置 (= header と同じ) */
const COL_INDEX = {
  madbId: 0,
  isbn: 1,
  summary: 2,
  publishedAt: 9,
  authorName: 11,
  title: 27,
  titleKana: 29,
  bookLabel: 33,
  publisherName: 37,
  volumeNumber: 44,
  editionLabel: 48,
  rating: 50,
} as const;

/** 期待 column 数 (= MADB CSV header 52 列固定: 1-MADB ID 〜 52-レーベル番号) */
export const EXPECTED_COLUMN_COUNT = 52;

/**
 * 1 行 (= 1 record) を string[] に分解する。 RFC 4180 風の最小 parser:
 *   - 各 field は double-quote で囲まれる前提
 *   - field 内の `""` は literal `"` に展開
 *   - field 区切りは引用外の `,`
 *
 * MADB CSV の実態に沿った前提:
 *   - 改行入り field は無い (= 行 == record と仮定)
 *   - 値が空の field は `""` で表現
 *   - `,` で field 終わり、 行末は EOL
 *
 * 想定外 (= 引用無し field) には optional 対応: quote が省略された場合は
 * 次の `,` までを field 値として扱う (= 警告対象)。
 */
export function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  let i = 0;
  const n = line.length;
  // expectField=true で field 開始位置に居る。 `,` を消費した直後 (= 後続
  // field を待っている状態) も同じ扱い。 行頭 / `,` 直後だけ空 field を
  // push する責任を持たせ、 quoted field 末尾で重複 push を避ける。
  let expectField = true;
  while (i < n) {
    const ch = line[i];
    if (ch === '"') {
      // quoted field
      i++;
      let buf = "";
      while (i < n) {
        if (line[i] === '"') {
          if (line[i + 1] === '"') {
            buf += '"';
            i += 2;
          } else {
            i++; // closing quote
            break;
          }
        } else {
          buf += line[i];
          i++;
        }
      }
      out.push(buf);
      expectField = false;
      // 次は `,` か EOL のはず
      if (i < n && line[i] === ",") {
        i++;
        expectField = true;
      }
    } else if (ch === ",") {
      // 直前が field 開始位置だったら、 empty field を push してから `,` を消費
      if (expectField) out.push("");
      i++;
      expectField = true;
    } else {
      // unquoted field (= MADB では通常出ないが保険)
      let buf = "";
      while (i < n && line[i] !== ",") {
        buf += line[i];
        i++;
      }
      out.push(buf);
      expectField = false;
      if (i < n && line[i] === ",") {
        i++;
        expectField = true;
      }
    }
  }
  // 行末で `,` 直後だった場合 (= trailing empty field) は明示的に push
  if (expectField) out.push("");
  return out;
}

/**
 * string[] (= parseCsvLine の出力) を MadbCsvRow に変換する。
 * column 数が EXPECTED_COLUMN_COUNT に満たない場合は null (= 不正行)。
 */
export function rowToMadbCsvRow(cells: string[]): MadbCsvRow | null {
  if (cells.length < EXPECTED_COLUMN_COUNT) return null;
  return {
    madbId: cells[COL_INDEX.madbId] ?? "",
    isbn: cells[COL_INDEX.isbn] ?? "",
    summary: cells[COL_INDEX.summary] ?? "",
    publishedAt: cells[COL_INDEX.publishedAt] ?? "",
    authorName: cells[COL_INDEX.authorName] ?? "",
    title: cells[COL_INDEX.title] ?? "",
    titleKana: cells[COL_INDEX.titleKana] ?? "",
    bookLabel: cells[COL_INDEX.bookLabel] ?? "",
    publisherName: cells[COL_INDEX.publisherName] ?? "",
    volumeNumber: cells[COL_INDEX.volumeNumber] ?? "",
    editionLabel: cells[COL_INDEX.editionLabel] ?? "",
    rating: cells[COL_INDEX.rating] ?? "",
  };
}

/**
 * MADB CSV row が成人コミックかを 4 層で判定する。
 *   1. rating == "成年コミック"               ← MADB 公式 (= 一次)
 *   2. summary に "成年コミック" 含む          ← 二次 (= rating 漏れ catch)
 *   3. bookLabel が adultImprints と一致      ← 三次 (= imprint 単位)
 *   4. publisherName が adultPublishers と一致 ← 四次 (= publisher 単位)
 *
 * いずれかにヒットしたら matched signal 名を返す (= log 用)。
 * 全部ハズレなら null。
 *
 * NFKC 正規化は呼び出し側 (= seed 側) で済ませている前提。
 */
export type AdultMatchSignal =
  | "rating"
  | "summary"
  | "imprint"
  | "publisher"
  | null;

export function isAdultMadbRecord(
  row: MadbCsvRow,
  adultImprints: ReadonlySet<string>,
  adultPublishers: ReadonlySet<string>,
): AdultMatchSignal {
  if (row.rating === "成年コミック") return "rating";
  if (row.summary.includes("成年コミック")) return "summary";
  // imprint / publisher は substring containment 不採用 (= MADB の bookLabel
  // は単体名のことが多い、 false-positive を抑える)。 完全一致のみ。
  if (row.bookLabel) {
    const norm = row.bookLabel.normalize("NFKC");
    if (adultImprints.has(norm)) return "imprint";
  }
  if (row.publisherName) {
    const norm = row.publisherName.normalize("NFKC");
    if (adultPublishers.has(norm)) return "publisher";
  }
  return null;
}

/**
 * 作者名 column (= "浅見朝志　＼＼　辻二十日") を `\\\\` 区切りで分割。
 * 区切り子は MADB の慣習で全角空白 + 半角バックスラッシュ x2 + 全角空白。
 * 役割タグ (= "[著]" 等) は MADB CSV では既に剥がされているので不要。
 */
export function splitAuthors(authorField: string): string[] {
  if (!authorField) return [];
  return authorField
    .split(/＼＼|\\\\|\u{5C}\u{5C}/u)
    .map((s) => s.replace(/[　\s]+/g, " ").trim())
    .filter(Boolean);
}

/**
 * 巻番号 column を数値化。 MADB の "巻" column は数字直のことが多いが、
 * "椿屋の源編" のような文字列もあるので、 純数字のみ採用。
 * 不正値は null を返す (呼び側で extractVolumeNumber(title) fallback 検討)。
 */
export function parseVolumeNumber(v: string): number | null {
  if (!v) return null;
  const m = v.normalize("NFKC").match(/^\d+$/);
  if (!m) return null;
  const n = Number(m[0]);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

/**
 * CSV 1 行目に付く BOM (U+FEFF) を除去する純関数。
 * file 読み込み側 (= scripts) で header 行に対してのみ呼ぶ。
 */
export function stripBom(s: string): string {
  return s.charCodeAt(0) === 0xfeff ? s.slice(1) : s;
}

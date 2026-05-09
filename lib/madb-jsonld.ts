/**
 * MADB 公式 JSON-LD (= GitHub release `metadata101_json.zip` 展開後の
 * `metadata101.json`) を 1 record ずつ extract する純ライブラリ。
 *
 * 設計方針:
 *   - GitHub release を source-of-truth にする (= portal の動的 URL より安定)。
 *     tag `1.2.15` の asset URL は固定で、 release ごとに新 tag が振られる。
 *   - file は 展開後 ≈627 MB / ≈390k records。 一括 JSON.parse は heap 不足の
 *     ため、 呼び出し側 (= scripts/fetch-madb.ts) は stream-json を使って
 *     `@graph` array を 1 element ずつ pull する。 このファイルは 1 record
 *     を typed 構造に変換する純関数を提供するのみ。
 *   - JSON-LD の field shape は MADB 独自の癖がある:
 *       * `schema:name`         ← string、 array、 object のいずれか
 *       * `schema:creator`      ← 単独/共著で形が変わる array
 *       * `schema:publisher`    ← string or array of strings
 *       * `schema:brand`        ← string or array (imprint)
 *       * `schema:contentRating`← string ("成年コミック" or "")
 *     これを robust に flatten する helper を共通化する。
 *
 * adult フィルタ (= CSV 路線と同じ 4 層):
 *   1. schema:contentRating == "成年コミック"   ← MADB 公式 (= 一次)
 *   2. schema:description に "成年コミック" 含む ← rating 漏れ catch
 *   3. brand (= 単行本レーベル) ∈ adult_imprints
 *   4. publisher (= 発行者名) ∈ adult_publishers
 */

/** JSON-LD record 内に出現する localized literal (= {@value, @language}) */
export type LocalizedLiteral = {
  "@value": string;
  "@language"?: string;
};

/**
 * MADB JSON-LD の field 型:
 *   - 単純 string
 *   - {@value, @language} の単独 object
 *   - 上記 2 つの array (= 漢字 と カナ が並ぶ)
 *   - {@id} URI 参照 (= dcterms:creator 等)
 */
export type MadbJsonLdField =
  | string
  | LocalizedLiteral
  | { "@id": string }
  | Array<string | LocalizedLiteral | { "@id": string }>;

/** JSON-LD の 1 record (= @graph[i] の生 object) */
export type MadbJsonLdRecord = {
  "@id"?: string;
  "@type"?: string;
  "rdfs:label"?: string;
  "schema:contentRating"?: string;
  "schema:isbn"?: string;
  "schema:datePublished"?: string;
  "schema:description"?: string;
  "schema:name"?: MadbJsonLdField;
  "schema:creator"?: MadbJsonLdField;
  "schema:brand"?: MadbJsonLdField;
  "schema:publisher"?: MadbJsonLdField;
  "schema:volumeNumber"?: string;
  "schema:alternativeHeadline"?: string;
  [key: string]: unknown;
};

/**
 * 内部 record (= upsertVolume に渡す前の typed shape)。
 * MadbCsvRow の置換だが、 「単一 string」 が strings[] に変わった点が違う
 * (= JSON-LD は共著で array が flat になる)。
 */
export type MadbRecord = {
  /** "M1032568" 形式 (= URI suffix) */
  madbId: string;
  /** ISBN raw (= 正規化前) */
  isbn: string;
  /** schema:contentRating (= "成年コミック" or "") */
  rating: string;
  /** schema:description (= 概要 string、 「成年コミック」 を含むことがある) */
  description: string;
  /** タイトル (= schema:name の漢字部分) */
  title: string;
  /** タイトルヨミ (= schema:name の @value, @language=ja-hrkt の object) */
  titleKana: string;
  /** サブタイトル (= schema:alternativeHeadline、 "完全版" 等が入ることあり) */
  subtitle: string;
  /** 著者 漢字名一覧 (= schema:creator の string 要素全て、 共著対応) */
  authors: string[];
  /** 単行本レーベル (= schema:brand の漢字部分) */
  brand: string;
  /** 発行者名 (= schema:publisher の string、 array なら最初の要素) */
  publisher: string;
  /** YYYY-MM-DD or partial */
  datePublished: string;
  /** 巻 (= schema:volumeNumber の数字 string、 解釈は呼び側で) */
  volumeNumber: string;
};

/**
 * JSON-LD field を string 配列に flatten。 LocalizedLiteral / @id 参照は
 * 落として、 純粋な string と {@value} の string 値を取り出す。
 *
 * MADB の field 形は以下の混合:
 *   - "単独 string"
 *   - ["string1", {@value: "kana1", @language: "ja-hrkt"}]
 *   - ["string1", "string2", {@value: "kana1", @language: "ja-hrkt"}]   ← 共著
 *   - {@id: "..."}                                                      ← URI 参照
 *
 * `keepLocalized=true` で {@value} string も配列に残す。 default は raw
 * string のみ (= 漢字相当)。
 */
/**
 * MADB の旧 format `schema:creator` (= "[著]吾峠呼世晴" / "[著]浦沢直樹,スタジオ・ナッツ"
 * 等の role prefix + comma-packed string) を clean 著者名 array に変換する。
 *
 *   "[著]吾峠呼世晴"               → ["吾峠呼世晴"]
 *   "[著]浦沢直樹,スタジオ・ナッツ"   → ["浦沢直樹", "スタジオ・ナッツ"]
 *   "原泰久"                       → ["原泰久"]                (= 新 format pass-through)
 *   "[著・画]山田太郎"              → ["山田太郎"]              (= 複合 role)
 *   "[原作]A／[漫画]B"              → ["A", "B"]               (= 全角スラッシュ separator)
 *   ""                            → []
 *
 * - 各 string について冒頭の `[<role>]` (= 任意の文字列、 ASCII bracket 必須) を除去
 * - 区切り文字 `,` `，` `、` `／` `/` で分割して個別著者に展開
 * - trim 後 empty なら drop
 *
 * authorIndex match は role を見ないので role 情報は捨てて良い (= 著者名さえ
 * mangaka.csv と一致すれば writer/artist 区別なく拾う)。
 */
export function cleanCreatorStrings(arr: string[]): string[] {
  const out: string[] = [];
  for (const raw of arr) {
    if (!raw) continue;
    const stripped = raw.replace(/\[[^\]]+\]/g, " ");
    for (const part of stripped.split(/[,，、／/]/)) {
      const t = part.trim();
      if (t) out.push(t);
    }
  }
  return out;
}

export function flattenStringArray(
  field: MadbJsonLdField | undefined,
  opts: { keepLocalized?: boolean } = {},
): string[] {
  if (field === undefined || field === null) return [];
  const result: string[] = [];
  const visit = (v: unknown): void => {
    if (typeof v === "string") {
      if (v) result.push(v);
      return;
    }
    if (Array.isArray(v)) {
      for (const x of v) visit(x);
      return;
    }
    if (typeof v === "object" && v !== null) {
      const obj = v as Record<string, unknown>;
      if (typeof obj["@value"] === "string") {
        if (opts.keepLocalized && obj["@value"]) {
          result.push(obj["@value"]);
        }
        return;
      }
      // {@id: "..."} 参照は無視
    }
  };
  visit(field);
  return result;
}

/**
 * field の最初の漢字 string を返す。 無ければ空文字。
 * (= タイトル / publisher / brand 等の primary 表記取得)
 */
export function firstString(field: MadbJsonLdField | undefined): string {
  const arr = flattenStringArray(field);
  return arr[0] ?? "";
}

/**
 * MADB literal の 「漢字 ∥ カナ」 形式から漢字部分のみ抽出する。
 *
 *   "集英社　∥　シュウエイシャ"   → "集英社"
 *   "白夜書房　∥　ビャクヤ ショボウ" → "白夜書房"
 *   "集英社"                      → "集英社"  (= ∥ 無しならそのまま)
 *
 * MADB の `schema:publisher` は ~43% の record で 全角空白 ∥ 全角空白 の前後に
 * 漢字とカナを並べる慣習があり、 publisher master との string 一致を妨げる。
 * ヨミは別 field (= {@value, @language=ja-hrkt}) に既に分離されているので、
 * literal 側のヨミは捨てて漢字側だけ採用する。
 */
export function splitMadbLiteral(s: string): string {
  if (!s) return "";
  // 全角空白を周辺許容、 半角空白も含む robust な split (= 表記揺れ対策)。
  const idx = s.search(/[\s　]*∥[\s　]*/);
  if (idx < 0) return s.trim();
  return s.slice(0, idx).trim();
}

/**
 * field の @language=ja-hrkt の @value を返す (= ヨミ取得)。 無ければ空文字。
 */
export function findKanaLiteral(field: MadbJsonLdField | undefined): string {
  if (!field) return "";
  const visit = (v: unknown): string | null => {
    if (Array.isArray(v)) {
      for (const x of v) {
        const r = visit(x);
        if (r !== null) return r;
      }
      return null;
    }
    if (typeof v === "object" && v !== null) {
      const obj = v as Record<string, unknown>;
      if (
        typeof obj["@value"] === "string" &&
        obj["@language"] === "ja-hrkt"
      ) {
        return obj["@value"];
      }
    }
    return null;
  };
  return visit(field) ?? "";
}

/**
 * MADB ID URI から接尾辞を取り出す (= "https://.../id/M1032568" → "M1032568")。
 * 不正値や空 URI (= 著者なし record の dcterms:creator が "../id/" 等) は
 * 空文字を返す。
 */
export function extractMadbId(uri: string | undefined): string {
  if (!uri) return "";
  const m = uri.match(/\/id\/([A-Za-z0-9]+)\s*$/);
  return m ? m[1] : "";
}

/**
 * MADB JSON-LD record を typed 内部 shape に変換。
 * 必須 field (@id) が無ければ null。
 */
export function extractRecord(raw: MadbJsonLdRecord): MadbRecord | null {
  const madbId = extractMadbId(raw["@id"]);
  if (!madbId) return null;
  return {
    madbId,
    isbn: typeof raw["schema:isbn"] === "string" ? raw["schema:isbn"] : "",
    rating:
      typeof raw["schema:contentRating"] === "string"
        ? raw["schema:contentRating"]
        : "",
    description:
      typeof raw["schema:description"] === "string"
        ? raw["schema:description"]
        : "",
    title: firstString(raw["schema:name"]),
    titleKana: findKanaLiteral(raw["schema:name"]),
    subtitle:
      typeof raw["schema:alternativeHeadline"] === "string"
        ? raw["schema:alternativeHeadline"]
        : "",
    // 共著の場合 schema:creator array に複数 string 要素が並ぶ。
    // {@value: kana} の object は無視 (= 漢字名のみ取り出す)。
    //
    // MADB は record によって creator 形式が異なる:
    //   - 新 format (= 2020 以降の多く): array 要素ごとに 1 著者の clean 名前
    //     例 ["原泰久", {@value: "ハラヤスヒサ"}]
    //   - 旧 format (= 2018 以前の多く): role prefix + comma-packed 1 string
    //     例 "[著]吾峠呼世晴"  /  "[著]浦沢直樹,スタジオ・ナッツ"
    //     prefix の種類: [著] [原作] [漫画] [作画] [作] [画] [絵] [編] [編集]
    //                    [監修] [著・画] [協力] etc.
    // cleanCreatorStrings で role prefix 剥離 + comma 分割 を行うことで
    // 両 format を unified array として下流に渡す。
    authors: cleanCreatorStrings(flattenStringArray(raw["schema:creator"])),
    // brand / publisher は ~43% の record で 「漢字 ∥ カナ」 形式の literal が
    // 入るので splitMadbLiteral で 漢字のみ抽出する (= でないと publisher master
    // との完全一致照合が大量に miss する)。
    brand: splitMadbLiteral(firstString(raw["schema:brand"])),
    publisher: splitMadbLiteral(firstString(raw["schema:publisher"])),
    datePublished:
      typeof raw["schema:datePublished"] === "string"
        ? raw["schema:datePublished"]
        : "",
    volumeNumber:
      typeof raw["schema:volumeNumber"] === "string"
        ? raw["schema:volumeNumber"]
        : "",
  };
}

/** 4 層 adult filter のマッチ結果 (= log 用) */
export type AdultMatchSignal =
  | "rating"
  | "description"
  | "imprint"
  | "publisher"
  | null;

/**
 * record が成年コミックかを 4 層で判定する。
 *   1. rating == "成年コミック"                ← MADB 公式 (一次)
 *   2. description に "成年コミック" 含む       ← rating 漏れ catch
 *   3. brand が adultImprints と一致           ← imprint 単位
 *   4. publisher が adultPublishers と一致     ← publisher 単位
 */
export function isAdultMadbRecord(
  rec: MadbRecord,
  adultImprints: ReadonlySet<string>,
  adultPublishers: ReadonlySet<string>,
): AdultMatchSignal {
  if (rec.rating === "成年コミック") return "rating";
  if (rec.description.includes("成年コミック")) return "description";
  if (rec.brand) {
    const norm = rec.brand.normalize("NFKC");
    if (adultImprints.has(norm)) return "imprint";
  }
  if (rec.publisher) {
    const norm = rec.publisher.normalize("NFKC");
    if (adultPublishers.has(norm)) return "publisher";
  }
  return null;
}

/**
 * 巻番号 string を数値化。 純数字のみ採用。 不正値は null。
 */
export function parseVolumeNumber(v: string): number | null {
  if (!v) return null;
  const m = v.normalize("NFKC").match(/^\d+$/);
  if (!m) return null;
  const n = Number(m[0]);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

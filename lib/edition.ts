/**
 * 単行本の「エディション種別」分類とタイトル正規化。
 *
 * 楽天 / NDL / openBD など複数ソースが返してくる書名から、
 *   - どのエディション (通常版/完全版/文庫/新装版/愛蔵版/ワイド版/...) に属すか
 *   - 巻番号は何巻か
 *   - シリーズの基底タイトル (エディション/巻番号を剥がしたもの)
 * を判定する。
 *
 * 楽天向けに scripts/fetch-rakuten*.ts に同等ロジックがインライン展開されているが、
 * NDL/openBD でも同じルールを使うため lib に集約した。fetch-rakuten 側も
 * 将来こちらに揃える（破壊的変更を避けるため移行は別コミット）。
 */

export type EditionType =
  | "standard"
  | "kanzenban"
  | "bunkobon"
  | "shinsoban"
  | "aizoban"
  | "wideban"
  | "renewal"
  | "other";

export const EDITION_LABELS: Record<EditionType, string> = {
  standard: "通常版",
  kanzenban: "完全版",
  bunkobon: "文庫版",
  shinsoban: "新装版",
  aizoban: "愛蔵版",
  wideban: "ワイド版",
  renewal: "新装版（カバーリニューアル）",
  other: "その他",
};

/** 表示順の規範（standard が常に先頭、other が最後） */
export const EDITION_ORDER: EditionType[] = [
  "standard",
  "kanzenban",
  "shinsoban",
  "aizoban",
  "wideban",
  "bunkobon",
  "renewal",
  "other",
];

/**
 * タイトル文字列からエディション種別を推定。
 * 入力は title + subTitle + seriesName を空白連結したものを想定。
 */
export function classifyEdition(text: string): EditionType {
  const t = text.normalize("NFKC");
  if (/完全版/.test(t)) return "kanzenban";
  if (/愛蔵版/.test(t)) return "aizoban";
  if (/ワイド版/.test(t)) return "wideban";
  if (/新装版|リニューアル|カバー新装/.test(t)) return "shinsoban";
  if (/文庫/.test(t)) return "bunkobon";
  return "standard";
}

/**
 * タイトルから巻番号を抽出。よくあるパターン:
 *   "うる星やつら 1"           "うる星やつら（1）"
 *   "うる星やつら 第1巻"        "うる星やつら 完全版 1"
 *   "うる星やつら〔新装版〕（1）"
 * 抽出できなければ null（読切・特装本・ガイドブック等）。
 */
export function extractVolumeNumber(text: string): number | null {
  const candidates = [text].filter(Boolean).map((s) => s.normalize("NFKC"));
  for (const t of candidates) {
    const m1 = t.match(/第\s*(\d{1,3})\s*巻/);
    if (m1) return Number(m1[1]);
    const m2 = t.match(/[（(](\d{1,3})[)）]/);
    if (m2) return Number(m2[1]);
    const m3 = t.match(/(\d{1,3})\s*$/);
    if (m3) return Number(m3[1]);
    const m4 = t.match(/\s(\d{1,3})\s/);
    if (m4) return Number(m4[1]);
  }
  return null;
}

/**
 * シリーズの「基底タイトル」を取り出す。エディション語と巻番号を剥がしたもの。
 *   "うる星やつら〔新装版〕（1）" → "うる星やつら"
 *   "うる星やつら 完全版 第3巻"   → "うる星やつら"
 * 異なるエディション間で同じシリーズに紐付けるためのキー材料。
 */
export function baseTitle(text: string): string {
  let t = text.normalize("NFKC");
  // 巻番号の括弧表記
  t = t.replace(/[（(]\d{1,3}[)）]/g, "");
  // 「第N巻」
  t = t.replace(/第\s*\d{1,3}\s*巻/g, "");
  // エディション語
  t = t.replace(
    /(完全版|文庫版|新装版|愛蔵版|ワイド版|カバーリニューアル|リニューアル|限定版)/g,
    "",
  );
  // 〔...〕や【...】内のエディション注釈をまとめて削除
  t = t.replace(/[【〔（(].*?[】〕）)]/g, "");
  // 末尾の独立した数字
  t = t.replace(/\s*\d{1,3}\s*$/, "");
  return t.trim().replace(/\s+/g, " ");
}

/**
 * シリーズキーの正規化（同シリーズ判定用）。
 *   - NFKC
 *   - 全空白除去・小文字化
 *   - エディション語と巻番号は baseTitle で剥がす
 */
export function normalizeSeriesKey(text: string): string {
  return baseTitle(text).normalize("NFKC").replace(/\s+/g, "").toLowerCase();
}

/**
 * "YYYY年MM月DD日" / "YYYY-MM-DD" / "YYYYMMDD" 等を YYYY-MM-DD に揃える。
 * 月日が無ければ "YYYY-MM" / "YYYY"。完全に解釈不能なら null。
 */
export function normalizeReleaseDate(raw: string | undefined | null): string | null {
  if (!raw) return null;
  const s = raw.normalize("NFKC").trim();

  // YYYY-MM-DD or YYYY/MM/DD
  let m = s.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})/);
  if (m) return `${m[1]}-${m[2].padStart(2, "0")}-${m[3].padStart(2, "0")}`;

  // YYYYMMDD
  m = s.match(/^(\d{4})(\d{2})(\d{2})$/);
  if (m) return `${m[1]}-${m[2]}-${m[3]}`;

  // YYYY年MM月DD日 / YYYY年MM月
  m = s.match(/(\d{4})年(\d{1,2})月(?:(\d{1,2})日)?/);
  if (m) {
    const y = m[1];
    const mo = m[2].padStart(2, "0");
    const d = m[3] ? m[3].padStart(2, "0") : null;
    return d ? `${y}-${mo}-${d}` : `${y}-${mo}`;
  }

  // YYYY-MM
  m = s.match(/^(\d{4})[-/](\d{1,2})$/);
  if (m) return `${m[1]}-${m[2].padStart(2, "0")}`;

  // YYYY のみ
  m = s.match(/^(\d{4})$/);
  if (m) return m[1];

  return null;
}

/**
 * ISBN-10 / ハイフン入り / ISBN-13 を ISBN-13 ハイフン無しに揃える。
 * 不正・JP番号・GTIN等は null。
 */
export function normalizeIsbn13(raw: string | undefined | null): string | null {
  if (!raw) return null;
  const s = raw.normalize("NFKC").replace(/[^0-9X]/gi, "");
  if (s.length === 13) return s;
  if (s.length === 10) return isbn10to13(s);
  return null;
}

function isbn10to13(isbn10: string): string | null {
  if (isbn10.length !== 10) return null;
  const body = "978" + isbn10.slice(0, 9);
  let sum = 0;
  for (let i = 0; i < 12; i++) {
    const d = Number(body[i]);
    if (Number.isNaN(d)) return null;
    sum += d * (i % 2 === 0 ? 1 : 3);
  }
  const check = (10 - (sum % 10)) % 10;
  return body + String(check);
}

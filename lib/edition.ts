import { toRomaji } from "wanakana";

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
 * 表示時の優先順位 (= EDITION_ORDER から導出)。 同 series 内で複数 edition
 * を表示する時の sort key として使う。 数値が小さいほど上に表示。
 *
 * promote-bulk で editions を並べる時に使い、 ユーザの意図する 「通常版 →
 * 完全版的なもの → その他」 の階層を出力 yaml にそのまま反映する。
 */
export const EDITION_PRIORITY: Record<EditionType, number> = Object.fromEntries(
  EDITION_ORDER.map((type, i) => [type, i]),
) as Record<EditionType, number>;

/**
 * タイトル文字列からエディション種別を推定。
 * 入力は title + subTitle + seriesName を空白連結したものを想定。
 *
 * M5 fix: 単純な if-cascade だと「完全版＋文庫版（完全版の文庫化）」のように
 * 複数キーワードが当たる場合の優先順位がハードコードされて柔軟性に欠ける。
 * スコア式に変更し、最も高スコアのものを返す。同点なら ORDER の順序が勝つ。
 */
export function classifyEdition(text: string): EditionType {
  const t = text.normalize("NFKC");
  const scores: Record<EditionType, number> = {
    standard: 1, // ベースライン
    kanzenban: 0,
    bunkobon: 0,
    shinsoban: 0,
    aizoban: 0,
    wideban: 0,
    renewal: 0,
    other: 0,
  };
  if (/完全版/.test(t)) scores.kanzenban += 3;
  if (/愛蔵版/.test(t)) scores.aizoban += 3;
  if (/ワイド版/.test(t)) scores.wideban += 3;
  if (/新装版/.test(t)) scores.shinsoban += 3;
  if (/カバー新装|カバーリニューアル/.test(t)) scores.renewal += 2;
  if (/文庫/.test(t)) scores.bunkobon += 3;

  let best: EditionType = "standard";
  let bestScore = scores.standard;
  for (const t2 of EDITION_ORDER) {
    if (scores[t2] > bestScore) {
      bestScore = scores[t2];
      best = t2;
    }
  }
  return best;
}

/**
 * タイトルから巻番号を抽出。よくあるパターン:
 *   "うる星やつら 1"           "うる星やつら（1）"
 *   "うる星やつら 第1巻"        "うる星やつら 完全版 1"
 *   "うる星やつら〔新装版〕（1）"
 *
 * 重要な落とし穴: タイトルに西暦 (例 "1980" "2024年初版") が含まれると
 * `\d{1,3}` が末尾 3 桁を貪欲マッチして 980 / 024 を巻番号と誤認する。
 * これを避けるため
 *   - 巻番号の手前は非数字境界を要求 (`(?:^|\D)`)
 *   - 4 桁以上の連続数字 (年・ISBN 部分文字列) が手前にあれば棄却
 *   - 候補が 1 個でも見つかったら早期 return せず、全体に疑わしい大きな
 *     数列がある場合に巻番号扱いを撤回する
 *
 * 抽出できなければ null（読切・特装本・ガイドブック等）。
 */
export function extractVolumeNumber(text: string): number | null {
  if (!text) return null;
  const t = text.normalize("NFKC");

  // 「第N巻」「全N巻」表記。第 が前にあれば年と誤認しない。
  const m1 = t.match(/第\s*(\d{1,3})\s*巻/);
  if (m1) return Number(m1[1]);

  // (N) または （N） — 括弧で囲まれた 1〜3 桁。年が括弧で囲まれることは稀。
  const m2 = t.match(/[（(](\d{1,3})[)）]/);
  if (m2) return Number(m2[1]);

  // 「N巻」（第なし） — "犬夜叉 5巻" "犬夜叉. 24巻" 等。
  // 直前を空白 / `.` / `,` / `:` のいずれかで区切られている事を要求して、
  // タイトル中の他の数字（年・記号埋め込み等）を巻番号と誤認しないようにする。
  const m2b = t.match(/(?:^|[\s.,:])(\d{1,3})\s*[巻集部話]/);
  if (m2b) return Number(m2b[1]);

  // 末尾の 1〜3 桁。直前は空白 (^/\s) を必須にし、「アバンチュール21」のような
  // タイトル末尾埋め込み数字（直前が文字）を巻番号と誤認しないようにする。
  // 例: "うる星やつら 1980" → 末尾 \d{1,3}="980" の直前は数字 "1" → \s 不在で棄却
  const m3 = t.match(/(?:^|\s)(\d{1,3})\s*$/);
  if (m3) {
    // さらに保険: 候補位置の前後に "年" "月" 等の年表記語が含まれれば棄却
    const idx = t.lastIndexOf(m3[1]);
    const tail = t.slice(idx);
    if (!/年|月|日|円/.test(tail)) {
      return Number(m3[1]);
    }
  }

  // 中間の独立した 1〜3 桁 — 空白境界を両側で要求 (m4 厳格化)
  const m4 = t.match(/(?:^|\s)(\d{1,3})(?=\s|$)/);
  if (m4) {
    // 4桁以上の数字塊が title 全体に存在する場合は年混入を疑い棄却
    if (/\d{4}/.test(t)) return null;
    return Number(m4[1]);
  }

  return null;
}

/**
 * シリーズの「基底タイトル」を取り出す。エディション語と巻番号を剥がしたもの。
 *   "うる星やつら〔新装版〕（1）" → "うる星やつら"
 *   "うる星やつら 完全版 第3巻"   → "うる星やつら"
 * 異なるエディション間で同じシリーズに紐付けるためのキー材料。
 *
 * M4 fix: 以前の実装は `[【〔（(].*?[】〕）)]` で全括弧内を削除していたため、
 * "(株)" のような括弧付きタイトル文字列まで巻き込んで壊した。今は
 *   「括弧の中にエディション語が含まれているとき**だけ**」削除する。
 *
 * NDL/MARC 由来の表記揺れ対策（実走で発覚した分）:
 *   - 末尾 `.` (NDL/MARC が必ず付ける終止符) を剥がす
 *     → "犬夜叉." と "犬夜叉" を同一シリーズに
 *   - `: <subtitle>` (英語タイトル / シリーズ副題) を剥がす
 *     → "境界のRINNE : Circle Of Reincarnation" → "境界のRINNE"
 *   - `= <english title>` (併記された英語タイトル) を剥がす
 *     → "うる星やつら ... = Urusei Yatsura ..." → "うる星やつら ..."
 *   - `, no.` / `. vol.` / `. v.` / `. no.` の連番表記を剥がす
 *     → "うる星やつら. no." → "うる星やつら"
 *     → "1ポンドの福音. v. 2" → "1ポンドの福音"
 */
const EDITION_TOKENS_INSIDE_BRACKETS =
  /[【〔（(][^】〕）)]*(完全版|文庫版|文庫|新装版|愛蔵版|ワイド版|カバーリニューアル|リニューアル|限定版)[^】〕）)]*[】〕）)]/g;

export function baseTitle(text: string): string {
  let t = text.normalize("NFKC");

  // 1) 「= 英語タイトル」併記を切る (= の前後にスペース必須)
  t = t.replace(/\s+=\s+.*$/, "");

  // 2) 「: サブタイトル」を切る (NDL の ISBD 慣用区切り)
  t = t.replace(/\s+:\s+.*$/, "");

  // 3) NDL/MARC + MADB の連番表記 (`, no.` `. vol.` `. v.` `. no.` `Volume.1`
  //    `chapter 5` 等)。 数字が後ろに付く/付かない両方をカバー。
  //    MADB は "Monster v.5" や "20世紀少年 Volume.1" "Monster chapter 5"
  //    のように `[.,]` 区切りなしの space 区切りで series を細分化発行する
  //    ため、 `[.,]` を optional にして `\s+` (= 空白必須) で keyword と分離。
  //    keyword (no/vol/v/volume/chapter) が必須なので "Dr. House" 等は
  //    誤マッチしない。
  t = t.replace(/\s*[.,]?\s+(no|vol|v|volume|chapter)\.?\s*\d*\s*$/i, "");

  // 4) 「. 上 / . 下 / . 上巻 / . 下巻」 「上 / 下 / 上巻 / 下巻」 の半巻表記を切る
  //    (令和版ラブセレクション / 劇場版犬夜叉時代を越える想い、
  //     MADB 「21世紀少年 上」 「21世紀少年 下」 等)
  //    `[.,]` を optional にし、 `\s+` (= 空白必須) で漢字連続による誤マッチ
  //    (= "20世紀の上の人" 等) を回避。
  t = t.replace(/\s*[.,]?\s+[上下](巻)?\s*$/, "");

  // 5) 巻番号の括弧表記（純粋に数字だけのもの）
  t = t.replace(/[（(]\d{1,3}[)）]/g, "");
  // 6) かなだけの括弧注釈 (「(りんね)」のような読み仮名注釈) を剥がす
  t = t.replace(/\s*[（(][぀-ゟ゠-ヿー]+[)）]/g, "");
  // 7) 「第N巻」「第N集」「第N部」「第N話」（N=1-999）
  t = t.replace(/第\s*\d{1,3}\s*[巻集部話]/g, "");
  // 7b) 裸の「N巻」「N集」（"犬夜叉 5巻"、"犬夜叉. 24巻"、"めぞん一刻 1集" 等）
  //     直前は空白 / `.` / `,` / `:` のいずれか。直前が CJK 文字でも OK。
  //     N は 1-999、後ろに「巻/集/部/話」が必須なので 4 桁年と紛れない。
  t = t.replace(/[\s.,:]\s*\d{1,3}\s*[巻集部話](?=\s*$|[\s,.])/g, "");
  // 8) 括弧の中にエディション語があるパターンを優先して削除
  t = t.replace(EDITION_TOKENS_INSIDE_BRACKETS, "");
  // 9) 裸（括弧外）に書かれたエディション語も削除
  t = t.replace(
    /(完全版|文庫版|新装版|愛蔵版|ワイド版|カバーリニューアル|リニューアル|限定版)/g,
    "",
  );
  // 9b) ISBD 形式 `<title>. N (<副題>)$` を剥がす。
  //     "Kirara. 1 (夢じゃない)" → "Kirara"
  //     "Kirara. 6 (元気でね!!)" → "Kirara"
  //     副題内の `)` 以外の任意文字 (CJK / Latin / 記号) を許容する `[^)]+`。
  //     直前 Latin 文字でも CJK 文字でもマッチするので、Rule 10 の CJK
  //     lookbehind 制約に補完的。
  t = t.replace(/\.\s*\d{1,3}\s*\([^)]+\)\s*$/, "");
  // 10) `. <CJK 副題>` 形式（「しゃばけ漫画. 仁吉の巻」「BLEACH. パラダイス」等）
  //     を切る。`.` の直前が CJK 文字（漢字・かな）であることを lookbehind
  //     で要求して、英文略称 (`Dr. House`) を巻き込まない。
  t = t.replace(
    /(?<=[぀-ヿ一-鿿])\.\s+\D[^.]*$/u,
    "",
  );
  // 11) 末尾の独立した数字。lookbehind で「直前が空白」を要求して、
  //     "COLORS 1978-2024" の末尾 "024" を年の一部として保護する。
  t = t.replace(/(?<=\s)\d{1,3}\s*$/, "");
  // 12) 末尾の punctuation / 空白を全部剥がす（NDL の終止符 "." を含む）
  t = t.replace(/[\s.,:;]+$/, "");
  return t.trim().replace(/\s+/g, " ");
}

/**
 * シリーズキーの正規化（同シリーズ判定用）。
 *   - NFKC
 *   - 全空白除去・小文字化
 *   - エディション語と巻番号は baseTitle で剥がす
 *
 * 注: タイトル単独だと「ハンター」「クロス」「BLUE」など短いタイトルで
 * 異なる作家のシリーズが衝突する。実際の DB キーとしては
 * buildSeriesKey(title, authorRef) を使うこと。
 */
export function normalizeSeriesKey(text: string): string {
  return baseTitle(text).normalize("NFKC").replace(/\s+/g, "").toLowerCase();
}

/**
 * SQLite series.series_key に入れるべき完全キー。
 * タイトルだけでは同名異作家の衝突が避けられないため、必ず作家識別子を含める。
 *
 *   buildSeriesKey("うる星やつら〔新装版〕(1)", "Q193300")
 *   → "norm:うる星やつら|qid:Q193300"
 *
 *   buildSeriesKey("らんま 1/2", "高橋留美子")  // QID 無しの場合
 *   → "norm:らんま1/2|name:高橋留美子"
 */
export function buildSeriesKey(
  title: string,
  authorRef: { qid?: string | null; name?: string | null },
): string {
  const titlePart = `norm:${normalizeSeriesKey(title)}`;
  const authorPart = authorRef.qid
    ? `qid:${authorRef.qid}`
    : authorRef.name
      ? `name:${authorRef.name.normalize("NFKC").replace(/\s+/g, "")}`
      : "name:_unknown";
  return `${titlePart}|${authorPart}`;
}

/**
 * タイトルから URL slug を生成する（[a-z0-9-]+ のみ）。
 *
 * 漢字は wanakana では romaji 化できないため、優先順位:
 *   1. kana ヒントが渡されたら toRomaji() でローマ字化
 *   2. それも無ければ title をそのまま toRomaji（カナ部分だけ romaji 化される）
 *   3. 結果の [a-z0-9] 文字種を取り出し、空白/記号を `-` に集約
 *   4. 60 文字で truncate
 *
 * 漢字のみのタイトルで kana ヒントが無い場合は "" を返す。
 * 呼び側でフォールバック (例: `series-<id>`) を決める。
 */
export function slugFromTitle(
  title: string,
  opts: { kana?: string | null } = {},
): string {
  const source = opts.kana && opts.kana.trim() ? opts.kana : title;
  let s = toRomaji(source.normalize("NFKC")).toLowerCase();
  // 半角化したダイアクリティカルマーク除去（macron 等）
  s = s.normalize("NFD").replace(/[̀-ͯ]/g, "");
  // [a-z0-9] 以外を - に
  s = s.replace(/[^a-z0-9]+/g, "-");
  // 端の - を除去
  s = s.replace(/^-+|-+$/g, "");
  if (!s) return "";
  return s.slice(0, 60);
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
 * ISBN-10 / ハイフン入り / ISBN-13 を ISBN-13 ハイフン無しに揃え、
 * Mod-10 チェックディジットを検証する。不正値 / JP番号 / GTIN は null。
 *
 * チェック検証無しだと NDL の OCR 誤読・typo 由来の不正 ISBN
 * （13桁数字だがチェックディジットが合わない）を DB に投入してしまい、
 * 後段の openBD/Amazon 検索で 404 を引いた時点で気付く事になる。
 * 入口でブロックするほうがクリーン。
 */
export function normalizeIsbn13(raw: string | undefined | null): string | null {
  if (!raw) return null;
  const s = raw.normalize("NFKC").replace(/[^0-9X]/gi, "");
  if (s.length === 13) return isValidIsbn13(s) ? s : null;
  if (s.length === 10) {
    if (!isValidIsbn10(s)) return null;
    return isbn10to13(s);
  }
  return null;
}

/** ISBN-13 Mod-10 チェック (978/979 prefix) */
function isValidIsbn13(s: string): boolean {
  if (!/^\d{13}$/.test(s)) return false;
  if (!/^97[89]/.test(s)) return false; // GTIN-13 で書籍以外を弾く
  let sum = 0;
  for (let i = 0; i < 12; i++) sum += Number(s[i]) * (i % 2 === 0 ? 1 : 3);
  return (10 - (sum % 10)) % 10 === Number(s[12]);
}

/** ISBN-10 Mod-11 チェック (末尾は X = 10 のときあり) */
function isValidIsbn10(s: string): boolean {
  if (!/^\d{9}[0-9X]$/i.test(s)) return false;
  let sum = 0;
  for (let i = 0; i < 9; i++) sum += Number(s[i]) * (10 - i);
  const last = s[9].toUpperCase();
  const cd = last === "X" ? 10 : Number(last);
  sum += cd;
  return sum % 11 === 0;
}

/**
 * 作家名比較用の正規化。NDL は MARC 系図書館目録規則由来で「姓, 名」
 * 形式 ("高橋, 留美子") で creator を返すことが多いので、CSV 側の
 * 「高橋留美子」と一致させるために区切り類をすべて落とす。
 * 半角/全角の空白、カンマ、中黒、句読点を全部消す。
 */
export function normalizeCreatorName(s: string): string {
  return s
    .normalize("NFKC")
    .replace(/[\s,，、・·.\-_]/g, "");
}

/**
 * NDL の creator フィールドが LCC 形式で「姓, 名」格納されている可能性に
 * 対するクエリ用変換。「高橋留美子」→「高橋, 留美子」。
 *
 * 入力の作家名から姓と名を分離する heuristic:
 *   1. 入力に空白が含まれていれば最初の空白で分ける
 *      （藤子・F・不二雄 / CLAMP メンバー名等で空白入りのケース）
 *   2. それ以外は先頭 2 文字を姓として扱う（日本人名の経験則）
 *   3. 全長が 3 未満ならそのまま返す（CLAMP / ONE 等の単名はサポート外）
 *
 * 完璧ではないので、当たらなくても fetch-ndl の variant fallback が他の
 * variant で挽回する設計。確実性ではなく「試す価値のある別形」として使う。
 */
export function toLccCreatorForm(name: string): string {
  const nfkc = name.normalize("NFKC");
  const spaceMatch = nfkc.match(/^([^\s]+)\s+(.+)$/);
  if (spaceMatch) return `${spaceMatch[1]}, ${spaceMatch[2]}`;
  if (nfkc.length >= 3) {
    return `${nfkc.slice(0, 2)}, ${nfkc.slice(2)}`;
  }
  return nfkc;
}

/**
 * NDL SRU の CQL クエリ用に文字列をエスケープする。
 * CQL 標準ではダブルクオート内のダブルクオートは バックスラッシュでエスケープ。
 * バックスラッシュ自体も二重化する。
 */
export function escapeCql(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

/**
 * 漫画家名 (alt_names 含む) のリストから NDL の CQL OR クエリを組み立てる。
 *   buildCreatorClause(["高橋留美子", "高橋るみ子"])
 *   → '(creator="高橋留美子" OR creator="高橋るみ子")'
 *
 * 4個以上ある作家 (CLAMP, 藤子・F・不二雄 系) は呼び側で分割クエリにする。
 */
export function buildCreatorClause(names: string[]): string {
  const uniq = Array.from(new Set(names.map((n) => n.trim()).filter(Boolean)));
  if (uniq.length === 0) return "";
  if (uniq.length === 1) return `creator="${escapeCql(uniq[0])}"`;
  return `(${uniq.map((n) => `creator="${escapeCql(n)}"`).join(" OR ")})`;
}

/**
 * imprint 文字列が「既知の成人系出版社」リストにマッチするかを判定する純関数。
 *   - 完全一致（NFKC 正規化後）
 *   - imprint がリスト内のいずれかの名前を **substring として含む** 場合もマッチ
 *     (例: imprint "茜新社コミックス" / "白夜書房 メディアックス" 等の派生表記)
 * 試金石レベルでは false-positive より false-negative を防ぐ方を優先する
 * （Amazon ToS 違反より誤掲載の方がリスク高いため）。誤検出が出たら
 * 個別 series で `adult_score` を override する運用。
 */
export function matchAdultPublisher(
  imprint: string | null | undefined,
  knownAdult: ReadonlySet<string>,
): string | null {
  if (!imprint) return null;
  const norm = imprint.normalize("NFKC");
  if (knownAdult.has(norm)) return norm;
  for (const name of knownAdult) {
    if (norm.includes(name)) return name;
  }
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

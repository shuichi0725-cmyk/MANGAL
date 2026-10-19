import type { Manga } from "@/lib/schema";

/**
 * ★他言語名の表示整形(2026-10-19 らんま型の全頁見直し。 ユーザ裁定A1 = AIが埋めた英題は表示しない)。
 * データ = manga.other_names(組み立て正本 = scripts/_other_names.py。 言語コード付き・表示順に並んでいる)。
 * 英語・中国語・韓国語は常に見せ、残りの言語と「その他の表記」(言語不明のラテン文字)は畳む。
 */

const LANG_LABEL: Record<string, string> = {
  en: "英語",
  zh: "中国語",
  ko: "韓国語",
  th: "タイ語",
  vi: "ベトナム語",
  id: "インドネシア語",
  fr: "フランス語",
  de: "ドイツ語",
  it: "イタリア語",
  es: "スペイン語",
  pt: "ポルトガル語",
  ru: "ロシア語",
  pl: "ポーランド語",
  ar: "アラビア語",
  alt: "その他の表記",
};
/** 中国語は簡体/繁体/無印を1行にまとめ、字体を小さな札で添える */
const ZH_TAG: Record<string, string> = { "zh-hans": "簡", "zh-hant": "繁" };
const PRIMARY = new Set(["en", "zh", "ko"]);

export type OtherNameRow = { lang: string; label: string; names: { name: string; tag?: string }[] };
export type OtherNamesView = {
  primary: OtherNameRow[];
  rest: OtherNameRow[];
  /** 畳んだ部分の見出し(例「ほか4言語・その他の表記」) */
  restSummary: string;
  /** 日本語の別名(AniList synonyms の仮名入り・題の漢字だけの略称) */
  jaAliases: string[];
  /** 検索エンジン向け(JSON-LD alternateName / 頁下の別題) */
  all: string[];
};

/** 重複判定キー(scripts/_other_names.py の _n と同じ考え方: NFKC・空白記号除去・小文字) */
const norm = (s: string) => s.normalize("NFKC").replace(/[\s\p{P}\p{S}]+/gu, "").toLowerCase();
const KANA = /[぀-ヿㇰ-ㇿｦ-ﾟ]/;
const HAN = /[㐀-鿿]/;

/** other_names 欄が無い頁(=未処理の旧データ)は null = 呼び出し側が旧表示を使う */
export function otherNamesView(m: Manga): OtherNamesView | null {
  if (!m.other_names) return null;
  const rows = new Map<string, OtherNameRow>();
  for (const o of m.other_names) {
    const lang = o.lang.startsWith("zh") ? "zh" : o.lang;
    const label = LANG_LABEL[lang];
    if (!label) continue;
    if (!rows.has(lang)) rows.set(lang, { lang, label, names: [] });
    rows.get(lang)!.names.push({ name: o.name, tag: ZH_TAG[o.lang] });
  }
  const all = [...rows.values()];
  let primary = all.filter((r) => PRIMARY.has(r.lang));
  let rest = all.filter((r) => !PRIMARY.has(r.lang));
  // 英中韓が1つも無い頁は、言語の分かる行を先頭3行まで見せる(「その他の表記」は畳んだまま)
  if (primary.length === 0) {
    const langRows = rest.filter((r) => r.lang !== "alt");
    primary = langRows.slice(0, 3);
    rest = rest.filter((r) => !primary.includes(r));
  }
  const nLang = rest.filter((r) => r.lang !== "alt").length;
  const hasAlt = rest.some((r) => r.lang === "alt");
  const restSummary = [nLang ? `ほか${nLang}言語` : "", hasAlt ? "その他の表記" : ""].filter(Boolean).join("・");

  const otherSet = new Set(m.other_names.map((o) => norm(o.name)));
  const titleSet = new Set([m.title, m.title_kana].filter(Boolean).map((s) => norm(s as string)));
  const jaAliases = (m.synonyms ?? []).filter((s) => {
    const k = norm(s);
    if (titleSet.has(k) || otherSet.has(k)) return false;
    return KANA.test(s) || HAN.test(s);
  });
  return {
    primary,
    rest,
    restSummary,
    jaAliases,
    all: [...m.other_names.map((o) => o.name), ...jaAliases],
  };
}

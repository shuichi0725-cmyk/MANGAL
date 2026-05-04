/**
 * 漢字混じり日本語タイトルを「ヨミガナ」(katakana) に変換するユーティリティ。
 *
 * 用途: NDL の dcndl:titleTranscription が空のシリーズ（純粋漢字タイトル）で
 * slug を URL 安全な英数字列に出来るようにするため、kuromoji の形態素解析で
 * 各形態素の reading を取り出して連結する。
 *
 *   "犬夜叉"            → "イヌヤシャ"
 *   "1ポンドの福音"      → "1ポンドノフクイン"
 *   "あしたのジョー"      → "アシタノジョー"  (kana のままパススルー)
 *   "Astro Boy"          → "Astro Boy"      (Latin はそのまま)
 *
 * kuromoji は CJS 由来で、辞書ロードに 3〜5 秒かかる。プロセス全体で
 * tokenizer インスタンスを 1 つ持ち回す（lazy singleton）。
 */
import path from "node:path";
import kuromoji, { type IpadicFeatures, type Tokenizer } from "kuromoji";

let tokenizerPromise: Promise<Tokenizer<IpadicFeatures>> | null = null;

function getTokenizer(): Promise<Tokenizer<IpadicFeatures>> {
  if (!tokenizerPromise) {
    const dicPath = path.join(
      process.cwd(),
      "node_modules",
      "kuromoji",
      "dict",
    );
    tokenizerPromise = new Promise((resolve, reject) => {
      kuromoji.builder({ dicPath }).build((err, tokenizer) => {
        if (err) reject(err);
        else resolve(tokenizer);
      });
    });
  }
  return tokenizerPromise;
}

/** 一度初期化した tokenizer を持っているか（テスト用 / プロセス終了確認用） */
export function isTokenizerInitialized(): boolean {
  return tokenizerPromise !== null;
}

/**
 * タイトル文字列を kuromoji で形態素解析し、各形態素の reading を連結して返す。
 * reading は katakana。連結結果も katakana ベース（slug 化は呼び側で wanakana
 * の toRomaji() に通すと "inuyasha" のような英字 slug が得られる）。
 *
 * 失敗時 / 空入力時は入力をそのまま返す（呼び側で fallback できるよう、
 * 例外は throw せず文字列を返す）。
 */
export async function readKanaFromTitle(title: string): Promise<string> {
  if (!title || !title.trim()) return "";
  let tokenizer: Tokenizer<IpadicFeatures>;
  try {
    tokenizer = await getTokenizer();
  } catch (err) {
    console.warn(`[kana] tokenizer init failed: ${err instanceof Error ? err.message : err}`);
    return title;
  }
  try {
    const tokens = tokenizer.tokenize(title);
    const out = tokens
      .map((t) => {
        // surface_form: 元の文字列, reading: カタカナ読み (なければ undefined or "*")
        const r = t.reading;
        if (r && r !== "*") return r;
        return t.surface_form;
      })
      .join("");
    return out;
  } catch (err) {
    console.warn(`[kana] tokenize "${title}" failed: ${err instanceof Error ? err.message : err}`);
    return title;
  }
}

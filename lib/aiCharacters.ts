/**
 * AI書評家リーグの「キャラクター(アバター)」定義。
 * 字ばかりの書評を、顔つきで読みやすく・誰の評か一目で分かるようにする飾り。
 *
 * ★法務メモ([[ai_review_league_operation]] / 2026-06-17 ユーザ方針):
 *  - キャラは **オリジナルの飾り**。 ブランド名・ロゴは使わず、 連想名も UI で名乗らせない。
 *  - どの AI が書いたかは **事実として実名テキスト**(model / vendor)で別に表示する(指名的利用)。
 *  - 「キャラはイメージ・各社/公式とは無関係」を明記する(コンポーネント側で表示)。
 *  - 各書評は各 AI の出力 verbatim(出所は正直)。
 *
 * 将来、 ユーザ作のドット絵スプライトを `public/ai-characters/<key>.png` に置けば
 * `img` を足すだけで絵に差し替え可能(今は emoji フォールバック)。
 */
export type AiCharacter = {
  key: string;
  /** emoji フェイス(スプライト未配置時のフォールバック) */
  face: string;
  /** 任意: 差し替え用スプライト(public 配下)。 未指定なら face を使う */
  img?: string;
  /** アクセント色(枠・チップ) */
  color: string;
  /** 背景の淡色 */
  tint: string;
};

const DEFAULT_CHAR: AiCharacter = {
  key: "ai",
  face: "🤖",
  color: "#6b7280",
  tint: "rgba(107,114,128,0.12)",
};

/** vendor(会社名)→ キャラ。 ブランド連想名は持たせない(飾りのみ)。 */
const BY_VENDOR: Record<string, AiCharacter> = {
  anthropic: { key: "octo", face: "🐙", color: "#e0892e", tint: "rgba(224,137,46,0.14)" },
  openai: { key: "squid", face: "🦑", color: "#13a37f", tint: "rgba(19,163,127,0.14)" },
  deepseek: { key: "whale", face: "🐳", color: "#2563eb", tint: "rgba(37,99,235,0.13)" },
  alibaba: { key: "wizard", face: "🧙", color: "#8b5cf6", tint: "rgba(139,92,246,0.14)" },
  google: { key: "ghost", face: "👻", color: "#6366f1", tint: "rgba(99,102,241,0.14)" },
  xai: { key: "shades", face: "😎", color: "#475569", tint: "rgba(71,85,105,0.14)" },
  moonshot: { key: "moon", face: "🌙", color: "#0ea5e9", tint: "rgba(14,165,233,0.14)" },
};

/** vendor 文字列(例 "Anthropic")からキャラを引く。 未知は汎用ロボ。 */
export function characterFor(vendor: string): AiCharacter {
  const k = (vendor || "").toLowerCase().replace(/[^a-z]/g, "");
  return BY_VENDOR[k] ?? DEFAULT_CHAR;
}

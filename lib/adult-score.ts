/**
 * Fix C: Adult-score の多層シグナル合算ロジック (純関数)。
 *
 * 重み設計 (Option B: 作家シグナルだけでは skip しない):
 *   wikidata_hentai_credit       : 2  ← 作家全体に hentai クレジットがあっても、
 *                                       同じ作家が一般青年誌で描いた作品まで巻き込まない
 *                                       ように単独では threshold(3) に届かないようにする
 *   wikipedia_adult_mangaka_list : 2  ← 同上
 *   adult_publisher_imprint      : 3  ← 出版社/レーベルが成人系なら作品単位で確定
 *
 * 結果 (利用側 promote-bulk は score >= 3 で draft skip):
 *   作家シグナルのみ                      → score = 2  → drafted
 *   出版社シグナルのみ                    → score = 3  → skip
 *   作家 + 出版社                         → score = 5  → skip (強い確証)
 *   作家両方ヒット (Wikidata + Wiki list) → score = 4  → skip
 *
 * Phase 5 で `amazon_browse_node_adult` signal を追加する余地あり (`amazon_metadata`
 * テーブルの `is_adult_browse_node` を参照する形)。
 */
import { matchAdultPublisher, normalizeCreatorName } from "./edition";

export type AdultSignal = {
  signal: string;
  weight: number;
  evidence: string;
};

export type AdultScoreResult = {
  score: number;
  signals: AdultSignal[];
};

export type AdultScoreInput = {
  hasWikidataCredit: boolean;
  authorName: string;
  imprints: string[];
  knownAdultMangaka: ReadonlySet<string>;
  knownAdultPublishers: ReadonlySet<string>;
};

export function computeAdultScore(input: AdultScoreInput): AdultScoreResult {
  let score = 0;
  const signals: AdultSignal[] = [];

  // 1. Wikidata の hentai-genre クレジット (mangaka.has_adult_credit=1)
  if (input.hasWikidataCredit) {
    score += 2;
    signals.push({
      signal: "wikidata_hentai_credit",
      weight: 2,
      evidence: input.authorName,
    });
  }

  // 2. 既知の成人向け漫画家リスト (Wikipedia 由来) に名前一致
  const norm = normalizeCreatorName(input.authorName);
  if (norm && input.knownAdultMangaka.has(norm)) {
    score += 2;
    signals.push({
      signal: "wikipedia_adult_mangaka_list",
      weight: 2,
      evidence: input.authorName,
    });
  }

  // 3. imprint が既知の成人系出版社に部分一致 (同一 series 内で複数当たっても 1 回だけ加算)
  for (const imprint of input.imprints) {
    const matched = matchAdultPublisher(imprint, input.knownAdultPublishers);
    if (matched) {
      score += 3;
      signals.push({
        signal: "adult_publisher_imprint",
        weight: 3,
        evidence: `${imprint} ⟵ ${matched}`,
      });
      break;
    }
  }

  return { score, signals };
}

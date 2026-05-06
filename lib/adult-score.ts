/**
 * Fix C: Adult-score の多層シグナル合算ロジック (純関数)。
 *
 * 重み設計 (Option B: 作家シグナルだけでは skip しない):
 *   wikidata_hentai_credit              : 2
 *   wikipedia_adult_mangaka_list        : 2
 *   adult_imprint                       : 3  ← imprint 単位 (granular)
 *   adult_publisher_imprint             : 3  ← publisher 単位 (coarse)
 *   adult_mangaka_borderline_publisher  : 3  ← (Option A) 既知 adult mangaka
 *                                              × 中堅 publisher の連結シグナル
 *
 * 結果 (利用側 promote-bulk は score >= 3 で draft skip):
 *   作家シグナルのみ                      → score = 2  → drafted
 *   imprint / publisher シグナルのみ      → score = 3  → skip
 *   borderline 連結 (作家 + 中堅 publisher) → score = 2 + 3 = 5 → skip
 *   作家 + imprint / publisher            → score = 5  → skip (強い確証)
 *   作家両方ヒット (Wikidata + Wiki list) → score = 4  → skip
 *
 * publisher 系シグナル (3 種) の排他関係:
 *   adult_imprint > adult_publisher_imprint > adult_mangaka_borderline_publisher
 *   の順で先勝ち、 一つ発火したら他はスキップ。 同種 (= レーベル/出版社の
 *   adult 照合) なので独立証拠ではない、 という思想で重複加算しない。
 *
 * borderline 連結シグナルの動機:
 *   NDL の editions.imprint には出版社名しか入っておらず、 サブレーベル名
 *   (クリベロン、 ペンギンクラブ等) は取得できない → adult_imprints テーブル
 *   での substring match では倉科遼の女帝・嬢王 (リイド社) を捕捉できない。
 *   「Wikipedia 由来 adult mangaka × 中堅 publisher (リイド社等)」 の AND を
 *   取って publisher 単位の偽陽性を抑えつつ広く拾う。
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
  knownAdultImprints: ReadonlySet<string>;
  borderlineAdultPublishers: ReadonlySet<string>;
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

  // 3. imprint 単位の adult 判定 (granular)。 一致すれば 4 (publisher) はスキップ。
  let imprintMatched = false;
  for (const imprint of input.imprints) {
    const matched = matchAdultPublisher(imprint, input.knownAdultImprints);
    if (matched) {
      score += 3;
      signals.push({
        signal: "adult_imprint",
        weight: 3,
        evidence: `${imprint} ⟵ ${matched}`,
      });
      imprintMatched = true;
      break;
    }
  }

  // 4. publisher 単位の adult 判定 (coarser)。 imprint で当たらなかった時のみ。
  let publisherMatched = false;
  if (!imprintMatched) {
    for (const imprint of input.imprints) {
      const matched = matchAdultPublisher(imprint, input.knownAdultPublishers);
      if (matched) {
        score += 3;
        signals.push({
          signal: "adult_publisher_imprint",
          weight: 3,
          evidence: `${imprint} ⟵ ${matched}`,
        });
        publisherMatched = true;
        break;
      }
    }
  }

  // 5. (Option A) Borderline publisher × 既知 adult mangaka の連結シグナル。
  //    純 adult publisher ではないが adult カタログも持つ中堅 publisher で、
  //    かつ作家が wikipedia_adult_mangaka_list 該当の場合に +3。 step 3/4 で
  //    既に publisher 系シグナルが発火している場合は重複加算しない。
  const mangakaIsKnown = norm !== "" && input.knownAdultMangaka.has(norm);
  if (!imprintMatched && !publisherMatched && mangakaIsKnown) {
    for (const imprint of input.imprints) {
      const matched = matchAdultPublisher(
        imprint,
        input.borderlineAdultPublishers,
      );
      if (matched) {
        score += 3;
        signals.push({
          signal: "adult_mangaka_borderline_publisher",
          weight: 3,
          evidence: `${input.authorName} × ${imprint} ⟵ ${matched}`,
        });
        break;
      }
    }
  }

  return { score, signals };
}

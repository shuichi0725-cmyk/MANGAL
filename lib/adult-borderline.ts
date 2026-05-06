/**
 * Borderline adult publishers: 中堅 publisher で adult カタログも持つ。
 *
 * adult_publishers (= 純 adult publisher、 adult_score +3 単独で発火) には
 * 入らないが、 dump (manga-db.com) 上で adult 出版が確認されている。 一般
 * 作品も併売しているため publisher 単位 flag では使えないが、 wikipedia_
 * adult_mangaka_known の作家がここで作品を出している場合、 「borderline ×
 * known adult mangaka」 の連結シグナル (+3) で adult 判定の追加証拠とする。
 *
 * 構造的背景: NDL の editions.imprint カラムには出版社名しか入っておらず、
 * 真のサブレーベル名 (クリベロン等) は取得できない。 そのため adult_imprints
 * テーブル (Tier 2) の substring match だけでは倉科遼の女帝・嬢王 (リイド社)
 * 系を捕捉できない。 この borderline list はその穴を埋める保険。
 *
 * メンテナンス方針:
 *   - 既知 adult mangaka × ここの publisher の組合せが mainstream 作品で
 *     誤検出された (= false positive) 場合、 該当 publisher を外す
 *   - dump で adult カタログが圧倒的に多いことが確認できた publisher のみ採用
 *   - 純 adult publisher (例: 茜新社、 ワニマガジン社) はここに入れない
 *     (adult_publishers でカバー済)
 *   - 講談社・集英社・小学館・KADOKAWA・秋田書店 のような pure mainstream は
 *     入れない (倉科遼/沖圭一郎が一般青年誌で出した作品を巻き込まないため)
 */
export const BORDERLINE_ADULT_PUBLISHERS: ReadonlySet<string> = new Set([
  // 倉科遼の女帝・嬢王・夜王、 ふじいあきこ等。 クリベロン/メンズゴールド系
  "リイド社",
  // 倉科遼のパチンカー戦国絵巻、 沖圭一郎の劇画
  "日本文芸社",
  // ペンギンクラブ、 WEBバズーカ、 漫画ローレンス、 COMIC桃姫DEEPEST 系
  "辰巳出版",
  // サイベリア系 (3500+ vol、 dump 確認済)
  "ぶんか社",
  // 人妻もの・ヤング系の adult アンソロジー (ふじいあきこの大胆告白等)
  "竹書房",
  // MD コミックス、 EROS BOYS、 マイウェイコミックス 系
  "メディアックス",
  // ガールズポップ、 禁断ハーレム、 危険恋愛M、 エースファイブ 等大量 adult アンソロ
  "松文館",
  // 禁断ハーレム、 本能爆発、 マンガの金字塔、 女子校生美女マニア 系
  "グループ・ゼロ",
]);

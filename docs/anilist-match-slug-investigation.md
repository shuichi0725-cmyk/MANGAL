# AniList マッチング & slug 精度 調査レポート(夜間自走 2026-05-31)

> ユーザ指示: 8h上限、 マッチ率改善とフォルダ(slug)精度向上の**調査に徹する**
> (実データ変更なし)。 限界まで色々試し、 朝読めるよう docs にまとめる。
> 最優先 = ①確実なマッチ ②正しい slug。 表示バグ対策で成果は本ファイル(commit)に集約。

## ガード(遵守事項)
- 種2 / 種3 / 本番 manga.v2 は**変更しない**(matcher実験は sandbox・.cache、 結果は本doc)
- slug rename・productionization 適用は**しない**(修正案の提示まで=朝ユーザ承認待ち)
- AniList 再dump は**新ファイル**へ(既存 dump 保持)。 取得=追加であり既存破壊なし

## 進捗サマリ(随時更新)
- [x] D. 種a データ拡充テスト(100件全項目)→ 再dump推奨フィールド確定
- [~] D. 全件 re-dump(高価値項目)= 実行中(background)
- [x] A. S180 誤マッチ率 実測 + 失敗パターン分類 → **FP率 0.1〜0.3%、 S180安全**
- [ ] C. slug 正確性監査(種aマッチ×slugソース突合)
- [ ] B. recall(著者経由23,304 / DISPLACED3,298 / 正規化)
- [ ] 今後の作業推奨テキスト

## ★最重要の発見(先に要約)
1. **S180(30,617件)は安全** = 99%が著者/en裏取り有、 最危険群でも実FPは僅少 → productionization に使える。
2. **著者正規化に系統的弱点**(romaji↔カタカナ・漢字異体字・名前順・韓国名hanja↔hangul・**翻訳者混入**)。 これが「偽の著者MISMATCH」を生み、 **弱スコア帯では本物マッチを取りこぼす(recall損失)主因**。 → ここの改善が最大の伸びしろ。
3. **真の誤マッチの型** = 同題+同年+著者が真に別+巻数で確認できない(例: パンドラ 明智抄↔よしながふみ / ジュエルペット 別作画)。 専用ガードで捕捉可能。

---

## 現状(調査開始時点の数値)

`match-v9-all.tsv`(種3 全 76,435 / matcher = `_audit-match-v9.py`):

| verdict | 件数 | 意味 |
|---|---|---|
| S180 | 30,617 | 高信頼マッチ(a_id 有) |
| S150 | 1,932 | 中信頼 |
| S130 | 671 | |
| S100 | 793 | |
| **S系 計** | **34,013 (44.5%)** | 確度ありマッチ |
| DISPLACED | 3,298 | 候補有→1:1競合で他に取られた(a_id空=recall ロス、 誤マッチではない) |
| REJECT | 2,250 | 候補有→ガードで棄却 |
| NO_MATCH | 36,874 | 候補なし(うち約23,304は著者がAniListに実在=著者経由の余地) |

種a由来 種3補完の現状: `alternative_titles.en` のみ結線済(S180×2,820、 commit ba44a8a)。
`anilist_id / synonyms / genres_anilist` は未投入(箱のみ)。

---

## D. 種a データ拡充(100件全項目テスト)

ツール: `scripts/_anilist-fulltest-100.py`(S180マッチ100件を全項目再取得)。
現 dump に無い候補項目の充足率を実測:

| 新項目 | 充足率 | マッチ価値 |
|---|---|---|
| **popularity** | **100%** | ★最強の tie-break(同名曖昧を人気で裁定) |
| description | 87% | あらすじ照合(英↔日=keyword重なりで曖昧判別) |
| meanScore | 84% | tie-break 補助 |
| idMal | 80% | MAL経由 cross-ref / fallback照合 |
| endDate(年) | 73% | 年レンジ照合の補強(現在 startDate のみ) |
| chapters | 68% | ✗ volumes空の補完は **1/100** = ほぼ無価値 |
| externalLinks | 44% | △ 出版社リンクのみ(ISBN無)=種2裏取り弱い |
| characters | 24% | ✗ 低充足 |
| synonyms | 平均1.4 | 現dumpと同等(enrichment無し) |

**結論**: 全件 re-dump で **popularity / meanScore / description / endDate / idMal** を
追加する価値あり(特に popularity=100%・軽量・強い tie-break)。
chapters / externalLinks / characters は費用対効果低く優先度下げ。
→ 既存 dump を保持したまま新ファイルへ再取得を実行(下記 B/C の照合に反映)。
ツール: `scripts/_anilist-dump-v3.py`(v2 流用 + description/popularity/meanScore/
averageScore/favourites/chapters/isLicensed 追加、 出力 `anilist-manga-dump-v3.jsonl.gz`)。

---

## A. S180 誤マッチ率 実測

ツール: `scripts/_audit-s180-fp.py`(S180を corroboration 強度で分類)。

| 分類 | 件数 | |
|---|---|---|
| SAFE(著者 or en 裏取り有) | 30,520 | **99%** |
| R2(裏取り無し=題+年/巻のみ) | 76 | 0% |
| R1(author_MISMATCH なのに180=最危険) | 21 | 0% |

**R1 21件を全数精査** → 「MISMATCH」の大半は**偽の食い違い**:
- romaji↔カタカナ未橋渡し: Boichi↔ボウイチ / judal↔ジュダル / abec
- 漢字異体・名前順: 神﨑↔神崎 / 栄羽弥↔羽弥栄 / あだち充↔安達充 / おおや和美↔おおやかずみ
- 韓国名 hanja↔hangul: 朴晟佑↔박성우
- **a_authors に翻訳者混入**: モブサイコ100「one」↔翻訳者群 / 青のフラッグ「kaito」↔翻訳者
- → 真の誤マッチは **パンドラ(明智抄↔よしながふみ、 同年1995・別作品)/ ジュエルペット(別作画)/ (疑)第九のマギア・未来の僕らのためのソナタ** = **2〜4件 / 21**。

**R2 76件サンプル精査** → 題が完全一致 + 年/巻 exact。 著者裏取り無しは「片側の著者データが空」なだけ = **実質ほぼ全て正当**。

**→ S180 実FP率 ≈ 0.1〜0.3%(数十件/30,617)。 productionization に安全。**
高リスク群: `.cache/s180-fp-R1-mismatch.tsv`(21) / `s180-fp-R2-noauthor.tsv`(76)。

### A から導かれる改善(matcher、 ※本番未適用=提案)
1. **著者正規化の強化**(recall の最大伸びしろ): romaji↔カタカナ橋渡し、 漢字異体字
   吸収(﨑=崎 等)、 名前順非依存(集合比較)、 韓国名 hanja↔hangul。 現状これらが
   偽MISMATCH(-40)を生み、 弱スコア帯で本物を取りこぼす。
2. **翻訳者フィルタ**: 種a staff は role 付きで取得済 → a_authors を Story/Art/原作系
   role に限定(Translator/Letterer 除外)。 翻訳者混入が偽MISMATCH源。
3. **真FPガード**: 同題+著者が真に別(正規化後も)+巻数で確認できない → 保留/減点
   (パンドラ・ジュエルペット型)。

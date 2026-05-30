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
- [x] C. slug 正確性監査 → **カタカナ英語綴り是正 5,299件 + 衝突4,523群 + 生成バグ**
- [x] B. recall(著者経由)→ **+3,815件回収可(精度~80%)、 目標44.5%→~50-52%**
- [x] 今後の作業推奨テキスト(本doc末尾)
- [~] 追加実験(imprint接頭辞 / popularity tie-break = re-dump完了後)

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

---

## C. slug(フォルダ名)正確性 監査

ツール: `scripts/_slug-prototype-audit.py`(title_kana_segmented → pykakasi ヘボン slug を
全76,435件で試作 → カバレッジ/衝突/種a romaji 突合)。

### 前提の発見
現 `makeSlug`(group-into-series.ts)= **display(漢字含む)を wanakana で romaji 化**。
wanakana は漢字非対応 → 漢字題で破綻。 既存42 slug は旧「英語名優先」or 手動由来。
**CLAUDE.md 新規則(title_kana 起点ヘボン + カタカナは元綴り)は未実装**。
→ 全件 slug 生成器を新規則で作り直す必要(本番未着手の領域)。

### 試作の結果
- **カバレッジ: 76,417 / 76,435(99.98%)** が title_kana からヘボン slug 生成可(空18=外国残渣)。
- **字種分布**: 漢字含む 66% / カタカナ主体 13% / ひらがな 9% / 英字のみ 5% / 数字 4%。
- **種a romaji 突合: 一致44% / 不一致55%(18,965)**。 ★不一致の正体を精査 → **大半は読み崩れでなく系統差**:

| 不一致の型 | 例 | 意味 |
|---|---|---|
| **カタカナ外来語の英語化** | アーマ `aama`→**Armor** / ベアー→**Bear** / サックス→**Sax** / ナイトブラッド→**Night Blood** | ★CLAUDE.md規則#4そのもの。 種aが正しい元綴りを示す = **slug是正の最大レバー** |
| ヘボン表記の流儀差 | maou-sama↔maousama / を=wo↔o / nichijou-kei | 一貫方針を決めれば解消(崩れではない) |
| 真の誤マッチ露見 | まんがサイエンス↔Wagahai wa Robot de Aru | A の FP と同根(少数) |

### ★最大の slug 改善 = カタカナ外来語の英語綴り是正
- **カタカナ主体 title 10,930件、 うち48%(5,299)が種aマッチ有** = 英語綴りを取得でき **slug を正しい元綴りに是正可能**(aama→armor, beruseruku→berserk 型)。
- 残り52%は種a無し → ヘボン fallback(規則通り)。

### slug 衝突 = 4,523群 / 10,648 entry(要対処)
`.cache/slug-proto-collisions.tsv`。 内訳:
- **真の同名異作品**(日本の歴史×31 / 三国志×10 / 源氏物語×13)→ CLAUDE.md の `-姓+年` suffix 規則が必要
- **merge 候補**(まんがグリム童話×11 等の長期巻物)→ 本来 series-merge で統合されるべき分裂
- **★生成バグ**: `daito-comics-tlshiriizu`×21 = imprint ラベル「ダイトーコミックスTLシリーズ」から slug 生成 = title でなく副題/レーベルを拾っている → 要修正
- **誤併合**: `joker`×11 に 女〔女咼〕 等 別字が混入 = 別表記の取り違え

### C から導かれる改善(※提案、 本番未適用)
1. slug 生成を **title_kana_segmented 起点ヘボン**に作り直す(現 display 起点は漢字破綻)
2. **カタカナ外来語は種a english/romaji の元綴りを採用**(5,299件是正可、 音写フィルタで判定)
3. 衝突 4,523群に **`-姓+年` 自動 suffix**(主版=巻数多/古い を無印)
4. 副題/imprint ラベルからの誤生成を除外(daito型バグ)

---

## B. recall(著者経由)実測

ツール: `scripts/_audit-recall-authorroute.py`(改良著者正規化で AniList 著者→作品 index
を作り、 NO_MATCH 種3 を著者経由で再照合)。

改良点(A の発見を反映):
- **romaji↔カタカナ橋渡し**(hepburn_to_kata を著者にも適用 = Boichi↔ボウイチ)
- ひらがな→カタカナ、 NFKC 正規化(異体字の一部吸収)
- **翻訳/制作 role 除外**(Translator/Letterer/Editor/Designer 等を著者集合から外す)

### 結果(著者一致 AND 題一致の二重確認で回収)
- AniList works 101,590 / 著者form index 101,859。

| verdict | 著者有 | 著者経由回収 | 率 |
|---|---|---|---|
| NO_MATCH | 36,349 | **3,815** | 10% |
| **DISPLACED** | 3,221 | **2,622** | **81%** |
| REJECT | 2,225 | 222 | 9% |
| **合計** | | **6,659** | |

- ★**DISPLACED は 81% 回収可能** = 1:1 greedy 割当が「勝てるマッチ」を落としていた裏付け
  (DISPLACED は候補が他に取られただけ=著者+題で確認すれば復活)。 = 最も確実な回収源。
- NO_MATCH サンプル25件精査 → **精度 ~80%**(正20 / 疑3-5)。 誤りは続編→基底の取り違え
  (デビルサバイバー2↔Devil Survivor)、 ドロップ対象のイラスト集 等。
- **副産物**: CLAMP PREMIUM COLLECTION〜 等の **imprint 接頭辞**で題ファースト候補生成が
  失敗していた case を著者経由が回収 = C の `daito` slug バグと同根(接頭辞/レーベル汚染)。

### B から導かれる改善(※提案)
1. **著者経由を v9 に第2経路として追加**: 題ファーストで候補0でも、 同一著者
   (改良正規化)の作品に題が(包含)一致すれば候補化 → +3,000件規模(精度~80%、
   続編/版の tie-break 要)。
2. **著者正規化の改良(romaji↔カナ/role除外)を v9 本体へ**: DISPLACED/REJECT/弱スコア帯の
   偽MISMATCH も同時に減り、 S系全体の信頼度も上がる。
3. **題の接頭辞(レーベル/imprint)除去**: CLAMP PREMIUM COLLECTION / ◯◯コミックス 等を
   正規化で剥がす → 題ファースト候補生成の取りこぼし回収(slug 生成バグとも共通対処)。

### マッチ率の伸びしろ(総括)
- 現状 34,013(44.5%)。 著者経由 **+6,659 回収可能**(うち DISPLACED 2,622 は高精度)。
- 精度ディスカウント込で **+約5,500 solid** → **~39,500(~52%)**。
- 題正規化(imprint接頭辞剥がし)+ popularity tie-break で さらに上積み余地。
- ★重要: いずれも著者+題の二重確認で **精度を保ったままの recall 改善**(水増しでない)。
- ★DISPLACED 81%回収は **1:1 greedy の緩和(著者確認時は複数共有許可)or popularity tie-break**
  で実装でき、 効果/確実性が最も高い → Tier1 候補に格上げ推奨。

---

# 今後の作業推奨(優先順)= 朝の判断用

各項目: 効果 / リスク / 前提 / **承認要否**。 ★=ユーザ最優先(確実なマッチ・正しい slug)に直結。

## Tier 1 = 高効果・低リスク・即着手可

### 1. anilist_id 結線(S180 × 30,617)★
- 内容: S180 マッチの AniList id を 種3 `anilist_id` に **surgical 純粋追加**(en と同手法)。
- 効果: productionization の**土台**(以後 synonyms/genres/popularity 等を id 経由で連結可)。
- リスク: **最小**(ID リンクのみ・上書き無し・可逆)。 A で S180 実FP率<0.3%確認済。
- 承認: en-fill と同じ純粋追加なので**即実行可**(朝 OK ですぐ着手できる)。

### 2. 著者正規化の改良を v9 へ + 著者経由 recall(matcher 改善)★
- 内容: romaji↔カナ橋渡し / 翻訳者 role 除外 / 異体字吸収 を v9 著者照合に入れる。
  さらに「題ファーストで候補0でも同一著者の作品に題一致→候補化」第2経路を追加。
- 効果: **マッチ +約3,000(精度~80%)**、 偽MISMATCH 減で S系全体の信頼度も向上。
  マッチ率 44.5%→~48-49%。
- リスク: 低(種3 不変、 TSV 再生成のみ)。 続編/版の tie-break は要調整。
- 承認: matcher 実験は調査内。 v9 本体差し替えは結果確認後。

## Tier 2 = 高効果・要設計

### 3. slug 生成器を新規実装(title_kana 起点ヘボン + カタカナ英語綴り)★★
- 内容: 現 makeSlug(display→wanakana=漢字破綻)を捨て、 **title_kana_segmented 起点
  ヘボン**で再実装。 カタカナ外来語は **種a english/romaji の元綴り採用**(5,299件是正)。
- 効果: 「正しいフォルダ作成」の**本丸**。 全76,435件に一貫 slug。
- リスク: **slug=フォルダ名は rename 困難**(CLAUDE.md)。 → **本番未生成の今がチャンス**
  (42ページのみ既存)。 既存 slug は alias/redirect 表を残す。
- 承認: **要ユーザ確認**(slug 規則の最終裁定 + 適用 GO)。 まず全件 slug 案を生成して
  レビュー可能な形にする(調査の延長で生成だけ先行可)。

### 4. synonyms / genres_anilist の productionization(S180)
- 内容: en と同 surgical 手法で synonyms・AniList ジャンルを 種3 へ純粋追加。
- 効果: 検索性・ジャンル網羅の向上(箱は実装済)。
- リスク: 低〜中(synonyms 誤りは検索ノイズ)。 anilist_id 結線後が綺麗。
- 承認: 純粋追加。 anilist_id(項目1)の後に。

## Tier 3 = 中効果・仕上げ

### 5. 全件 re-dump 完了 → popularity tie-break
- v3 dump(description/popularity/meanScore)完了後、 同名曖昧・DISPLACED を
  **popularity で裁定**。 DISPLACED 3,298 の一部回収 + 真FP低減。

### 6. slug 衝突 4,523群の `-姓+年` 自動 suffix
- 同名異作品(日本の歴史/三国志/源氏物語)に CLAUDE.md 規則で自動 suffix。
- imprint/レーベル接頭辞からの誤生成(daito 型)除外もここで。

### 7. 真FPガード(パンドラ型)
- 同題+著者が真に別(正規化後)+巻数で確認不可 → 保留/減点。 残存の少数 FP 除去。

## 依存関係(推奨順)
```
1 anilist_id 結線(即) ─┬─→ 4 synonyms/genres ─→ 5 popularity tie-break
2 著者正規化+recall(matcher)─┘                      ↑
3 slug 生成器(要承認)──→ 6 衝突 suffix ───────────┘
                                7 真FPガード(matcher の最終仕上げ)
```

## まず朝イチで決めること(3つ)
1. **項目1(anilist_id 結線)を即実行して良いか**(純粋追加・最低リスク・土台)
2. **項目3(slug 生成器)の slug 規則最終裁定** + 全件 slug 案生成に進んで良いか
3. **項目2(v9 著者正規化改良)を本体反映して良いか**(まず before/after 数値を見てから)

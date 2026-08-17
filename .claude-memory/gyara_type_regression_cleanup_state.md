---
name: gyara_type_regression_cleanup_state
description: ギャラ型(巻×発売日の大逆行)是正。検出器 573→130版まで到達。残122頁は理由つきで gyara-anomalies.tsv に台帳化。トリガー「ギャラ型続けて」
metadata: 
  node_type: memory
  type: project
  originSessionId: 11f90ab9-a3a1-4cd0-b8a8-b5174b421920
  modified: 2026-08-17T07:43:03.509Z
---

**トリガー「ギャラ型続けて」**。全帯を一巡し **573版 → 130版**(122頁)。残りは全部 **理由つきで台帳**にしてある。

## いまの状態(2026-08-17)
- 検出器 = `scripts/_audit-vol-date-regression.py`
- ★**残りの一次ソース = `docs/production-diagnostics/gyara-anomalies.tsv`**
  (years / slug / stem / title / authors / edition / worst_pair / canonical有 / **reason**)
- canonical seed は **589本**。健全性は `scripts/_check-edition-canonical.py` で常時検査

### 残122頁の内訳(reasonごと)
| 理由 | 頁 | どうすべきか |
|---|---|---|
| 自動生成すると本番から巻(ISBN)が消える | 36 | 種2から辿れない版が頁に載っている。種4/別seed由来を人が突合 |
| 種2のrunが1本以下 | 18 | 頁の混線が種2起因でない(別seedが作っている)。seed側を見る |
| 自動生成は通るが検出器がまだ鳴る | 17 | extraタブ側の混在。切り分け粒度を上げる |
| 連載中の可能性(直近18ヶ月に新刊) | 14 | ★canonicalは巻を固定するので使わない。`release-date-override.jsonl` で日付だけ直す |
| 主版候補の中で既に逆行(1 edition内が混成) | 22 | MADB行自体が混成。発売日ギャップで切れないもの |
| 版が14〜31本 | 17 | 手塚/横山クラスの多版頁。人手 |

## 道具(この柱の資産)
- `scripts/_gyara-worksheet.py --min N --max M` = 帯ごとの作業台帳(頁の版タブ構成 + 種2クラスタを1行に)
- `scripts/_check-edition-canonical.py` = canonical seed の番人(後述の罠を全部見る)
- `.cache/gyara/canon.py` = 種2のeditionからcanonicalを組み立てる。版元は**本番66k頁から学習したISBN出版者記号→社名表**(1,629記号)+NDL確認済みレーベル表から解決。引けなければ「不明」
- `.cache/gyara/autofix.py` = 1頁分を全自動で組み立て。**判断が要る形は作らずに理由を返す**
- `.cache/gyara/run_tier.py <worksheet> <tier>` = 帯を丸ごと処理(生成→反映→ISBN差分検証→減っていたら差し戻して台帳に記録)

## 厳守(実踏済みの罠。全部 _check-edition-canonical.py が見る)
- ★**壊れたcanonicalは無警告でskip**される(promoteが`except: continue`)。reflectは成功と表示する
- ★**canonicalは種4(volumes-supplement)を上書きして消す**。NDL裏取り済みの取込もれ巻が黙って落ちる。既存589本を掃引して5頁15巻を検出・4頁復帰済み。残5件(golgo-13/kinpeibai/majima-kun×2/puroresu-super-star-rendetsu)は**種4とcanonicalが別の版のISBNを主張**していて機械的に決められない=人の裁定待ち
- ★**連載中作品にcanonicalを当てるな**(巻が固定され続刊が出ない)。日付1件だけの問題は `release-date-override.jsonl`
- ★**同名レーベルでも巻番号が重なる版は統合するな**。講談社漫画文庫の1990年代版と2001年版のような別セットを束ねると dedup が実在巻をISBNごと潰す(14頁で実踏)
- ★**1 editionの中に年代違いの2runが同居**する。巻番号順に5年以上逆行するrunは発売日ギャップ8年超で切る
- ★**既存seedを再dumpするな**。`compact_edition`/`routing`/`versions` 等の未知キーを落とす(ゴルゴ13で173巻を消して差し戻した)。1巻足すだけなら該当行だけをテキストで挿す
- ★**反映の「消えたISBN N件」は必ず追う**。生成前後で頁のISBN集合を比較するのが確実
- ★**文庫タブの混在は suppress_types:[bunkobon] + bunkobonのextra_editions** でしか直らない
- ★**extra_editions は既存タブを消さない** → 種2側に同じ版が居ると二重タブ
- ★**canonicalのキーは SRC slug(ファイル名)**。検出器が出すのは公開slugなので必ず引き直す(ymlの`slug:`フィールドで逆引き)
- **捏造しない**: 両ソースに無い巻は入れない/欠番は空けたまま/版元が不明なら「不明」と書く

関連: [[edition_canonical_mechanism]] [[never_delete_because_broken]] [[merge_needs_external_proof]]

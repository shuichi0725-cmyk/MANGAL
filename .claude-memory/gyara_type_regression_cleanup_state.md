---
name: gyara_type_regression_cleanup_state
description: ギャラ型(巻×発売日の大逆行)是正。検出器 573→100版。残=gyara-anomalies.tsv(reason: 済/正史/未了を追記済)。トリガー「ギャラ型続けて」
metadata: 
  node_type: memory
  type: project
  originSessionId: 11f90ab9-a3a1-4cd0-b8a8-b5174b421920
  modified: 2026-08-17T08:37:04.216Z
---

**トリガー「ギャラ型続けて」**。全帯一巡(Opus)で 573→130版、仕上げラウンド(Fable 2026-08-17)で ring17全消化→115版、種2外seed起因クラス14件+ムダヅモPoJ新頁分離で **→100版**(未了4件=NDL要: 俺の剣道/そして子連れ狼/新々上ってなンボ/嫌韓流=ledgerに理由つき)。残りは全部 **理由つきで台帳**にしてある。

## ★仕上げラウンド済(2026-08-17 Fable): ring17クラス全消化+三国恋戦記
- 「自動生成は通るが鳴る」17頁を全裁定: 俊平(初版YMKC全11巻復元・4run完備)/オールド・ボーイ/AKIRA(架空27巻main修理+volume-exclude誤同定645057撤回+アニメコミック2種除去)/日本沈没(小説カッパ・ノベルス除去)/SWAN(МC全21巻再建+completed1981)/クイーンエメラルダス/タンク・タンクロー(1935初版)/ピカドンくん/ふしぎな少年(連載年1961-62)/てんとう虫の歌/0課の女/保健室のオバさん(架空ワイド2タブ解消)/光る風/花も嵐も(別作品1956断片除去)/EDEN千之ナイフ(**5作品混線・遠藤EDEN18巻の頁間ISBN重複解消**)/永遠の野原=**正史(許容)**確定(ワイド1-2巻の1995後追い=NDLレーベル番号#363/364)
- 三国恋戦記=頁実体がとこしえの華墨と確定→ **rename**(sangoku-rensenki-tokoshie-no-kaboku)+オトメの兵法!頁へv5返却・ISBN重複×4解消
- ★promote恒久修正2件: build_ymlのedition-overrides参照に公開slug変換(3412と同じ罠の別現場) / volume-exclude枝の無条件年再計算にoverrides年・status-corrガード(連載年が踏まれる)

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

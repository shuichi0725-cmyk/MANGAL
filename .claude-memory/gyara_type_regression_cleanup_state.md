---
name: gyara_type_regression_cleanup_state
description: ギャラ型(巻×発売日の大逆行)是正=★完遂(573→3版=99.5%)。残3=意図的保留(バカボン刷日付/永遠の野原=正史/G・defend=完結後)。月次=検出器の新規増加を見る
metadata: 
  node_type: memory
  type: project
  originSessionId: 11f90ab9-a3a1-4cd0-b8a8-b5174b421920
  modified: 2026-09-03T23:56:32.728Z
---

**トリガー「ギャラ型続けて」**。全帯一巡(Opus)で 573→130版、仕上げラウンド(Fable 2026-08-17)で ring17全消化→115版、種2外seed起因クラス14件+ムダヅモPoJ新頁分離で→100版、「ISBN消える」クラス33頁+ふくふくNEW新頁分離で→67版、round3(行内混成+単発日付誤り32頁+新・駅弁新頁)で→36版、**round4(怪物クラス14頁)で→20版、**round5(手塚6頁: アトム/リボン/どろろ/シュマリ/BJ/三つ目)で →10版**(2026-08-17)。★手塚頁=全集タブ(extra-editions.yml)はcanonical適用後に再付与されるので共存OK(6頁で実証)。★DA attachの罠: 帯違いの新装ISBNが原版日付に誤添付される(BJで実踏)→同一帯の刷ISBNだけ添付し別帯は版タブへ。残=源氏物語3頁(作画者別の教育系分離=NDL要)/NDL要4(嫌韓流v1・そして子連れ狼・新々・さすらい文庫)/人狼ゲーム(頁分割)/欲望パンドラ/G・defend(連載中BL76版)/正史1。残りは全部 **理由つきで台帳**にしてある。

## ★仕上げラウンド済(2026-08-17 Fable): ring17クラス全消化+三国恋戦記
- 「自動生成は通るが鳴る」17頁を全裁定: 俊平(初版YMKC全11巻復元・4run完備)/オールド・ボーイ/AKIRA(架空27巻main修理+volume-exclude誤同定645057撤回+アニメコミック2種除去)/日本沈没(小説カッパ・ノベルス除去)/SWAN(МC全21巻再建+completed1981)/クイーンエメラルダス/タンク・タンクロー(1935初版)/ピカドンくん/ふしぎな少年(連載年1961-62)/てんとう虫の歌/0課の女/保健室のオバさん(架空ワイド2タブ解消)/光る風/花も嵐も(別作品1956断片除去)/EDEN千之ナイフ(**5作品混線・遠藤EDEN18巻の頁間ISBN重複解消**)/永遠の野原=**正史(許容)**確定(ワイド1-2巻の1995後追い=NDLレーベル番号#363/364)
- 三国恋戦記=頁実体がとこしえの華墨と確定→ **rename**(sangoku-rensenki-tokoshie-no-kaboku)+オトメの兵法!頁へv5返却・ISBN重複×4解消
- ★promote恒久修正2件: build_ymlのedition-overrides参照に公開slug変換(3412と同じ罠の別現場) / volume-exclude枝の無条件年再計算にoverrides年・status-corrガード(連載年が踏まれる)

## ★ISBN消えるクラス済(2026-08-17 Fable): 33頁+新頁1で100→67版
- 型=頁の孤児ISBN(種4/harvest由来)をcanonicalが消すため自動生成不可だった層。**楽天全量資産(isbn-title-map+rakuten-isbn.jsonl)の題名逆引き**で孤児を裁定し、canonicalに明示組込して解決
- 全巻復元: GOLD(YKC全16巻)/だめんず(SPA!20+文庫15)/愉快な話(田島みるく版10)/さすらいのギャンブラー(よみうり10)/真・異種格闘(10)/修羅の門弐門(月マガKC18)/女喰い(10)/Sleeping beauty(オークラ4)
- 続編分離の新頁: **ふくふくふにゃーんNEW**(全8巻2005-13、PoJ型=stub+canonical+overrides(anilist:false)+status)
- 発見済の型: ①後年新装はISBN連番ブロックで見抜く(1987アリエス/1998物陰/2002ラブパック文庫/1995巨人の星文庫/2000紫電改文庫→別タブ) ②KC1990紫電改=楽天題で「豪華愛蔵版」判明 ③種4誤配(浅見光彦v20=傑作選)を除去 ④コンビニ判退場: スーパーワイド/Coins/YKベスト/プラチナ/マイパル/MFB/KPC/remix/ATCW/MOOK/Gコミ/テレビまんがえほん
- ★罠: scratchpadのbuilder(build_wave1.py)はimportでも全再生成=手Edit後にimportすると上書きで戻る(実踏)。手直しはbuilder側に反映するか再Edit
- 未了持ち越し: サスケ(1960年代run混線=NDL要)/魔界転生×2頁(とみ新蔵vs石川賢が同一内容=franchise分離要)/さすらい文庫v1・バカボンKC原版の刷日付(NDL要)

## ★round3済(2026-08-17 Fable): 行内混成+単発日付誤り 32頁で67→36版
- 型: 早い巻の枠に新装/別シリーズ/最新刊のISBN・日付が座り後続が逆行扱いになる層。逆行点×楽天突合で裁定
- ★連載中頁の枠復元の型(canonical禁止でも直せる): ①占有行の正体が別series & 真巻が種2既在→**volume-exclude1行**(リコリス/動物のおしゃべり+) ②真巻が種2に無い→**種4追加**(dedup最古勝ちで占有行が自然退場: 文鳥様あおばv1-3/act2真v1/再召喚v1) ③ISBN正・日付だけ誤→release-date-override(あひるの空v27=年typo)
- franchise是正: 魔界転生=とみ新蔵版(SP2002-03全6冊=魔/界/転/生/魔界/転生之巻)と石川賢版(角川1996)に分離(2頁が同一内容だった)/駅弁ひとり旅=原版v1-17復元+続編『新・駅弁』新頁(shin-ekiben-hitoritabi・連載中=**次巻は手動top-up要**)/ドカベン プロ野球編=SCC v1-52復元
- ★罠: 過去のpage-dedup entry(2026-07-07)が新設slugを無言でdrop(dedup_skip=1)→page-dedup.ymlから除去して復活(新・駅弁で実踏)
- 未了: 人狼ゲーム(本編/ビーストサイド/CF/ロスト・エデン4作が1頁混在=頁分割要)/欲望パンドラ(v1原版不明)

## ★round6済=最終(2026-08-17 Fable): NDL裁定で10→3版・ギャラ型ほぼ完遂
- NDL SRU(1.3秒/req)で楽天の届かない層を裁定: 嫌韓流v1(9784883804788 2005-09)/そして子連れ狼=刃コミックス(小池書院2007-09)v1-4/さすらい奇想天外文庫v1=初版1976-01(1981-12-01は文庫280再刊日)/俺の剣道初版=リイド社SPコミックス全20巻/沼田水滸伝=中国歴史コミック巻4-10(v3の1980断片=真崎守×久保田・学研グローバルと判明=別作画タブ)
- ★NDLの欠字ISBN復元の型: 「48622531949」(11桁)/「9784962254108」(1字化け)→チェックデジット検算+帯連番一致で確定(そして子連れ狼v3/v4)
- 人狼ゲーム4頁分割: 本編(v1+v3、v2は両ソース無)/ビーストサイド全3/クレイジーフォックス全4/ロスト・エデン3巻(作画=麗太朗をoverrides authorsで是正)
- 源氏物語×3=各作画者の実書誌だけに絞る(1982コミグラフィック断片=どの頁にも帰属不能で不収載)
- 欲望パンドラ=NOiPA再刊v1をexclude(MeDu原版v1は種2既在)
- ★残3版(意図的保留): バカボンKC刷日付6年(NDL per-vol要=費用対効果低)/永遠の野原(正史)/G・defend(連載中、新装v1-36と旧版同居=完結後にcanonical化)
- 以後は月次サニティで検出器の新規増加分だけ見る

## ★後日判明した一括是正の副作用(2026-09-03 Sugar&Spice型の見送り群から)
- 8/17一括の「巻数が最も多く最も古い run を主版」規則は、**原版が種2に断片しか無い頁で再刊を主版に据える**: 幸せの時間(2012新装版9巻が主版、原版1997-2001全19巻は1-5・7の断片が別版に散っていた)/第三の極道/タコポン/新・ぴーひょろ一家(2003-05再刊が主版)。楽天キャッシュ(検出器TSVのOTHER_ISBN行=同番号別ISBN)に原版が揃っていたので主版に組み直した。
- 同型の override 版: 「再刊1冊(文庫/SV/新装)を通常版1巻」にした override が9頁(赤い糸の伝説/エーイ!剣道/エクレア気分/Mickey/身から出た鯖/ロスマリンの伝説/闇鍵師/夕陽よ昇れ!!/地球ナンバーV7)→ override の editions/年を外し canonical へ。
- ★検出の型: canonical で **extra_editions の最古日付 < 主版の最古日付** なら「再刊が主版」の疑い(機械で引ける。未検出器化)。日付逆行の見送り理由 D+F はこの型の入口。
- ★罠2件: canonical に文庫 extra を足すなら `suppress_types: [bunkobon]`(種2由来の文庫タブと同ISBNで二重化) / 版を1本に統合すると reflect の減少ゲートが版数減で止まる→意図確認のうえ `--allow-loss`。

## いまの状態(2026-08-17)
- 検出器 = `scripts/_audit-vol-date-regression.py`
- ★**残りの一次ソース = `docs/production-diagnostics/gyara-anomalies.tsv`**
  (years / slug / stem / title / authors / edition / worst_pair / canonical有 / **reason**)
- canonical seed は **589本**。健全性は `scripts/_check-edition-canonical.py` で常時検査

### 残の内訳(2026-08-17時点=67版。reasonは台帳が正)
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

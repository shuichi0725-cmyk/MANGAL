---
name: volgap_fill_pipeline_2026_09
description: 【機構・再利用】巻抜けを「ローカル楽天種→NDL→under-merge結線」の3段で埋めるパイプライン。決定打はISBN連番ゲート
metadata: 
  node_type: memory
  type: project
  originSessionId: a6e17d72-d62d-4a2e-a121-36a8fd75a363
  modified: 2026-09-06T15:52:15.957Z
---

2026-09-07 ユーザ指示「ローカルの楽天で巻抜けが補完できる物があるか一つずつ調べて修正して。無ければndl」。
468頁 → **408頁**(旧模型)/実測 430頁(版単位是正後)まで詰めた。**128巻を補完**(楽天58+NDL46+under-merge24)。

## 道具(この順に回す)
1. `scripts/_volgap-gap-targets.py` — 残gap頁 → 「どの版の何巻を埋めるか」の表。
   ★**版(edition)単位**で穴を取る + 先頭欠け(LEAD)も出す + **経路**を判定
   (`seed4` / `canon:volumes` / `canon:compact` / `canon:extra[i]` / `overrides`)。
   ★canonical結線頁は promote が最後に editions を丸ごと置換するので**種4に書いても出ない**
   = canonical本体に書く。 edition-overrides に editions を持つ頁も同じ。
2. `scripts/_volgap-local-fill-v2.py` — 楽天ローカル種(delta 828MB + old 373MB = 818,420item)を1パス。
   題variant(ルビ括弧を落とす)で引く。 旧 `_volgap-rakuten-local-fill.py` は先頭欠けを扱えず
   751巻を取りこぼしていた。
3. `scripts/_volgap-ndl-harvest2.py` → `_volgap-ndl-match.py` — 楽天で埋まらない頁をNDL SRUで収穫
   (354頁・11分・5,546レコード)。 ISBN10→13変換 / 「第N巻」「題. N」の巻抽出 / 和暦・[年]の日付解釈。
4. `scripts/_volgap-adjudicate.py` — 追加ゲートを当てて APPLY/HOLD/DROP を決める(共通)。
5. `scripts/_volgap-exists-split.py` → `_volgap-undermerge-fill.py` — EXISTS層の仕分けと第3段。
6. `scripts/_volgap-apply-fill.py` — 種4 / canonical へ純粋追加(可逆backup + changelog)。

## ★ゲート(効いた順)
- **G5 ISBN連番 = 決定打**。 `前巻ISBN < 候補 < 次巻ISBN`(先頭欠けは `< 次巻`)。
  版元prefixだけでは落とせない **同じ社の別レーベル**(プレミア=文庫版ISBNが通常版の穴に来た)と
  **別年代版**(復讐の兇獣=1982年版 / ハード&ルーズ=原版のISBN)を機械で落とす。
  逆に、日付ゲートが外れても連番が通れば採る(熱笑!!花沢高校 トクマ版= 820115→820122→820139→820207)。
- G1 既存ISBN(本番索引+種2) / G2 版元prefix / G3 発売日 / G4 著者
- G6 版元名一致(頁の版元が判る時だけ。 片側「不明」は判定不能=保留)
- G7 同じISBNが複数の版に提案 → 証拠の多い方だけ採る
- G8/G8b/G8c 同じ頁の別版との二重化防止 → [[volgap_edition_split_double_add]]


## ★2026-09-10: 「1冊だけ欠け」層は NDL では枯れた

残343頁のうち**欠番1個=179頁**を NDL で全数照合した実測:
```
ACCEPT 0 / REVIEW 0 / REJECT_EDITION 1 / EXISTS 6 / NOHIT 162(138頁)
```
**新規に採れる巻はゼロ**。1980年代以前・小出版社が多く、NDLに一次資料が無い層。
★**「NDLで調べれば埋まる」と再提案しない**。次に動かすなら Wikipedia / 出版社公式 / JPRO、
あるいは「ISBN以前は数えない」等の裁定見直し([[volgap_skip_isbnless_edition]] の拡張)。

★**EXISTS は「直せる印」ではない**。6件を個別に割ったら本物は2件だけで、
4件は**別版/別作品のISBN**だった(唇役主丞乾いて候=deluxe版5巻 / 椰=講談社KCデラックス3巻 /
聖=2016新装版3巻 / 人狼ゲーム=別作品クレイジーフォックス2巻)。ゲートが正しく弾いていた。
私は一度「6件直せます」と誤報した = [[feedback_raw_count_is_not_worklist]] の再演。

## 数字の読み方(2026-09-07 実測)
- ターゲット 1,718巻/468頁。 内訳= **NOHIT 1,272巻/307頁**(楽天ローカルにもNDLにも無い)/
  **EXISTS 251巻/107頁**(自前DBに在る=under-merge)/ ACCEPT 94 / REJECT_EDITION 53 / REVIEW 48。
- ★**楽天ローカル種は全網羅ではない**: NOHIT 354頁のうち 210頁は「その題の本が1冊も無い」。
  著者ハーベスト由来(2026-06-27)なので旧作・ニッチ作が丸ごと落ちている。
- ★**巻抜けの主因は取込もれでない**([[volgap_mostly_undermerge]] の再確認)。 埋まったのは1割弱。

## 残り(次の手)
- NOHIT 1,272巻/307頁 = 楽天live / Wikipedia / JPRO が次の情報源
- EXISTS の A2(自頁に別番号で在る)103巻/43頁・B1(別頁同題=頁分裂)48巻/15頁 は
  **番号付け直し / 頁統合**の領域で、巻を足す仕事ではない
- 表 = `docs/production-diagnostics/volgap-apply*.tsv` / `volgap-exists-split.tsv`

[[volgap_diagnosis_order]] [[volgap_virtual_tool_trigger]] [[harvest_match_mechanism_applied]]
[[ndl_volume_completion_better_than_rakuten]] [[feedback_efficiency_first]]

## ★2026-09-21: 楽天live を当てた結果(MID=効く / LEAD=枯れ)

**MID層(途中の欠番)** = 楽天live収穫 → 照合 → ISBN連番+発売日+著者+G5ラノベ除け で
**13巻を充填**(鬼太郎1985年版10-13 / 江戸前の旬134 / ヘタリアGangsta2 / ニシトーキョー2 / 帝都2 /
まんがプロジェクトX 9・10 / Double call 2・3 / オーイ!!やまびこ5)。
日付矛盾の3巻(学研まんが世界の歴史#4#5#9)はユーザ条件どおりHOLD。

★**反例として重要**: 鬼太郎1985年版は前日「NDL・Wikipedia・種2のどれにも無く連番推測もできない」と
結論した層だったが、**楽天liveには在った**。「無い」と言う前にソースを1つずつ潰すこと
([[feedback_absence_needs_verification]])。

**LEAD層(1巻が無い)** = 869巻/282頁を楽天live+NDLで全数照合 → **ACCEPT 0**
(REJECT_EDITION 15 / EXISTS 58=26頁 / NOHIT 786=250頁)。
= 上の「NDLでは枯れた」に加えて **楽天liveでも枯れた**。
★**1巻欠け層に『楽天で拾えないか』を再提案しない**。残るのは JPRO / Wikipedia / 出版社公式 か、
「ISBN以前は数えない」の裁定拡張。

**穴1冊だけ層の機械分類**(180頁 → `docs/production-diagnostics/volgap-onehole-class.tsv`):
C 自前DBに無い160 / B' 種2に在るが別頁に出ている17 / B 種2に在るのに出ていない3。
B の3件を個別検証したら **2件が本物・1件(人狼ゲーム)は別作品**(クレイジーフォックス)= EXISTS の偽陽性は再現する。

巻抜け推移(2026-09-21): 月次前346 → 蒸留後341 → per-case+楽天live → **330**


## ★2026-09-23 訂正: 「1巻欠け層は楽天でも枯れた」は**題名の揺れで検索を外していただけ**の部分がある
ユーザ仮説「1冊だけの頁は、そもそも1冊の作品では?」を、「1巻が無い」97頁のうち1冊だけの**38頁**で検証した。
→ **仮説は外れ(0件)**。38冊とも本の題に「2」「第2巻」「vol.2」「続」「下」が付いた、本当に2冊目だった。代わりに次がわかった
(表 = `docs/production-diagnostics/vol_gap_lead1_single_book_2026-09-23.tsv`):
- **A 割れ 15**: 1巻が MANGAL の**別の頁**に載っている(グラン・**バカン**2 ↔ **バガン**1 / かるってと2 ↔ かるてっと / LA VIE EN ROSE 2 ↔ **LOSE** 1 /
  エスカレーション1 ↔ たかまり指数エスカレーション2 …)。MADB が巻ごとに題を揺らして登録した型。★かるってと=**同じISBNが2頁**(重複頁)。
- **B 取込もれ 12**: 1巻の ISBN が判明したのに、どの頁にも無い。★うち5件は**楽天liveで普通に出た**(奥さま火の用心1〜5・死ぬほどキスして1〜4 など)。
  頁の題「奥**様**火の用心!」で引いて外し、楽天の題「奥**さま**火の用心」で当たった = 9月の LEAD 全数照合 ACCEPT 0 の一因は**検索語の揺れ**。
- C ISBN以前の1巻 2 / D 見つからず 9(真夜中のラブレター=上下巻の下、など)。
★手法: MADB元記録(`.cache/madb/metadata101-clean.json` は json.load で**6秒**)の巻欄+同名/同叢書の兄弟 → ISBN頁索引 → NDL `--creator` → 楽天 `--title`(頁の題でなく**MADB/NDLの題**で引く)。
★`_lookup.py` の楽天題検索は ISBN を表示していなかった → 先頭に出すよう是正(同日)。
残り59頁(2巻以降が複数冊の「1巻が無い」頁)は未調査。
**★是正結果(2026-09-23 ユーザ「可能な限り修正して」)**: 38頁中 **22頁を是正**(commit 0af096b97)。
統合12組(series-merge + page-dedup + slug-aliases + prune台帳)+ 重複削除1(かるってと)+ 巻追加16冊(種4 15 + 愛=edition-overrides)。
巻抜け 346→**324**、「1巻が無い」167→**145**。書影は16冊とも楽天に無し(90年代本)。
見送り = 天保銭(多版+日付疑い)/ぐうたらママ(ISBN付け違い)/宮沢賢治・漫画館(版混在)/大長編ドラエもん1984(ISBN誤り)/
ビーパル小僧(巻ごと作画者違い)/ ISBN以前の1巻2件(裁定どおり触らない)/ 見つからず9。
★湘南グラフィティ = 種2の1巻が**同typeの別版(ダイト)の1巻に番号で隠されていた** → `separate_editions: imprint` で解消(銀河鉄道999の型)。
★統合のホストは「正しい題の頁」を選ぶ(LA VIE EN **LOSE** 側は吸収)。自動統合(series-merge-auto.json)の既存entryがある作品は、そのキーも全部含めて書く。

## ★2026-11-01 見直し: 残り314頁のうち **81頁は直せば閉じる**(ユーザ予想「新しい物以外ほぼ直せない」は外れ)
ユーザ指示「改めて調査してみて」。表 = `docs/production-diagnostics/volgap-reinvestigate-2026-11-01.tsv`(生成器 `scripts/_volgap-reinvestigate-table.py`)。
- 取込もれ25(楽天/NDLでISBN確認)/ 紛れ込み1 / **1巻だけ副題付き別登録21** / **版タブ割れ10** / **頁分裂21** / 版元移籍1 / 掲載対象外の頁2。
  判断が要る35(アンソロジー20・作画者違い/日付矛盾/番号付け直し15)、一部だけ6、直せない192(どの情報源にも無い141=8割が1980〜2000年代)。
- ★**旧照合は楽天の題に副題が付く本を全部捨てていた**(G0「残差題==頁題」)。世界最強の魔女〜私だけ『攻略サイト』を…〜(6) / INOZ -55歳から…-(2) /
  熱中!コボちゃん10 おいしいお使い編 / ピットスポルム 二葉 / 邦キチ!映子さん Season14。**9月の live 収穫に本は入っていた**のに照合で落ちた。
  → `scripts/_volgap-subtitle-match.py`(楽天の題が頁題で**始まれば**よい+巻は残りから1つだけ読めれば採る+著者/版元/ISBN連番/日付/本番不在/1欠番1候補)。
  上の「1巻欠け層は楽天でも枯れた」は**この照合の穴で言い過ぎ**だった。
- ★**1巻だけ副題付きで別登録**(TL/BL・ぶんか社/宙出版/大都社に多い): MADB の1巻が「題 : 副題」+巻番号なし→種2で別series→孤児で**どこにも出ない**。
  `scripts/_volgap-madb-siblings.py`(同著者+同叢書/版元+題が似る+欠番の巻番号)で引く。★MADB の ISBN は10桁が混じる=13桁化必須(しないと全部「どこにも無い」に見える)。
- ★**版タブ割れ**: 月刊少年マガジン作品で MADB の叢書が途中から「講談社コミックスデラックス. 月刊少年マガジン」になり deluxe タブへ割れる(世界最強の魔女・追放されたチート付与魔術師)。
  集英社の「通常版」と「ユーコミックスデラックス」も同じ刊行の割れ(ぽっかぽか・シッポがともだち = ISBNの並びで判る)。
- ★**版元のISBN記号が変わると G2 で落ちる**: ヒーローズ(978-4-86468→86805・旧発売元 小学館クリエイティブ)/ TOブックス(86699→86794)/ 白夜書房→ガイドワークス。
- 紛れ込み = ティンカー・ベル3巻 = 「山岸凉子短篇ベストコレクション3」(楽天予約ハーベスト①が題の前方一致で付けた)。予約ハーベスト2,046件を同じ型で洗って**この1件だけ**。
- ★**2026-11-01 是正済(ユーザ「1終わった2やって」)= 78頁を直し 314→235**(push 53fb88cdb7 / 9f14a455fb・本番は次の週次)。
  手順1(47頁)= `_volgap-apply-fill.py --in .cache/volgap-apply-20261101.json`(65冊)+書影14 / 手順2(31頁)= canonical 5本のタブ統合・merge_edition_types 4件・
  シッポがともだち=edition-overrides・頁分裂19組 series-merge+page-dedup+slug-aliases・重複頁2。
  **残り(未着手)**: アンソロジー20頁(埋める/頁ごと外すの裁定待ち)・判断要15・一部だけ6。
- 直す途中で出た型(各1回):
  ・vol0-first(番号0→1巻)が『ピットスポルム 二葉/三葉』を**1巻として種4に入れていた**(漢数字の巻表記を読めない)。48件中この2件だけ。
  ・volume-exclude に**ISBN記号の切替を別出版社と誤判定した除外**(新日本人物史 907150→909064・2026-06-29)。外すと台帳減少で seed lint が止める
    → `_check-seeds.py --allow-shrink volume-exclude.yml` → seed を先に commit → 反映。
  ・ぽっかぽか通常版1巻=『ちいさな絵本』(非漫画)/シッポがともだち通常版1巻=文庫 vol.1 = 種2の型割れに別の本が混じる。
  ・canonical 結線頁(プレミア)は series-merge しても canonical の巻で上書き → 吸収した巻は canonical 本体へ書く。
  ・page-dedup の drop は SRC slug(=manga.v2ファイル名)。8/5 に統合を決めた 新耳袋 怪談百物語 は page-dedup が無くフルpromoteで復活していた。
  ・volume-exclude は頁単位でISBNごと消す = 版の付け替えには使えない(シッポがともだちは overrides)。

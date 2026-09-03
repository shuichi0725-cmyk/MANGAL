---
name: subtitle-orphan-volume-split-sugar-spice
description: 【型・検出器あり・3段適用済 2026-09-03】Sugar&Spice型=巻題を題としてMADBが単独登録→種2別sid→本編頁から末尾巻が欠ける。_audit-subtitle-orphan-volume.py で全DB掃引→override固定頁4/別sid195巻/取込もれ643巻を適用。残=REVIEW一覧(レーベル和英表記違い等)
metadata: 
  node_type: memory
  type: project
  originSessionId: f8fa63b4-3ce7-45e1-b2ab-f3f4fbab02f4
  modified: 2026-09-03T09:56:27.842Z
---

**型 (2026-09-03 ユーザ発見 sugar-spice)**: 各巻に固有の巻題を持つシリーズ(Sugar & Spice=全巻ジャズ標準曲題)で、MADBが
17/19/20巻を巻題「Somethin' stupid」等を**題として**別MADB-IDで登録し、種2のクラスタキー(著者+題)が別sid(number=0/1,
is_extra=1)に落とした。本編頁は「17巻欠け+18巻で終わり」に見えた(完結・全20巻)。是正=種4結線+4巻の後刷り日付是正。

**検出器 = `scripts/_audit-subtitle-orphan-volume.py`**(楽天キャッシュ1パス24秒。CLAUDE.md月次サニティ登録済):
副題/題の「親題+巻番号」→既存頁と照合→本番に無いISBNを 巻状態×種2(SPLIT/SAME_SID/ABSENT)×tier×一致×疑 で列挙。
第2部= edition-overrides(editions固定)頁の続巻取りこぼし(種2駆動)。

**2026-09-03 ユーザ「1から順番にやって」で3段を適用**:
1. 第2部(override固定): フェルマーの料理8/聖女に嘘は通じない6/壁抜けバグ12/狼男だよ2 を override に追記。
   見送り= 魔法科2頁(実体はよんこま編4-7=step2で別頁へ)/うちの3姉妹17-19(傑作選=除外が正)/嶋二(同人誌選集)/花警察・鬼太郎(多版別件)。
2. SPLIT(別sidに眠る): 機械証拠(版種keep/レーベル一致/発売日順/出版者記号一致/題完全一致)でAUTO162+手動採択→**195巻を種4で62頁へ**。
   ★同クラスタ掃引を追加(採択sidの兄弟巻で楽天キャッシュに無かったもの=CODE:BREAKER 15-26 は19だけ楽天に在った)。
   ★頁化済み変種: 特別編1巻『ハニー・ヴァイオレット』/2巻『レコンキスタ』が単巻頁で存在→種4で特別編1-7を揃え page-dedup drop→301。
   ★くらべて、けみして: 種2が新潮文庫1巻を通常版number=1で登録→原本1巻が同番号ガードで弾かれ、override で通常版1-2/文庫1に分離。
   見送り= 0巻(cluster)/文庫だけの頁に原版1冊(fanshii-dance)/プリキュア版混在/将太の寿司18(原シリーズ巻)/アニメKC/supo-chan(旧キャッシュ誤記録)。
3. ABSENT(真の取込もれ): 6ゲート(standard版/レーベル整合/発売日順/同番号無し/ISBN未在/bind/override・canonical外)で
   **AUTO 643巻/413頁 → volumes-supplement-auto.yml (source: rakuten-title-tail)**。REVIEW 516巻/325頁は
   `docs/production-diagnostics/subtitle-orphan-volume-review.tsv`(理由列つき。最多=レーベル和英表記違い416=alias表で救える)。

**判定の学び**: ①出版者記号は桁数表(2〜7桁)で切る(先頭7桁固定はKADOKAWA/講談社で題番号を巻き込み別社扱い) ②楽天の旧キャッシュ
(rakuten-isbn.jsonl)は誤記録あり=delta優先 ③種2の版種は当てにならない(新潮文庫がstandard) ④SAME_SIDの内訳=真の0巻(表示方針
マター)/page-dedup残骸/override固定/MADB誤番号 ⑤override が editions を持たなければ種4は効く(is-2010は題だけのoverride)。

**4段目(同日「524巻、見送り理由つきを確認して」)**: レーベル別名を**経験表**で解いた= 同一ISBNを種2 imprint と楽天 seriesName が
別名で呼ぶペアを全DBで数え(8,388ペア、sid≥3の強ペア1,916。actioncomics⇔アクション/bamboocomics⇔バンブー/kiraramenu⇔まんがタイムKR…)、
対象版の既存巻の楽天seriesName一致(自頁証拠)も可。日付比較は「日付を持つ巻」基準に修正(最終巻が無日付で誤逆行していた)。
→ **371巻/236頁を追加**(rakuten-title-tail)。override固定4巻は手で追記(ジェノサイド2/下駄を履くまで2/ピン!ピン!ピン!新装版2-3)。
**残153巻**(理由つき `subtitle-orphan-volume-review.tsv`): 日付逆行55(頁側が新装/後刷り日付=版の付け直しが要る per-case)、
canonical/override固定の複合41(第三の極道11/幸せの時間13-19/Eden3-5 は canonical の run 再構築が要る)、G1 版なし13(頁の巻が全部
number=0 の頁)、真のレーベル違い17(花の慶次19-21=Bunch world新潮社版/悪魔くん千年王国=KCスペシャル等=別版で却下が正)、step2見送り8。
★alias表は scratchpad 生成物(label_alias.py)で seed 化していない=次回は検出器に組み込む価値あり。
★銀魂3年Z組銀八先生 の候補2巻は JUMP j BOOKS(小説)= 正しく却下。検出器の DROPIMPRINT に j books/文庫/ノベル を追加済。
**5段目(同日「進めて」)**: 判定を **`scripts/_apply-subtitle-orphan-volume.py`** に正式化(検出器が別名表を `.cache/label-alias-pairs.json` に
同時生成→apply がゲート→種4-auto→stems)。CLAUDE.md登録済。日付逆行55巻を検分した結論: **頁側の後刷り日付は1件だけ**
(セイシュンの食卓3巻 MADB 1991-05→楽天 1989-11-01+ISBN序列で override)。大半は頁が**新装版/ポケットワイド/スペシャル版/合本**
(SP pocket wide=リイド社の廉価再刊、バーズコミックススペシャル版 上下、新装合本版…)しか持たず、候補=原版の続巻という**版の欠落**
=版分離案件(edition-canonical/extra-editions)。ラベル一致の取り違え2型を是正: 'yk'⊂'ykコミックデラックス'(短い包含)、
'ホラーm'⊂'ホラーmコミック文庫'(文庫版に吸われる)→ 包含はstandard版のみ・4字以上。1か月許容(奥付月vs発売日)で3巻救済。
残194巻(SAME_SID56含む)。ドラえもん0巻はユーザ裁定で表示(override直書き+year 1974-1996明示)。

**6段目(同日「原版が欠けている頁の版分離進めて」)**: 日付逆行群の**頁側が再刊しか持たない**型を edition-canonical で
「原版run=主版 / 再刊=別版タブ(shinsoban/wideban)」に分離、**20頁**(scratchpad/split_canonical.py の SPEC から生成)。
材料= 検出器TSVの全候補(OTHER_ISBN含む=原版1..Nが揃う)+種2の不可視巻(同番号で負けた再刊/単発)+NDL作者束縛検索で全巻数確認。
★NDLで原版が更に古いと判明した例: 柳生十兵衛死す(頁=リイド社2015ポケットワイド→SPコミックス2008も再刊→**原版は集英社YJC BJ全5巻2001-02**)、
水滸伝さいとう版(1996 世界文化社Sebun 巻ノ1-3 を別版で復元)、なぎら健壱バチ当たりの昼間酒(本編=思い出食堂コミックス その1-5、頁は
ぐる漫特別編集1冊だけ)。球道くん=原版マンガくんコミックス/少年ビッグコミックス全20巻(MADBはSV再刊ISBNに原版日付を付けていた)。
★canonical で release_date 不明の巻は `null`(空文字はreflect検証ゲートNG)。extra_editions は type 明示(既定は kanzenban)。
見送り= 独眼竜伊達政宗/太陽が呼んでいる/紅丸ぼたん(原版1巻がNDL・楽天のどちらにも無い)、日付空の末尾8巻(未発売か楽天未登録=日次蒸留の予約ハーベスト待ち)。

**7段目(同日「真のレーベル違い20巻と0巻は全部漫画なら出してok」)**: 0巻= **`data/seeds/vol0-show.yml`**(opt-in、promote `get_vol0_show()` を新設。
13作: ハヤテ/花子くん/ジュン/彼女のカレラRS/ケンガンアシュラ/KIMURA/禁猟六区/KOBAN/政宗くん/松田優作物語/パラダイスレジデンス/そろえてちょうだい?/ラインバレル)
+別sidの0巻3作(東京トイボックス/蜜談/CLUSTER)は種4 number=0。SAME_SIDの正体は3型= 真の0巻 / **page-dedup残骸**(落とした頁のsidが
本編に結線されない: Bird/ホヒンダ村/Ψchic/Wジュリエット2 → series-merge.yml merge_keys で結線) / **MADB誤番号**(number=0/1 extra=1: 熱中!コボちゃん6-14等 → 種4)。
レーベル違い18巻は種4 standard(同社後継レーベル/表記違い/移籍)、花の慶次 Bunch world版(新潮社 全21巻)は extra-editions の版タブ。
非漫画として除外= スマグラー+4(プラチナコミックス=コンビニ)/あずきちゃんメディアブックス(アニメ)/ガンダムSEEDアニメKC(フィルムコミック)/おまもりひまり0(ガイドブック)。
合計 47頁反映(commit 42a0e8749)。

**次**: canonical頁(第三の極道/幸せの時間/Eden)のrun再構築、原版1巻が見つからない3頁(独眼竜/太陽が呼んでいる/紅丸ぼたん)。
[[volume_split_merge]] [[series_fragmentation_rootcause]] [[feedback_one_bug_means_a_class]] [[harvest_match_mechanism_applied]]

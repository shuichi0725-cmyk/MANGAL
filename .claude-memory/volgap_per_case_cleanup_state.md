---
name: volgap_per_case_cleanup_state
description: 【進行中・最重要】巻抜け1417の本番前per-case仕上げ。誤マッチ/奇子型162/単純抜け1050。NDL土台+楽天harvest+Wikiで一個ずつ。全部やる・順番聞かない
metadata: 
  node_type: memory
  originSessionId: 04923414-a96f-48e2-b7f4-5622fc881e58
---

2026-06-30〜 ユーザ指示「効率でなく一つの作品事(per-case)調べて、本番前の最後の仕上げ。**全部やるので順番を聞く必要はない**(=どの作品から等を毎回聞くな・私が淡々と全部潰す)」。これまでの試行錯誤の結論=巻抜け作は「ほぼ確実に何らか問題を持つ」群、丁寧にやらないと直らない。

## 対象と分類 (docs/production-diagnostics/vol_gap.tsv = 1,417作)
- **誤マッチ(別作混入)**: 別作の巻が混入(欠けでない)。検出=`_detect-mismatch-ndl.py`(ISBN→実題名 NDL+harvest照合)→`.cache/mismatch-ndl.json`(34候補・大半は英↔カナ/ハイフン/巻副題のFP、本物は別作)。
- **奇子型(多版混在)**: 162作=`.cache/kiko-candidates.json`。signal=volume_label混在(数字+上下)+発売日矛盾+書影一部欠け。古典の多版作(サイボーグ009/カムイ伝/ドラえもん/エロイカ/ゴルゴ13等)。
- **単純抜け**: ~1,050作=1巻欠け。NDL/楽天で欠番巻確証→種4補完。

## ★土台データ (取得済・再取得不要)
- **`.cache/volgap-ndl.jsonl`** = 全1,414作のNDL正データ(ISBN/出版社/発売日/巻label/叢書/題、74,971レコード)。per-case是正の一次照合源。
- `.cache/isbn-title-map.json` / `isbn-author-map.json` = 楽天harvest ISBN→題/著者。
- `docs/production-diagnostics/*.tsv` = 本番診断(`_production-diagnostics.py`で再生成)。

## ★厳守ルール (ユーザ確定)
1. **楽天API=1秒1回 絶対厳守**(time.sleep(1.1))。NDLも1.2s。
2. **巻の多い作=Wikiがある可能性高→必ず活用**(版リスト・巻数の権威確定)。ユーザがWikiリンクをくれる事も。
3. **推測で触らない**=怪しい/曖昧は止めて確認・flag。同著者の作品集/原題/収録話は誤マッチと即断しない。
4. 全修正は**durable seed**+可逆。種2(.cache/db-v2.sqlite)不変。

## ★per-case是正の型 (確立済)
- **誤マッチ**: `data/seeds/volume-exclude.yml`に混入巻ISBN追記(slug/isbn13/reason/at)。正ページが在れば欠け巻を`volumes-supplement.yml`(種4)で移設。
- **奇子型(長編)**: ①Wiki版確定 ②`_reconstruct-cyborg009.py`を雛形に楽天harvest(title検索・booksGenreId=001001・outOfStockFlag=1・1.1s)→**ISBN-prefixでレーベル分類**→各版vols(title「009（N）」からN抽出・cover=largeImageUrl) ③`data/seeds/edition-overrides.json`に`{slug:{editions:[...], authors:[{name,role:writer_artist}]}}`。spinoff/コミカライズ別作は本編edition外(除外)。版アナライザ=`_analyze-edition.py <slug>`(現データ+NDL版グループ一望)。
- **単純抜け**: ISBN連番/題で欠番巻推定→NDL+楽天+種2(無=取込もれ)確証→種4(series_keys=既存ISBN→db-v2逆引き)。例=ゴルゴ13愛蔵版173。

## 済 (seed投入・次promiseで本番反映)
- ゴルゴ13愛蔵版173(取込もれ種4) / ねこぱんち(キジトラ猫の小梅さんvol26-29除去+29移設) / 人間ども集まれ!(4版分離=ホリデー新書/講談社漫画文庫/文春文庫/原版) / 丹下左膳(←手塚治虫漫画全集68除去) / だめんず(←グータンヌーボ除去) / 新上ってなンボ(←新々除去) / **サイボーグ009**(著者→石ノ森章太郎・本編4版=秋田SC15/豪華版23/MF完全版36/秋田文庫23・コミカライズ別作除外)
- **#6 単純抜け一括808巻(2026-06-30)**: ★`scripts/_volgap-offline-harvest.py`新規=キャッシュ済NDL(.cache/volgap-ndl.jsonl)からオフライン収穫(liveNDL不要・高速)。guard4層(出版社prefix一致/series_key bind/種2既存ISBN skip=under-merge除外/巻番号既存skip)+媒体別作guard(録音資料/小説prefix/外伝)。813clean中808適用(除外4=バスタード録音資料・コナン特別編小説v4v5・ぼっち外伝v7、既存dup1)。**770件が2023+新刊MADBラグ**(ワンパンマンv32/チェンソーマンv19/ちいかわv7等)。種4 auto 151→959。`data/seeds/volumes-supplement-auto.yml`。本番反映=次promote。w3.yml直接編集(非durable奇子型・壊れimprint)はrevert済(W3は巻抜けリスト外)。

## 保留 (推測で触らず・要個別確証)
- 空がすき!←竹宮恵子作品集5(作品集版か) / マンハッタン・オプ←凝った死顔(収録話か) / 脱いだら絶倫!?←絶倫教授の実験体(=**成年向け**・vol1原題で同シリーズ濃厚=触らない)

## under-merge(欠番ISBNが種2の別クラスタに実在)= 2026-06-30 全63作分析済
- ★worklist=`docs/production-diagnostics/volgap-undermerge-worklist.tsv`、アナライザ=`scripts/_volgap-undermerge-analyze.py`。
- **DIFF 17作**=別作(実は欠けでない・無対応が正): グラゼニ大リーグ編/東京ドーム編・X-MEN・ねこぱんち別作混入・euromanga→ラストマン等。NDL題検索が別作を返しただけ=触らない。
- **SAME 46作**=同題分裂(要確証merge)。merge機構: `find_related_series_ids`が自動merge(同qid+同題/kana表記ゆれ但しASCII片側のみ)、明示=`series-merge.yml`の`merge_keys:[series_key...]`形式(`main`/`aliases`はinert)。
  - **済(著者一致確認の安全merge6件)**: キラーズホリディ/デイ・ミスター味っ子Ⅱ/2・新約Marchen/Märchen・ちょこれいと/ちよこれいと・猛き竜星/龍星・ほんにゃらゴッコ/ごっこかりあげクン。
  - **要NDL改題確証(残)**: 暴君ヴァーデル花嫁↔初夜編=巻番号錯綜(初夜編1-12と17-21両存)tangled・スーパーマリオくん=2qid(Q11477301/Q4023214)多クラスタ・湘南爆走族=著者違い(吉田聡vs西城隆詞)。これらは推測禁止・各々NDL「改題巻次継承」確認後。

## 確証ベースの収穫(ユーザ方針=確証だけ修正・怪しいは飛ばす・人気多版は後回し)
- ★**楽天全harvestがローカルキャッシュ済**(.cache/rakuten-isbn-delta.jsonl 828MB等)→`scripts/_rakuten_match_lib.py`(残差題完全一致guard=スピンオフ排除)でオフライン照合可。NDLで拾えなかった残にはこれが補完。
- **#8 cyborg-009 vol34**=#5収穫漏れ自己修正。NDL深掘りページングでメディアファクトリー版vol34=9784840104760特定(非連番ISBN)。
- **#9 楽天harvest確証64巻(38作)**=`_volgap-rakuten-harvest.py`(EASY+MID対象/BIG除外)→候補115→`_volgap-rakuten-filter.py`で厳格化(同出版社prefix+種2非存在+**前後巻発売日整合=版混在検出**+partial-skip作丸ごと除外+人気pop>=3000除外)→クリーン64のみ適用。男どアホウ甲子園11/悪魔の花嫁3/紺碧の艦隊/BIRTH7等。
- ★**飛ばした(怪しい/版混在/人気)**: うしおととら/今日から俺は!!/ゲゲゲ鬼太郎/北斗/ナウシカ/極道めし/GOLD/東京物語(版跨ぎ日付逆行=Frankenstein)+ぼっち外伝。これらは奇子型per-case(Wikipedia版確定)が要る=後回し。

## 残 (確証できるものから・怪しいは飛ばす・人気多版後回し)
- ★現況: 巻抜け仮想 **適用前1391 → 適用後532(859 closed)**。残532=`docs/production-diagnostics/vol_gap_virtual_remain.tsv`。
- 残の主構成: ①版混在/人気多版(奇子型per-case=Wikipedia要・後回し) ②NDLも楽天も無い(真の欠落 or 偽gap=触らない) ③under-merge SAME残(NDL改題確証) ④単巻欠け残(楽天で題が完全一致しなかった=表記差)。
## 奇子型per-case(option3)着手 = 2026-06-30
- ★型: 多版作は「版ごとにISBN系列が固まる」→cached NDLに同版欠番が在る。`scripts/_volgap-edition-aware.py`=欠番ISBNが**その版の既存ISBN共通prefix>=10桁一致**時のみ採用(版跨ぎFrankenstein回避)+種2非存在+発売日整合。
- **済**: うしおととら(ワイド版v2-9=9784091258625〜694取込もれ・standard/文庫は完備)/帯をギュッとね!ワイド版v14/南国少年パプワくんDX v2/世紀末リーダー伝DX v6。→種4手動(edition_type指定でpromoteが版振り分け)。
- ★**飛ばした(怪しい=ユーザ指示通り)**: 風の谷のナウシカ=standard欄が上下巻/アニメージュ/別年ISBN混在のFrankenstein+2ページ分裂(-1984/無印)+NDLに楽譜/小説/台湾版混入。無理に1巻足しても直らない=全面Wiki版確定rebuildが要る大仕事→後回し。多くの残がこの型。
- ★現況: 巻抜け仮想 **適用前1391 → 適用後528(863 closed)**。機械確証(NDL union/楽天harvest/版aware)はほぼ出し切り。残528の大半は①Frankenstein多版(全面rebuild要・後回し)②偽gap/非漫画混入③under-merge。**確証できないものは触らない**方針継続。

## Frankenstein全面rebuild(ユーザWikiリンク提供) = 2026-06-30
- **#11 風の谷のナウシカ(本編)**: Wikipedia権威で版確定→edition-override再構築。ワイド版全7巻(徳間・1983-07-01〜1995-01-15・原刊日)+豪華装幀本上下(1996-11-30)。混在ISBN(上下巻/別刷/講談社/楽譜)排除・著者宮崎駿・全冊楽天書影。★講談社1984版(別ページkaze-no-tani-no-naushika-1984・正体未確定=フィルムコミック疑い)は保留。
- **#12 北斗の拳**: 本編(原哲夫・hokuto-no-ken・standard30+文庫15)は完備。junkページhokuto-no-ken-2016(イチゴ味v5,6,8,9+BBQ味の寄せ集め=本編無関係)を解消: イチゴ味が2 series_key分裂(qid Q16770279)していたのをseries-merge→ichigoaji 1-9完成(NDL確証・dup dedup・迷子v8,9回収)、BBQ味は別作で単独化。★本編standardのv28-30=新潮社2002(9784107700XXX=コアミックス完全版系)混入を発見=別版混入(gapでなく余剰)・多版rebuild案件で後回しflag。
- ★型の学び: 多版人気作は「同qid別series_keyの分裂」と「別版ISBN混入」が両方ある。Wiki版確定→①分裂はseries-merge②混入はedition-override or volume-exclude。NDL by-ISBNで各ISBNの実題・巻・版を確認してから。

## title+wiki 自律処理 = 2026-06-30 (ユーザ「タイトル wikiで調べて進めて」)
- 自分で `ja.wikipedia.org/wiki/<title>` をWebFetch→版確定。記事無しはNDL/楽天のみ・確証取れねば飛ばす。
- ★auto guardの系統的盲点(手動per-case要): ①ルビ題(怪物(けもの)事変=残差題不一致) ②出版社移籍(魔法使いの嫁 マッグガーデン→ブシロードワークス=同pub guard弾き) ③latin/accent題(Murciélago)。
- **#13適用**: 怪物事変v22,23・魔法使いの嫁v21・極道めし7,8・元祖Dr.タイフーン7,11(楽天確証・手動)。
- ★live楽天確証器`_volgap-rakuten-live.py`(全379単一版・残差題完全一致+同pub+発売日整合)→候補67だが**大半が怪しい**(外国X-MEN/4コマアンソロ/外伝ぼっち/体験告白/多版ゲゲゲ)→`docs/production-diagnostics/volgap-live-cands-pending.tsv`に63件文書化し飛ばし(後日漫画性per-case確認)。
- ★現況: 巻抜け仮想 **1391→522(869 closed)**。残522は怪しい(外国/アンソロ/外伝/体験/多版Frankenstein)が中心。確証できる単純取込もれはほぼ尽き、残りは多版wiki rebuild(薬屋=2作画版/キングダムaizoban/ノラガミdeluxe等)か漫画性判定要。

## 端から全件sweep(人気順やめ) = 2026-06-30 進捗
- 全remainに対し系統sweep完了: ①cached NDL版aware(9桁prefix一致+残差題完全一致) ②cached楽天harvest ③live楽天単一版 ④live楽天×版aware ⑤ルビ除去パス。各々 種2非存在+発売日整合(版混在Frankenstein検出)+残差題完全一致(外伝/別作排除)guard。
- ★スクリプト群: `_volgap-edition-aware.py`(cached NDL版aware) / `_volgap-rakuten-harvest.py`(cached楽天) / `_volgap-rakuten-live.py`(live単一版) / `_volgap-edition-live.py`(live版aware) / `_volgap-ruby-pass.py`(ルビ除去)。怪しいは`docs/production-diagnostics/volgap-*-skipped/pending.tsv`へ文書化し飛ばす。
- ★現況: 巻抜け仮想 **1391→477(914 closed=66%)**。残477内訳: latin題109(foreign+format)/単一版old<2000 119(pre-ISBN=false-gap/no-data多)/多版107(wiki rebuild要)/recent>=2015 56(出版社移籍/format)/other87。
- ★残の直せる見込み: recent56(移籍tolerant)/多版107(wiki per-case=薬屋2作画版等)。latin/old大半はforeign/データ無=skip。

## clean多版 慎重rebuild = 2026-06-30 (ユーザ「clean構造の多版だけ慎重rebuild・ISBN無し飛ばす」)
- 全巻ISBN有の多版remain=94作抽出(`.cache/clean-multiedition.json`)。ISBN無し含む作はskip。
- **キカイダー型を発見**: 種2でbunkobon巻のedition_typeが"standard"誤分類→promote dedupで消失。→`_volgap-edition-complete.py`(各版を同ISBNブロック9桁prefix+残差題完全一致でNDfrom欠番補完・既存巻保持)。
- ★**版完成器の落とし穴**=版間でISBN 9桁prefix共有する作(rinta deluxe+19/g-defend bunko+50/ginga-weed bunko+35/王様の仕立て屋/12の結婚物語等)はブロックで版区別できず**別版巻を引き込んで重複版生成**→`版間prefix重複作はskip`guard必須。これ入れて39→8作に絞り、5完全解消(れもん白書/やじきた/浦安鉄筋/光とともに/うちの3姉妹)+キカイダー手動。
- ★現況: 巻抜け仮想 **1391→471(920 closed=66%)**。
- ★残471の性質(慎重判断で大半skip): ①版間prefix共有多版31(ブロック区別不可=per-case wiki要・リスク高) ②ISBN無し/pre-ISBN(データ無=直せない) ③foreign/アンソロ(scope外) ④false-gap。**確証して安全に直せる分は概ね出し切り**。残りは無理に触らない(誤rebuild=DB破壊リスク)。

## 有名作の版/分裂per-case + 新機構 = 2026-06〜07
- ★**related_pin機構**(新設): `lib/schema.ts`+`components/RelatedWorks.tsx`(computeRelated pin最優先)+promote(_eov.related_pin pass)。edition-overridesに`related_pin:[slug]`で関連欄の先頭固定。ドラえもん→大長編 / カムイ3部相互。
- ★**series-keep機構**(新設): `data/seeds/series-keep.yml`{keep:[slug]}+promote(spinoff drop免除)。spinoff誤判定(同題前方一致の子)でdropされる独立作を復活=独立ページ化。**dropクラスタ復活の正規ルート**。カムイ伝第二部(max2000<CUTOFF2015でspinoff drop)を復活。
- ★**ISBNはWiki/ユーザ提供を鵜呑みにせずNDL/楽天で1冊照合**(カムイで痛感): 提供790系=のりピー/櫻狩り、900系=ワタリ/伝染るんです 等の別作だった(小学館共有ISBNブロック)。決定版878系のみ正。**楽天で正ISBN自取**が確実([[feedback_extract_full_source_data]])。
- **済(promote#2反映・push済)**: 悪魔の花嫁(3版)/ゴルゴ13コンパクトv173/ドラえもん(4分裂統合+てんとう虫全45巻Wiki権威ISBN+大長編v18+pin)/カムイ伝3部(第一部:ゴールデンC21+決定版15+文庫920系15 / 外伝:原版14+文庫922系12+決定版11 / 第二部:原版711系22+文庫858系10+決定版12・series-keep復活)/ナウシカ分裂元-1984(講談社フィルムコミック)drop。
- ★多版rebuildの型: ①Wiki/楽天で版構造確定 ②各ISBNをNDL/楽天照合(鵜呑み禁止) ③edition-override(版完全置換・現データ誤ISBN是正) ④別シリーズは混ぜず別ページ+related_pin。promote#1=922巻/promote#2=有名作群。manga.v2はgitignore(R2別配信)・索引+previewはcommit。

## NDL全件triage一括補完 = 2026-07-01 (今セッション中核)
- ★**方式**: 巻抜け仮想の残tsv全件×`.cache/volgap-ndl.jsonl`で、各作の**欠け巻番号→NDL volume一致のISBN**を引く→「全欠け巻のISBNがNDLに在る」128作を抽出→**同社guard**(欠けISBNと既存巻のISBN出版者記号reg[3:9]一致 or NDL出版社名=ページ版社名一致=版混同排除)で安全部分集合に絞る→**手動種4(volumes-supplement.yml)へ純粋追加**(edition_type=該当版でpromoteが版振り分け・series_keys=既存ISBN→db-v2逆引き)。巻抜け仮想で閉鎖検証。
- **確定(commit/push済 #39+#40)**: SAFE46作92巻(同registrant一致)→41閉鎖 + 救済19作51巻(NDL社名=版社一致=同社別ISBN block)→18閉鎖。**計59作閉鎖・巻抜け仮想 448→379**。少年ケニヤ/男どアホウ甲子園(秋田文庫)/マッドブル34/博多っ子純情(愛蔵)/キャプテンキッド(deluxe)/ARMS(wide)/王様の仕立て屋/エロイカ(文庫)等。版routing(bunkobon/aizoban/deluxe)検証済。
- **個別per-case(#36-38)**: ピン!ピン!ピン!/おしごと(1巻2版誤番号→edition-override)・うさるさん/ゲーム世界転生<断罪>/キスミークライング(真の欠けv補完)。
- ★**revertした失敗(教訓)**: 自動round化(`_volgap-autofill-round.py`)は危険=①**年号誤parse**(umanari「2011」をv2011化) ②アンソロ再混入(ねこぱんち/本当にあった笑える話=高番号で閉じず) ③**部分埋め**(bartender standard[2-18]・red-eyes deluxe[8-26]はNDLが部分被覆のみ+版混在疑い=閉じず・tangle悪化)。→**閉じる(全欠け被覆)cleanだけ残す**方針。番号>=500 guard(年号/アンソロ排除)も有効。
- ★**worklistは古い**(stale): `.cache/pubdiff-worklist.json`はやっぱ人間/花に噛みぐせ等[1-4]既完備を残gapと誤表示。**現manga.v2基準=巻抜け仮想 --list が真**。

## ★残379の性質 (2026-07-01・大半は安全に直せない)
- **版混在/under-merge**(bartender/red-eyes deluxe=旧版+新版mix・NDL部分被覆): 真のper-case disentangle要(版分離)。
- **多版第2版gap**(myououden-rei deluxe[11,12]・shippo deluxe等=片版埋め済の残り版): 別版ISBN要。
- **アンソロ高番号**(本当にあった笑える話204-208・ねこぱんち): 構造的・欠番ISBN無。
- **テーマ別題シリーズ**(NHKその時歴史60巻超/ゲゲゲ鬼太郎=themed題でISBN多版混在): 構造modeling要。
- **年号誤parse**(umanari v2011型): 欠けでなく**誤番号**=renumber案件(別タスク)。
- **ISBN無/pre-ISBN/foreign**: データ無で直せない。
- → 機械的に安全補完できる分(NDL欠け巻ISBN有+同社)は**ほぼ出し切った**。残りは各々judgment要・怪しいは飛ばす方針継続。

## 旧・残メモ
- under-merge SAME残40=NDL改題確証→series-merge.yml merge_keys追記。
- 奇子型161(サイボーグ009以外)=長編はWiki+楽天harvest。カムイ伝/ドラえもん/エロイカ/はいからさん/ワイルド7…
- 単純抜け 残=NO_NDL_FOR_MISS約325(キャッシュNDLに欠番巻ISBN無=楽天/Wiki liveで要確証→種4)。※2023+新刊ラグ808は#6で収穫済。
- 誤マッチ保留3の確証。

## ★巻抜け仮想再現ツール (= 2026-06-30・ユーザ要望「テスト環境の巻抜けフィルタを本番DBで仮想再現」)
- テスト環境(mangal-preview)の「テスト専用フィルタ巻抜け✓」(`app/HomeClient.tsx` vol_gap=index flag)を本番DBで仮想再現する `scripts/_volgap-virtual.py`。
- **未promoteのseedを仮想適用**(種4 supplement+auto / series-merge手動+auto / **edition-overrides奇子型=版完全置換**)し、build-list-index同等のvol_gap判定(=ある版でmax-min+1>巻数)を再計算。promote(~90分)待たず**80秒**で残巻抜けを算出。冪等(既反映no-op)。
- `--list`で残gapをTSV出力=`docs/production-diagnostics/vol_gap_virtual_remain.tsv`(slug/title/版type:欠番)。
- ★結果: **適用前1391 → 適用後552(今セッションの種4 808+merge6+奇子型overrideで839 closed)**。残552が次worklist。
- ★副産物: 自分の修正の欠陥も炙る(cyborg-009 MF完全版vol34抜け=#5収穫漏れを検出)。修正後はこのツールで再確認する習慣。

## ★反映パイプライン (節目で一括)
seed投入後、`python scripts/_promote-bulk-v2.py`(フル~90分 or 影響slugを--only)→cover stage(`_apply-covers-stage.py`)→索引(`_build-list-index.py` フル or --update)→commit/push。テスト環境=`.preview-data`に巻抜け作copy+索引(現在巻抜けだけ1,399配置済)。promoteは重いので数十件溜めてから。

関連: [[kiko_multiedition_mixing_heuristic]] [[edition_canonical_mechanism]] [[volgap_mostly_undermerge]] [[harvest_match_mechanism_applied]] [[feedback_accuracy_is_the_goal]]


## 2026-07-01 巻抜け434 title+author NDL per-case (イアラ式)
- ★**全433作をtitle+author でNDL検索しキャッシュ**=`.cache/volgap434-ndl.jsonl`(全版データ・再検索不要)。残worklist=`docs/production-diagnostics/volgap434-remaining.tsv`。
- triage: **SAFE13**(同社ISBNで欠け全被覆=新刊ラグ最新巻・種4補完済 bocchi/saki/riezon等) / complex365(奇子・版混在) / NDLデータ無55。
- ★**per-case済**: イアラ(GC6+文庫5+異色短編傑作選1に版分離)/あばしり一家(bunko 1978v7除去)/俺の甲子園(1976v11除去)/ムサシ(1977v12,13除去)。
- ★**迷子巻除去の判定(重要・危険)**: 「版内の年代外れ巻」除去でgap解消に見えるが**2種を峻別必須**:
  - (a)**別版の迷子**=ISBN無+別年代(あばしり1978/俺甲1976)→除去OK。NDLで別版と確認。
  - (b)**実在する後巻**=ISBN有+最近(railgun v19/20=2024/25, out v26/29)→中間が未取込なだけ。**除去=実巻消し=重大誤り**。触るな。
  - 自動検出(`.cache/stray-cand.json`)は両者を混同=一括禁止。必ずNDL+ISBN有無で個別確認。
- ★除去はISBN無だと volume-exclude 不可→**edition-override で版再構築**(ISBN有巻保持)。著者は**現ページ保持**(推測禁止=水島新司と誤記した反省)。
- 反映=`_reflect-targeted.py --only <stem> --push`(数分)。stemはslug-aliases逆引きで解決。
- ★残complex365の大半=「真に不完全(原版pre-ISBN欠番)」「別作homonym」「版混在Frankenstein」で**無理に触らない**。安全fixは~10-15%程度。多セッションgrind。


## 2026-07-02 自律per-case最終tally
- ★本番巻抜け **434→411**(今セッションで約23頁closed)。全fix=targeted反映+push済(_reflect-targeted.py)。
- 済28作: SAFE13(新刊ラグ種4)+迷子除去7(あばしり/俺甲/ムサシ/月姫/コンドル+α)+奇子reconstruct5(イアラ/けっこう仮面/ハチのす大将/狼の星座/パーマン)+ISBN補完3。
- ★著者汚染是正例: 狼の星座=川島健三除去→横山光輝(NDL権威)。パーマン=中公藤子不二雄ランドv11補完+レーベル是正。
- ★**自律の到達点**: 「ISBN無し飛ばす」方針では**ISBN付きで安全に閉じられる分は尽きた**。残411の大半=(a)no-ISBN pre-ISBN原版(走れメロス/背番号0/RG VEDA新書館原版等) (b)実在最近巻が未取込でNDLもISBN無 (c)別作homonym。純no-ISBNの完全再構築は推測要=方針上skip。
- ★キャッシュ`.cache/volgap434-ndl.jsonl`(全433 title+author NDL)+`docs/production-diagnostics/volgap434-remaining.tsv`は永続化=中断耐性。特定作をユーザ指定 or 方針緩和時に再開可。

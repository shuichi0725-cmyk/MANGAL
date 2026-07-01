---
name: collision-slug-investigation
description: slug/衝突調査の結論。派生物は必ずmerge+promote全filter後のページ単位で。真の本番衝突1,797と雑誌drop list/副題appendの taxonomy
metadata:
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

slug 生成器(B-3)+ 衝突/分裂調査の結論(2026-05-31)。 関連 [[series_fragmentation_rootcause]] [[pending_slug_generator]] [[adult_judgment_architecture]]。

## ★最重要教訓: 派生物は「merge + promote全filter適用後のページ単位」で作る
slug/衝突分析を **生 種3(76,435 entry)**で作ると過大評価。 ユーザ指摘で3つの欠陥が連続発覚:
1. **merge無視**(はたらく魔王=029/和ケ原/qid の3断片は series-merge-auto で正しく1ページ。 私のslugがentry単位で誤3-suffix)→ `_slug-assemble.py` を rep(merge代表key=巻数最大)集約に修正(commit 0c6e004)
2. **promote DROP無視**(とんでぶーりん孤立stub=アニメコミック edition type=anime で本来drop。 daito imprint slug=フリガナ修正済だが pkl cache stale で旧値)
3. **成年除外無視**(個人授業 鬼ノ仁=adult_score7 で正しく除外済なのに collision-detail に出た。 成年システムは正常=鬼ノ仁flag/遊人青年誌エッチは0が妥当)

→ `_collision-filtered.py` = merge+成年(adult≥3)+kept edition+title prefix/contains drop+雑誌drop を全適用。 **生存ページ69,070 / 真の衝突1,797 base・4,362ページ(~2.6%)**。 生種3の見かけ衝突から大幅減。

## 衝突の taxonomy(`_slug-collision-triage.py`)
- **真の別作品(suffix正当)**: kana(カナ/（仮名）/KaNa)/vampire(5別作)/clover = 発売年suffix で区別
- **副題で区別すべき(170群)**: 劇画池波正太郎(谷中・首ふり坂/決闘高田の馬場)/大判鬼平犯科帳 = ★**subtitle列を title+slugに append**が自然(種2にsubtitleデータ実在を確認済)。 未実装
- **merge漏れ(少数)**: ①著者マスター重複(PEACH-PIT全角‐ vs Peach-Pit半角- が別id→しゅごキャラ割れ) ②著者ゼロstub(arion/akira の著者なし記録) ③原作のみ共有(その時歴史=多人数作画/A1ガードで保留)
- 巻レベルmis-grouping: その時歴史(全55単行本、 コミック版4巻が3sidに散在+別edition混在)= MADB元データの巻散乱、 hand整備案件

## 雑誌 drop list(`data/seeds/magazines-drop.yml`、 commit e3b8021)
- ★判別軸: 真のアンソロ誌=号ごと**distinct著者≥20**(古典翻案は原作+作画で平均2だが distinct最大~15)。 avg著者では古典/海外comic誤検出
- 59件抽出 = confirmed:true 51(GUSH maniaEX/on BLUE/つぼみ/ルチル/実話・怖い話mook/Fate等アンソロ)+ 要目視8(ソニック=海外comic/ロミオ/怪談/漫画版世界の歴史等の誤検出疑い)
- promote drop配線は**未実装**(confirmed:trueのみdrop予定、 種2/種3不変)。 review_small 345は小規模で保留

## 著者正規化(修正1)= naive は危険
`_gen-author-set-merges.py --normalize`(既定OFF): 著者名NFKC正規化でPEACH-PIT統合できるが、 原作者名寄せで**椿姫/ああ無情/十五少年漂流記の別翻案をover-merge**(検証で確認)。 common-primary等のガード必要、 現状opt-in OFF。

## ★衝突 suffix の確定ルール(2026-06-05 ユーザ確定)
- **原作者がいて複数の漫画家が漫画化した名作**(その時歴史/古典翻案 等)= ★**全版に `作品名-作画家姓-年` を付与し、無印を作らない(option2 確定)**。 理由: bare(無印)は“原作/作品そのもの”を指し、 どの漫画版にも与えない。 ★これで「どれが無印か」の取り合い=**順番(deterministic)問題が消える**。
- 一般の同名異作品(原作なし・偶然同名)= 主版(巻数多→古→姓ローマ字昇順で固定)無印 + 従版 `-姓+年`(option1)。
- ★作画家姓ローマ字 = mangaka.qid→Wikidata→ヘボン / 年 = 初出。 ★無印を作る場合の主版選定は**決定的tie-break**でURL安定を担保。
- ※私は当初これを記録しておらず聞き直した=記録漏れ。 今後 gap c(衝突suffix)実装時に本ルール適用。 [[pending_slug_generator]]。

## ★gap c 実装の進捗(2026-06-06)
- ★**前提=gap a/b を base に統合済**(`_build-slug-override.py`→`.cache/slug-override.tsv` 5,634件[gapA確信3684+gapB num1362+latin588]、 `_slug-assemble.py` に override 最優先注入。 title-join回避=V2からkey決定的再導出・衝突0)。 これで衝突集合が gap a/b ベースで確定(engage-kiss等が英題統一で正しく衝突)。 ★cache再生成のみ・本番不変。
- ★**gap c-3(不正/空slug 16件)= 完了**(`data/seeds/slug-malformed-triage-candidates.tsv`)。 ISBN国コードで判別: 非978-4=外国版orphan13→drop(漫画由来はJP原編残存確認・BD系は非漫画)、 978-4=EMPTY真作3(`Page 1`=ぺーじわん/`囿者は懼れず`=Web確定でSquare Enix漫画[勇者ユウシャ当て字]→KEEP+merge+slug `yusha-wa-osorezu`)。 ★latin判定だけなら誤dropだった2件をISBN国コードで救済([[mangal_inclusion_scope]])。
- ★**gap c-1(真の別作品=著者非共有・別年 → option1)= 候補確定**(`data/seeds/slug-collision-option1-candidates.tsv`、 1,235群)。 主版無印1,234 + 従版`-姓-年`592 + `-年`947。 ★決定的tie-break(巻数多→年古→姓→rep)。 ★姓ソース=**AniList staff.full**(`_extract-anilist-surnames.py`→native→姓34,359件、 Art役割優先・長音drop、 三浦→miura)が正規。 **pykakasi姓は不採用**(白泉社/HACCAWORKS等を姓と誤る)。 ★クリーンlatin外国版(Akira等)は ISBN国コードで分離→drop。 ★`surname_romaji` のラテン名バグ修正(「名姓」順=末尾が姓: Katsuhiro Otomo→otomo)。
- ★**重要教訓=「姓web検証67件」は精査で0件**だった: NEED判定の実体は **年欠落53(→年補完)+ v0スタブ18(断片récord→merge/drop)** で、 真の同年衝突=0。 Wikidataも欠落713はqid無で不可と判明。 ⇒ AniList正確姓+年で衝突解決ほぼ完結。 ★**一意性検証済**: 生成2,773 slug全ユニーク・重複0、 群外69,512ページとの交差衝突0=URL安全。 残71(DEFER_V0_STUB18/DEFER_YEAR_MISSING53)は本番化前の最終掃除へ繰越。

## ★gap c-2 merge漏れ336 = 裁定完了(2026-06-06、`data/seeds/slug-c2-merge-candidates.tsv`、適用なし)
- ★機械仕分け(`_gap-c2-classify.py`/`_gap-c2-refine-difftitle.py`: foreign/v0/フリガナ/前方一致/著者)→ merge候補だけ isolate → **2 workflowでWeb裁定**(計194群・282検索)。 ★[[merge_needs_external_proof]]を充足(全件出典付)。
- ★最終ルーティング(336群): **merge=147**(同一作の旧字/かな⇄ラテン/誤字/フリガナ括弧/★著者role split[原作⇄キャラ原案⇄脚色]) / **subtitle=100**(続編/第N部/外伝/編/スピンオフ→副題で別ページ) / **suffix=51**(同音異作・別作者→`-姓-年`) / **option2=1**(仕掛人藤枝梅安=池波原作+さいとう/竹村2作画→全版作画家姓) / **partial=8**(本編+outlier。 ★outlierに画集[ONE PIECE COLOR WALK]/アニメコミック[アニメブックBJ]/外国語版[思春期ちゃん英語版]=drop) / **drop=22**(外国版/v0/anthology) / **uncertain=5**(確証なし保留) / edition+c3=2。
- ★機械ORTHO_MERGE判定の**12%(15群)が実は別作**(BOYS BE続編/劣等眼別作画/闇のエクササイズ=kana誤紐付)→ Webで正しく排除。 = machineだけでmergeしてはいけない実証。

## ★gap c-2 同年衝突363 = 裁定完了(2026-06-06、 同 `slug-c2-merge-candidates.tsv` に追記。 計550群)
- 機械仕分けで356群が要Web(著者非共有=merge signal無で機械決定不可)→ workflow(26並列・583検索・1.86Mtok)。 既定=別作(接尾辞)、 確証ある同一作のみmerge。
- 結果(356): **different_works=152**(別出版社の同音異作=最多。 源氏物語/若草物語/西遊記の古典別漫画化、 バンパイヤ/EDEN/gift/red/himawari) / **merge_all=146**(★アンソロ寄稿者のauthor-cluster分裂[艦これ/ひぐらし/GUSH mania]、 ★著者role split[原作/作画/監修]、 表記揺れ[しゅごキャラ/スプーンおばさん/HR]) / **option2=9**(リトルバスターズ/大図書館の羊飼い=原作+別作画) / **subseries=10** / **partial=13**(本編+画集/アニメコミック/外国語版outlier) / **uncertain=25**(確証なし保留) / 欠落1(idx308要再検証)。
- ★**c-2 merge候補 合計293群**(merge漏れ147 + 同年146)= 全て外部確証(出典)付。 これが本番DB merge の適用対象(要GO)。 残り = 別作→接尾辞 / サブシリーズ→副題 / drop / option2→全版作画家姓。

## ★uncertain30 = NDL流ISBN/出版社裁定で解消(2026-06-06、 ユーザ指摘「ndlの情報です」)
- ★Web plain title検索は汎用題でノイズ大(一番すてきな結婚式 等の無関係作が大量ヒット)→ ★**ISBNプレフィックス(出版社登録ブロック=978-4-DDDD)が決定的**。 db-v2のISBNで: ★**全entryが同一8桁ISBN前方=同一出版社の同一numbering=同一シリーズの断片→merge** / ★**別出版社=別作→suffix**。 NDL SRU(`ndlsearch.ndl.go.jp/api/sru` recordSchema=dcndl、 HTML escape注意)も seriesTitle/著者典拠で裏取り可だが、 自前ISBNで足りた。
- 結果: uncertain30 → **merge12**(同出版社連番: komikku-arisu-shisutaa[97848773]/kinjirareta-otoko-to-onna[97845371双葉社]/omoikkiri系[97840634講談社]等) + **別作18**(別出版社: darkness[秋田253 vs 大都社821]/kyofu-gakuen[講談063 vs リイド651]等)。 ★**残uncertain 0**。 idx308(スパロボα4コマ、 workflow取りこぼし)=光文社334連番でmerge。
- ★この **ISBN/出版社突合は c-2全体の再監査にも使える**(work--agent判定の誤りを機械で照合)。 既存 `.cache/ndl-merge-proposed.json`(NDL著者典拠で51 merge提案)も同系。

## ★c-2 最終(全551群・uncertain 0): merge306 / 別作(suffix)182 / subseries21 / partial21 / option2 10 / no_merge10
## 未完/次の手
- ★gap c-2 適用設計: ★**merge306**を `series-merge-auto.json` 系へ反映(要GO・要alias)、 partial21のoutlier(画集/アニメコミック/外国語版)をdrop、 option2 10の全版作画家姓付与。
- 副題append(170群)実装 / 雑誌drop promote配線 / gap c-3のdrop13+kana補完3の適用 / 修正2(著者ゼロstub吸収、 但しアニメcomic除外要)/ slug適用(folder rename=要GO+alias表)
- ★統合TSV(gap a/b/c を全76,435件の最終slug案に束ねる)→ レビュー → GO → 適用

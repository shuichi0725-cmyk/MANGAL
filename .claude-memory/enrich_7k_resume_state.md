---
name: enrich-7k-resume-state
description: "キャッチ/詳細エンリッチの進捗と再開点。2026-07-30時点: full系バッチは全消化済。★現在の作業=短キャッチrequeue(batch-0001〜0190)の消化で、0116まで=2,393作を本番反映済/残1,681作・次はbatch-0117から。genre系0218-0380も実質完了(残121はmaster32該当なし)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 0f715f40-d14b-4e9a-806c-fe24cfb6fc30
  modified: 2026-07-30T04:01:46.598Z
---

エンリッチ(キャッチ/詳細/ジャンル)の消化状況。材料バッチは `.cache/enrich-batches/batch-NNNN.json`(380本、2026-07-26生成)。

- **kind='full'**(2巻以上・楽天caption有)= catch+synopsis / **kind='genre'**(1巻)= ジャンルのみ(2026-07-14裁定)。
- 生成物は git 追跡: `data/enrich-out-2026-07/batch-NNNN.json`(dict形式 {slug:{catch,synopsis,genres_add}})。
- 適用器 = ★**`scripts/_apply-enrich-batch.py`**。字数ゲート(catch48-74/syn78-114)+丸写し8gram+master32検証+本番既済skipの純粋追加。`--requeue` で上書きモード。
- 書込先 = catch-ja.json / synopsis-slug-ja.json / genre-enrich-2425.json / manga-catch-index.json(全てpromote結線済)。
- 初回生成(0191-0217=645作)は 2026-07-29〜30 に消化・本番反映済。★**full系の新規生成は 0217 で打ち止め**。

## ★現在の作業 = 短キャッチ requeue の消化(次は batch-0085 から)

対象リスト = `docs/production-diagnostics/catch-short-requeue.txt`。7/27の並列生成4,750作が平均19字で貧相だった分の作り直し。
★調査済の事実: **requeue の中身は全件 kind='full'・2巻以上・caption有で、batch-0001〜0190 に収まっている**(0191以降には1件も無い)。

- **2026-07-30: batch-0001〜0038 = 807作を消化**(生成→`--requeue --apply`→`_reflect-targeted.py --push`で本番反映済)。
- **2026-07-31: batch-0085〜0100 = 359作を消化**(1スライス=2バッチ、8スライス連続。丸写しBLOCK 0件/警告1件のみ)。
- **2026-07-31(続): batch-0101〜0116 = 353作を追加消化**。★catchが47字前後で字数ゲート(48字下限)に落ちる違反が一気に増えた回あり(0113/0114で16件)。**狙いは55〜62字**、48ぎりぎりを狙わない。
- **残 = 1,681作(batch-0117〜0190)。次は batch-0117 から**。
- ★消し込みは **scripts/_rqdone.py** に恒久化(2026-07-31新設。バッチ番号を渡すだけでrequeue.txtから除去+残数表示)。
- ★**本番頁が存在しないslugが49件混在していた**(7/27生成後にdrop/rename済=充填不能)。
  `docs/production-diagnostics/catch-short-requeue-nopage.txt` に分離済。本キューは実作業分だけ。
  新しいブロックに入る前に `os.path.exists(f'data/manga.v2/{slug}.yml')` で洗うと無駄な生成を防げる。
- 1周の手順(2バッチ≒45-49作が実用単位):
  1. `python scripts/_rqdigest.py 0039 0040` (★2026-07-30に scripts/ へ恒久化済=毎セッションscratchpadで作り直さない。requeue掲載slugだけを、旧catch/syn+全巻captionつきで整形出力。`CAPLEN=150`で十分)
  2. `data/enrich-out-2026-07/batch-0011.json` 等に生成物を書く
  3. `python scripts/_apply-enrich-batch.py 0011 0012 --requeue`(検証)→ 通ったら `--apply`
  4. requeueリストから消し込み+セッション累積に追記(小scriptで一括)
  5. commit → `_reflect-targeted.py --only <そのブロックのslug> --push`

## ★実装知見(効率に直結)

- ★**キャッチは必ず「2文構成」で書く**。単文フックだと例外なく38-40字に落ちて48字ゲートで全滅する(2026-07-30に40件一斉違反で実証)。
  手本 = hunter-hunter(64字)/one-piece(62字)/kimetsu(55字)= 「[主人公と状況のフック]。[ジャンルの手触りで締める第2文]。」
- ★**狙いは60-68字**。実績は 0001-0010=中央値51字 → 0011-0014=中央値54字(60台を狙って書いてもこの辺に着地する)。
  実勢コーパス中央値65字にはまだ届かない。**60台に乗せたいなら第2文だけでなく第1文も伸ばす**
  (例「時の大老が襲われた桜田門外の変に始まる、〜」のように第1文に修飾を足す=58字まで伸びた)。
- ★**7/27の一括生成物は「短い」だけでなく、稀に synopsis が事実として誤っている**。実例:
  bakemono-yawazukushi=**まるごと別作品の内容**(『凪のお暇』的な大島凪の話が入っていた) /
  bakusou-kyoudai-let-end-goo-makkusu=「前日譚」と書かれていたがcaptionでは第一回WGP後の**続編**。
  → requeue時は旧synopsisを下敷きにせず、**captionから読み直して書く**こと。
- 丸写し8gramゲートは BLOCK 0.55 / WARN 0.40。★**0.42以上が出たら直す**(captionの言い回しをそのまま使っている印)。
  落とし方 = 固有名詞の登場順を組み替える + caption外の情報(巻数構成・シリーズ位置・完結の有無)を足す。実績: 0.42-0.49が7件出て全て修正。
- syn は78字が下限なので77字落ちが頻発する。**文末を「〜していく」「〜のだった」で伸ばす**のが手っ取り早い。
- `_apply-enrich-batch.py` の master32 ローダは 2026-07-30 に修正済(`genres.yml`の平坦dict形式を読めずジャンル検証が常に失敗していた)。

## 残りのもう一方 = genre系 0218-0380 は実質完了(2026-07-30 調査)

4,071件中 **3,948件は既にジャンル付与済**。残121件を本番と突合したところ、
**学習漫画(ドラえもん学習シリーズ/学研まんがひみつシリーズ)・画集・原画集・図録・挿絵集・評論(大塚英志/押井守/萩尾望都対談)・傑作選**
が大半で、★**master32に該当キーが無い**(教育・学習・評論のキーは存在しない)。
CLAUDE.md「該当が無ければ無理に付けず空でよい」に従い**空のまま据置が正しい**=これ以上追わない。
なお画集/評論/図録は [[art_book_inclusion]] の別ストリーム or 掲載境界の検討対象で、ジャンル付与より先に掲載可否の裁定マター。

## 保留にする型(捏造せず空のまま残す)

傑作集/編集本(ワタシの川原泉)・材料が実質空(ヤバ盛/吉野家兄弟)・評伝など非漫画候補(闇の王子ディズニー)・**フィルムコミック**(ズートピア=掲載境界)。

全量一括WFはセッション枠を食うので不可([[enrich-catch-synopsis]] skill が正本)。Opusインラインで2バッチずつ。

## ★旧synopsis誤り型の続報(2026-07-30 Fable検証: 訂正が頁に届かない構造があった)

- Opus発見の2件(ばけもの夜話づくし/レッツ&ゴーMAX)は **synopsis-ja.json(anilistキー)側の誤り**で、
  ★ばけもの夜話づくし(105592)⇔凪のお暇(105614)は**相互スワップ**(=生成batch内の対交換型。第3の被害作=凪のお暇も誤っていた)。
- ★**synopsis-slug-ja.json への訂正だけでは頁に出ない**: promoteは anilist synopsis-ja が先に埋め、
  slug seed は「synopsisが空の時だけ」fallback(L3331)。**synopsis訂正は必ず synopsis-ja.json(該当aidキー)を直す**。
  3キー是正+reflect済(e8b0fa48a)。changelog=enrich-requeue-changelog.jsonl(op=synopsis_ja_fix)。
- 型の含意: スワップは同一batch内でペアで起きる=1件見つけたら**相手側(内容が指す作品)も必ず誤っている**。両方直す。
- 未掃引の残リスク: synopsis-ja 39,591件の初期waveに同型が潜在しうる(生成キャッシュは消失=位置法医学不可)。
  検出案=synopsis×同頁caption/catchの語彙交差ゼロflag→AI裁定(月次サニティ候補・未着手)。

## ★2026-07-30 追加: 短あらすじ再生成キュー(4,189件)
- `docs/production-diagnostics/synopsis-short-requeue.tsv` = synopsis-ja が規格60-120字に足りない分
  (severe<40字 2,030 / mild40-59字 2,159。**楽天素材あり1,776件が着手対象**、無い2,413件は現状維持)。
- 消化順は skill enrich-catch-synopsis の通り ①空欄頁 → ②短キャッチrequeue → ③**この短あらすじキュー**。
- ★★**書込層**: あらすじは2層あり promote は **anilist_id キーの synopsis-ja.json を優先**、
  slug側(synopsis-slug-ja.json)は空の時だけ fallback。`_apply-enrich-batch.py` は 2026-07-30 に
  **anilist層へ書く分岐を実装済**(報告に「うちanilist層N」が出る)。旧仕様のまま slug側に書くと**silent空振り**。
- 検品柱との分担: **誤りは検品柱(synopsis-audit / _catch-audit.py)が直す / 短いのはエンリッチが太らせる**。

## ★2026-07-30 セッションで判明した追加ゲート(生成時に先回りする)

- ★**catch と synopsis の冒頭20字が完全一致すると VIOLATION で弾かれる**(2件実踏: 敏感アイドル/BLACK★ROCKSHOOTER)。
  同じ導入文を長短で書き分けると必ず踏む=**catchとsynは切り口を変えて書き出す**(catchはフック、synは設定から)。
- ★丸写しゲートは実際に BLOCK が出る(border-world=0.68)。captionが2巻とも同文の作品は、旧synがcaptionをほぼ写しているので
  **旧synを下敷きにすると必ずBLOCK**。語順・視点・語尾を変え、caption外の情報(巻数構成/シリーズ位置)を足して落とす。
- 実績字数: 0015-0020 で catch 中央値≈59字 / syn 80字前後。60台に乗せるコツは「第1文に修飾を足す」(memory本文の既述どおり)。

## ★2026-07-30 追加: requeue消化中に別作品混入を1件発見 → 検品柱の穴を実証

- `chika-chan-to`(ちかちゃんと!/BL)の本番あらすじが **「あつ森を舞台に島の暮らしを描く…」= まるごと別作品**だった(今回是正済)。
- 原因は **`_synopsis-audit.py` の `len(syn_t) < 4` スキップ**。内容語2語しかない短文は交差スコア0.0でも flag されない。
  **該当779件(caption有339/無440)**。詳細と手当て案は `docs/production-diagnostics/audit-followups.md` の **D-2** に記載。
- 帰結: **短キャッチ/短あらすじのrequeue消化は「太らせる」だけでなく「誤りの是正」も兼ねている**。caption無し440件だけが取り残される。

## ★2026-07-31 セッションの追記(batch-0067〜0084を消化した実感)

- ★**別作品混入は3例目**: `jaaku-na-tenshi`(邪悪な天使)の本番あらすじが「フラン/リトリック/リサ」という**まるごと別作品**だった
  (楽天captionは「ケリー/ルチアーノ」= Jet/Graham Lynne のロマンス)。captionから書き直して是正済。
  chika-chan-to / ばけもの夜話づくし に続く型で、**短キューの消化が誤り是正を兼ねる**という位置づけを補強する実例。
- ★**「か行」以降は丸写しBLOCKが跳ね上がる**。艦これ系アンソロ・シリーズ物・全集など**captionが全巻ほぼ同文/定型の作品**が固まっており、
  旧synを下敷きにすると 0.55超が1スライスに6件出た(batch-0081/0082 で実測)。
  対策=**最初から「言い換え前提」で書く**(固有名詞を残しつつ語順・視点・語尾を総取り替え、caption外の情報を足す)。
  後から直すと1件あたり生成しなおしになるので、初手から強めに崩したほうが安い。
- 1スライス(2バッチ=41〜50作)の所要は、生成→検証→丸写し修正→再検証→apply→消し込み→commit→reflect で概ね一定。
  丸写し修正が10件超えると1往復増えるだけで、手順自体は安定している。

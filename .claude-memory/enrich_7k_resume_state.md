---
name: enrich-7k-resume-state
description: "キャッチ/詳細エンリッチの進捗と再開点。2026-07-31時点: ★短キャッチrequeue(4,750作)は完走=残0。full系/genre系も消化済。★次の柱=短あらすじrequeue(synopsis-short-requeue.tsv)。severe×has_caption=yes 820件のうち材料が enrich-batches に在るのは285件"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2e629c9e-d55a-4074-a6ec-d0691965d657
  modified: 2026-08-06T08:42:17.394Z
---

エンリッチ(キャッチ/詳細/ジャンル)の消化状況。材料バッチ = `.cache/enrich-batches/batch-NNNN.json`(380本、2026-07-26生成)。

## ★2026-08-06: 作業リストを script 化(scripts/_enrich-newest-scan.py)

毎回 ad-hoc に走査していたのを恒久化。`python scripts/_enrich-newest-scan.py` で
`data/manga.v2` 全走査 → **catch/syn 欠け × 2巻以上**を**最新巻の発売日降順**で TSV 出力
(`.cache/enrich-newest-backlog.tsv`)。**初回実測 12,910頁**。1巻頁は除外済(2026-08-03裁定)。
- 1周 = TSV先頭50 → `_enrich-captions.py --slugs ... --src data/manga.v2 --live` →
  `MINVOL=2 CAPLEN=400 _enrichgap-prep.py 92NN 50` → 生成 → `_apply-enrich-batch.py` → `_enrichgap-done.py`。
- **slice 9202 完了(2026-08-06)**: 50作中**材料あり44**(取得率88%)。catch+43 / syn+40 / genre+14 適用・上書き0。
  **残 12,864**。★材料なし6件(saikyou-no-seibishi/jadou-season/ken-oni-tensei/shokigai-kara-tabidatanai/
  saikyou-majutsushi-no-dekiai-saijo/watashi-no-konoe-kishi)は done に入らないので**次スライスで再照会される**
  (楽天に出たら拾える利点はあるが、常に先頭に居座る。溜まったら別途 skip list 化が要る)。
- ★**字数は3節構成でも初回全滅**(catch 30〜44字 = 下限48に届かず44件中43件BAD)。**3節でも足りない**:
  各節を「体言止め1つ」でなく**1文相当**にし、**catch 55〜68 / syn 85〜100 を狙う**と一発で通る(2回目 BAD=2 → 微修正で0)。

## ★2026-08-03: 「新しい順」柱を開始(ユーザ指示)

- **バックログの実測**(`data/manga.v2` 全走査で catch/synopsis 長を採取): catch空 33,578 / syn空 31,217 / **両方空 31,063**。
  欠けあり合計 **33,724** = **2巻以上 13,727 / 1巻 19,997**。
- ★**新しい順に並べると上位は全部1巻**(新連載の第1巻・予約頁)。2026-07-14裁定「1巻=ジャンルのみ」に従うと
  キャッチ/詳細がまったく増えない → ユーザ裁定(2026-08-03)= **「1巻は飛ばして2巻以上を新しい順で」**。
  以後の「新しい順エンリッチ」は **2巻以上のみ**を対象にする。
- 消化済: batch-9200(1巻・ジャンルのみ25作) / **batch-9201(2巻以上44作=catch42・syn36・genre42)**。
  次スライスは 2巻以上バックログの 2026-05-18 より古い側から。
- ★材料収集は `_enrich-captions.py --slugs ... --src data/manga.v2 --live`(**--src既定は .preview-data なので本番は明示**)。
  50作/116巻で live 116req ≒ 2.5分。材料取得率は実測 **44/50**。
- ★ad-hoc スライスは **バッチ番号9200番台**を使う(既存0001-0380/9104-9107と衝突しない)。
  材料を `.cache/enrich-batches/batch-92NN.json` に `{"items":[...]}` 形式で置けば applier の丸写し検査が効く。

### ★予約頁にジャンルseedが届いていなかった(2026-08-03 修正・commit c6bcc1760)

`data/seeds/preorder-pages`(1,615頁)は種2を通らず promote の**ジャンル決定点に来ない**ため、
`genre-enrich-2425.json` に正しく書いても **頁の genres が空のまま**だった(applierは applied と報告するのに頁に出ない)。
本流と同じ優先順(trusted > rakuten > enrich)で予約ストリームにも結線済。巻き添え5頁も是正済。
★**新しい順は対象が予約頁に偏る**(実測 44作中36作)ので、これを直さないと以降ずっと空振りしていた。
catch/synopsis は元から予約ストリームが `catch_map`/`synslug_map` を見ていたので無事。
= [[genre_append_seed_mechanism]] の「seedの適用点は1箇所ではない」型の3例目。

- **kind='full'**(2巻以上・楽天caption有)= catch+synopsis / **kind='genre'**(1巻)= ジャンルのみ(2026-07-14裁定)。
- 生成物は git 追跡: `data/enrich-out-2026-07/batch-NNNN.json`(dict形式 {slug:{catch,synopsis}})。
- 適用器 = ★**`scripts/_apply-enrich-batch.py`**。字数ゲート(catch48-74/syn78-114)+丸写し8gram+master32検証+本番既済skipの純粋追加。`--requeue` で上書きモード。
- 書込先 = catch-ja.json / synopsis-slug-ja.json / synopsis-ja.json(anilist層) / genre-enrich-2425.json / manga-catch-index.json(全てpromote結線済)。

## ★2026-07-31: 短キャッチ requeue **完走(残0)**

`docs/production-diagnostics/catch-short-requeue.txt` は **空**。7/27の並列生成4,750作(平均19字)の作り直しは全数終了。
- このセッションで batch-0175〜0190 = 376作 + batch-0018/0086の取りこぼし14作 = **390作**を消化。
- ★取りこぼしの正体: 過去セッションで「消化済」としたバッチにも、字数/丸写しゲートで落ちて未適用のslugが残っていた。**最後は `catch-short-requeue.txt` を直接読み、`.cache/enrich-batches/*` を全走査してバッチ番号を逆引き**して片付けた(この手が最終確認に効く)。
- ★本番頁が無い49件は `catch-short-requeue-nopage.txt` に分離済(充填不能)。
- 消し込み = `python scripts/_rqdone.py <バッチ番号...>`。残数を表示する。

## ★次の柱 = 短あらすじ requeue (= 未着手)

対象 = `docs/production-diagnostics/synopsis-short-requeue.tsv`(**4,189件**)。列 = tier/len/has_caption/anilist_id/slug/title/current_synopsis。
- 内訳: severe×yes **820** / severe×no 1,210 / mild×yes 956 / mild×no 1,203。★**has_caption=no(2,413件)は素材ゼロなので書き直さない**(現状維持)。
- ★**severe×yes 820件のうち、材料(captions)が `.cache/enrich-batches/*` に在るのは285件だけ**(残535は `scripts/_enrich-captions.py --slugs a,b,c --live` で楽天から取り直しが要る=1.2s/req)。
  → **まず285件から着手**するのが効率的。slug→batch の逆引きは enrich-batches 全走査で出せる。
- ★★**書き込み層**: あらすじは2層あり promote は **anilist_id キーの synopsis-ja.json を優先**、slug側(synopsis-slug-ja.json)は空の時だけ fallback。`_apply-enrich-batch.py` は anilist層へ書く分岐を実装済(報告に「うちanilist層N」が出る)。旧仕様のまま slug側に書くと **silent空振り**。
- 誤りでなく「短い」だけなので**上書き可**。生成は60-120字・ネタバレ無し・最終巻丸写し禁止。

## ★生成の実装知見(字数ゲートを一発で通すコツ)

- ★**catchは「3節構成」で組む**: `def T(a,b,c): return a+'。'+b+'。'+c+'。'` で `T("[フック]","[状況]","[ジャンル/締め]")`。2節だと必ず42〜47字に落ちて48字下限で全滅する。3節なら50〜65字に安定。
- ★**synは82〜90字を狙う**(3節catchに字数を持っていかれてsynが76〜77字に痩せる回が出るため)。
- ★**バッチJSONを書いたら、その場で字数チェックを同時実行する**(生成scriptの末尾に
  `bad=[(k,len(v['catch']),len(v['synopsis'])) for k,v in d.items() if not (48<=len(v['catch'])<=74 and 78<=len(v['synopsis'])<=114)]` を print)。**このセッションは全8スライスでBAD=0・丸写し警告0**。
- ★**字数直しは必ず文字を足す**(同義語に置換すると長さが変わらず同じ違反を2〜3往復繰り返す)。
- ★**丸写し8gramは「書く前に」潰す**。captionから10字以上の連続一致が出そうな箇所を、語順・視点・語尾の総取り替えで崩す。★特に危ないのは **①作品タイトルや固有名詞の長い連なり**(「探偵オペラ ミルキィホームズ」「東洋のストラディヴァリウス」型=それ自体が10字超)→ 別の言い換えに逃がす、**②編集部の惹句**(「〜エンターテインメント」「〜ラブコメディ」「〜必至」)、**③キャッチコピーの丸ごと引用**。8字ちょうどは通るが10字超は避ける。
- ★**catchとsynの冒頭20字が完全一致すると VIOLATION**。catchはフック・synは設定から、と書き出しを必ずずらす。

## 1周の手順(2バッチ≒41〜50作が実用単位)

1. `python scripts/_rqdigest.py 0175 0176`(requeue掲載slugだけを旧catch/syn+全巻captionつきで整形出力。`CAPLEN=150`で十分)
2. `data/enrich-out-2026-07/batch-0175.json` 等に生成物を書く(**字数チェックを同スクリプトで同時実行**)
3. `python scripts/_apply-enrich-batch.py 0175 0176 --requeue`(検証)→ 通ったら `--apply`
4. `python scripts/_rqdone.py 0175 0176`(消し込み+残数表示)
5. `git commit` → `python scripts/_reflect-targeted.py --only "$(cat .cache/enrich_changed_slugs.txt)" --push -m "..."`

## 別作品混入(短キュー消化が誤り是正を兼ねる型)

短い catch/syn の作り直し中に「まるごと別作品」が見つかる型が続いている(4例):
`bakemono-yawazukushi`⇔`凪のお暇`(**相互スワップ**=生成batch内の対交換型) / `chika-chan-to` / `jaaku-na-tenshi` / `bakusou-kyoudai-let-end-goo-makkusu`。
- ★スワップは同一batch内でペアで起きる= 1件見つけたら**相手側(内容が指す作品)も必ず誤っている**。両方直す。
- ★訂正は必ず **synopsis-ja.json(該当aidキー)** を直す(slug側だけ直しても頁に出ない)。changelog = `enrich-requeue-changelog.jsonl`(op=synopsis_ja_fix)。
- 検出器の穴: `_synopsis-audit.py` の `len(syn_t) < 4` スキップで**該当779件**が flag されない(`docs/production-diagnostics/audit-followups.md` の D-2)。

## genre系 0218-0380 は実質完了(2026-07-30 調査)

4,071件中 3,948件はジャンル付与済。残121件は**学習漫画・画集・図録・評論・傑作選**が大半で **master32に該当キーが無い**ため空のまま据置が正しい(これ以上追わない)。掲載可否の裁定マター。

## 保留にする型(捏造せず空のまま残す)

傑作集/編集本(ワタシの川原泉)・材料が実質空(ヤバ盛/吉野家兄弟)・評伝など非漫画候補(闇の王子ディズニー)・**フィルムコミック**(ズートピア=掲載境界)。

全量一括WFはセッション枠を食うので不可([[enrich-catch-synopsis]] skill が正本)。Opusインラインで2バッチずつ。

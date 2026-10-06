---
name: daily_distill_hold_not_requeued
description: 【2026-10-06 実装済】日次は前回差分しか分類しない=初見で頁に入らなかった巻が二度と拾われない穴 → 再投入+予約頁seedへ直接追記+検出器#36で封鎖。初回回収153冊
metadata: 
  node_type: memory
  type: project
  originSessionId: 450de73b-b605-4986-907d-85f528e9a408
  modified: 2026-10-06T15:02:23.026Z
---

2026-09-02 日次蒸留で確認。`_preorder-increment.py` の fresh = latest − prev(ISBN差分)で、`--commit-prev` は
**保留(ドラフト化しなかった)ISBNも含めた full を prev に昇格**する。increment に hold の再投入は無い(grep で hold/triage 参照ゼロ)。
帰結: `preorder-triage.tsv` の `*_hold` 行(著者不明/ヨミ汚染/全巻回収不成立/slug生成不可)は**人が簿を消化しない限り永久に落ちる**。
月次蒸留で種2に入っても promote は元頁駆動なので新規シリーズは頁化されない([[orphan_series_promote_is_srcpage_driven]])。

2026-09-02 時点の保留9件(全て prev 在): みにくい小鳥の婚約(著者=出版社名) / 六歳の王女ですが(ヨミ汚染) /
ex_mid 7件(夜明けをつれてくる犬・腹パン系ダンジョン配信者・二度目の人生・S級ギルド・ハズレ職・侯爵令嬢リディア・不純すら純情=先行巻がキャッシュに無い)。

**Why:** 「保留=後で通す」つもりの行が、機構上は「二度と来ない」になっている。捏造しない方針で hold を増やすほど取りこぼしが溜まる。
**How to apply:** `_preorder-increment.py` に **hold再投入**を焼く: triage の `*_hold` ISBN のうち ISBN索引(`.cache/isbn-page-index.json`)に無い物を
full harvest から拾って fresh に足す(=毎回再分類→材料が揃った日に自然に通る)。ex_mid の「全巻回収不成立」は楽天 live 題検索の fallback を
`_preorder-gen-midfill.py` に足すと大半が通る(先行巻が2026年刊でローカルcacheに無いだけ)。
併せて未着手の小穴: `clean_kana` は題に巻数があっても**空白無しの末尾巻読み**(…デスイチ)を剥がさない(精霊聖女で手直し)。
KANA_VOLNUM レビューは slug 側しか見ないので title_kana に漏れる。[[intake_manifest_ledger_live]]

## 2026-09-07 追記: B柱(NDL)側の同型は封鎖した

`_distill_backward.py --plan` は `ai-todo.jsonl` を**毎回まっさら再生成**するので、worksheet に
`is_manga: false` と裁定を書いても**翌日また同じ候補が並ぶ**(A柱の hold と同じ「二度と消えない/通らない」構造)。
→ plan に **恒久除外簿 `data/seeds/preorder-deny.jsonl` の読み込みを追加**(A柱と同じ台帳を両柱で共有)。
裁定済み3件(クレヨンしんちゃんパニック=コンビニ再編集 / とっておきドラえもん=傑作選 / 花丸ハムスターほおぶくろセレクション=傑作選復刊)
を除外して **掲載可worksheet待ち 5→2**。残2件は caption 無しで genre が確定できず登録保留(捏造しない)。

★A柱(preorder hold の再投入)は**まだ未着手**= 上の How to apply がそのまま残タスク。

## ★2026-09-24 ユーザ「日次蒸留時に保留になっている物をみなおしてほしい」→ 一括見直し(commit a3d771be8)
- ★triage は**毎回上書き**なので、過去の保留は **git の全版(37版)を和集合**して拾う(1,046件)。
  現状 = 本番掲載済376(別経路で入った)/ドラフト化2/**未解決668**。書誌は過去harvest(`.cache/preorders/preorders-*.jsonl`)から659件引けた。
- ★保留行は**理由が slug 列にずれていた**(見出し8列に7列で書いていた)= reason 列は空。6か所を8列に是正済。
  過去版を読む時は hold 行だけ `slug` 列を理由として読むこと。
- **現行分類器で再分類**(スクリプトを別出力先へ sed で差し替えて実行=本番の日次台帳 classified.json/triage を汚さない):
  zokkan 196 / new1a 80 / new1b 43 / ex_mid 303 / skip 37。= 7月以降の分類器改良と頁の増加で**続巻の2割が今なら通る**。
  - 続巻: **版違い疑い17件は自動適用から外す**(題に 愛蔵版/完全版/大全集 等があり頁題に無い=通常版に混ぜてしまう)。
    残り179件を apply-zokkan で適用 → 種4 +152冊/148頁。preorder-pages 由来16件は直接追記(上下は 上/下ラベル+発売済なら completed)。
  - 反映で**既定の slug 改名が33頁ぶん同時に適用**された(alias は全部既存)→ prune 台帳に旧slugを足した。
- **残り**(`docs/production-diagnostics/preorder-hold-review-2026-09-24.tsv`): ex_mid 303 / new1a 80 / new1b 43
  = preview ドラフト生成→ユーザ確認が要る(未実施)/ 版違い疑い17 / 巻番号不明・同巻既在 11。
- ★**構造穴(再投入が無い)は依然未実装**。次にやるなら: 保留を永続台帳に積み、`_preorder-increment.py` が毎回
  「未解決の保留」を fresh に混ぜて再分類する(今回の和集合+再分類を自動化する形)。

## ★2026-10-06 実害の実例(mangaseek の発売日一覧との突き合わせで発見 = [[competitor_mangaseek_teardown]])
- 10/6発売の **カクリキ2・猩猩姫3・ホイホ・ホイホイホ3・呪具師15** は 10/3 の full harvest(`preorders-latest-full.jsonl`)に**全部在る**のに頁に無い。
  4冊とも 10/3 の増分(`preorders-latest.jsonl`)には居ない=もっと前の回で初見→適用されず→以後二度と分類されない。
  3冊は**triage のどの版にも出てこない**(保留簿にすら載らない経路がある)。呪具師15は 8/26 に ex_mid(頁が2枚ある重複のせい?)。
- 9/17発売の **4軍くん(仮)14** は 7/20 に ex_mid のまま(頁は13巻まで在る)。
- ★穴は「hold」だけでなく**「初見で適用されなかった物すべて」**。再投入の対象は triage の hold に限らず、
  「full harvest に在る × ISBN索引に無い × preorder-deny に無い」全件にするのが正しい(=簿に載らない経路も拾える)。
- 同じ「拾ったのに頁に無い」は 7/24 の種4-auto全消し由来の消失も拾える([[seed4_auto_wipe_accident]])= 検出器を1本にまとめられる。

## ★2026-10-06 実装済み(GO)= 再投入 + 予約頁への直接追記 + 検出器#36
- `_preorder-increment.py`: prev在でも「本番頁(ISBN索引)/種2/予約頁seed/ドラフト/ISBN除外簿」に無いISBNを毎回 fresh へ戻す(`_requeue`)。
  ★**種4は「載っている」に数えない**(下の③)。特装版は戻さない。過去draft題の除外から**本番頁が在る題を外す**(deny は常に効かせる)。
- `_preorder-classify.py`: `_requeue` 行は**続巻(zokkan)の時だけ**適用へ。新作/途中巻は `requeue_hold`(簿のみ)=backlogをドラフトに水増ししない。
  著者照合で**括弧書き(スタジオ注記)を剥がし全角「／」でも分ける**(孟倫（SDwing）/Stonehead(AKEO STUDIO) で ex_mid に落ちていた6冊)。
- `_preorder-apply-zokkan.py`: 予約頁で作られる頁(`is_preorder_produced`=preorder-pages在・data/manga と source-pages に元頁無し)は
  **series_key が引けても seed へ行差し込み**(読み直し検算・記帳 preorder-page-zokkan-changelog.jsonl・退避)。巻番号順に処理・途中欠けは通し遠い飛び番だけ止める。
- 初回の回収: 再投入695 → 続巻182 + 欠番補充10 → 種4 122冊 + 予約頁へ 30+95冊(153冊すべて頁に出たことを検算)。保留38=新装版/愛蔵版/大全集/巻番号なし単巻。
- ★見つかった型3つ: ①予約頁出身の頁の続巻は「過去draft題」除外で**分類前に消えていた**(triageにも出ない)②**予約頁で作られる頁は種4を読まない**
  =作品が後から種2に入っても seed が頁の正。種4に入れた97冊が出ていなかった ③ホイホ・ホイホイホ「/3」= 斜線区切りの巻表示は分類器が読めず skip(個別追加済・型は未封鎖)。
- 監視 = 月次サニティ#36 `_audit-harvested-not-on-page.py`(A=種4の git 全版 / B=予約の全スナップショット+累積履歴 / C=予約頁seed / D=保留簿の git 全版 のうち ISBN 索引に無いもの)。
- ★2026-10-07 追記: 再投入は**予約の窓(未来)の中しか効かない**。発売日を過ぎて窓から外れた取りこぼしは full/prev が毎回上書きされるので何も残らなかった
  → `_preorder-increment.py` が初見ISBNを `.cache/preorders/harvest-history.jsonl` に累積追記(初期化=手元の全スナップショット6,491件)。
  これで見えた発売済み続巻31冊(9/17の4軍くん(仮)14・幼馴染は一卵性の獣9・ドラゴンの胃3、9月のみいちゃん以外24冊等)と、
  頁があるのに分類器が続巻と判定しない予約10冊(題の括弧・副題で照合が外れる)も適用済み。★みいちゃんと山田さん7 = 同日2ISBN(頁は…7444)=保留が正。
  保留簿の古い hold 行は**著者列が空**(列ずれ時代)= 著者照合だけだと拾えない → 検出器は「題が1頁だけ+巻が max+1..+3」で拾う。
  ★手元のどの記録にも無かった3冊(幼馴染9・実は性欲スゴイ3/4)は楽天予約の取得自体に掛かっていなかった= 外部一覧(mangaseek)でしか見えなかった層。

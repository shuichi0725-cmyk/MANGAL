---
name: preorder_date_drift_sutegoro_type
description: 【型・検出器+適用器・36巻適用済】すてごろブッチ型=予約巻の発売日が延期されても追随せず古い日付のまま。根因は promote の予約頁合流ブロックに release-date-override が通っていなかった(予約頁は本流を通らない穴の5件目)。適用は楽天とNDLが一致した行だけ
metadata: 
  node_type: memory
  type: project
  originSessionId: f086dd6b-7485-4639-a714-c55609a075cc
  modified: 2026-09-04T13:45:20.054Z
---

2026-09-04 ユーザ発見。「**画像が古いままだと思ったら発売日が違う。変わったのかも**」
= すてごろブッチ! (9784091543295) 本番 **2026-08-28** / 楽天・NDL **2026-09-28**(1か月延期)。
2026-07-09 の予約ハーベスト時の値を握ったままだった。

★**症状の読み方**: 「もう発売済のはずなのに書影が仮(文字だけの .gif)のまま」= **延期のサイン**。
書影の柱([[cover_source_affiliate_only]] / placeholder-cover-refresh)を疑う前に**発売日を疑う**。
仮書影は発売前に出るものなので、発売日が未来へ動いていれば仮のままなのが正しい。

## 根因は2層

1. **追随機構が無かった**。予約(未発売)の巻は後から発売日が動く(延期/前倒し)のに、
   既に本番に居る巻の発売日を再取得して更新する処理がどこにも無かった。
2. ★**promote の予約頁合流ブロック(`_promote-bulk-v2.py` L4108付近)に release-date-override が
   通っていなかった** = cover-override / genre-enrich / genre-append / magazine-corrections に続く
   「**予約頁は本流を通らない**」穴の **5件目**。override seed に正しく書いても永久に届かない状態。
   → 2026-09-04 に cover-override と同型(キーが在れば必ず勝つ)で結線。
   日付が動いた時は頁の **出版年レンジも追随**(★現在値が巻から導ける時だけ=手入力を壊さない)。

★**次に同じ穴を探す時**: 予約頁合流ブロックが通している seed と本流が通している seed を突き合わせる。
「予約頁にも意味があるのに(B)に無い層」が次の穴。

## 道具

- 検出 `scripts/_audit-preorder-date-drift.py`
  証拠 = **日次の楽天予約ハーベスト** `.cache/preorders/preorders-latest-full.jsonl`(漫画001001の未来〜今日 全量)。
  本番 manga.v2 の release_date と ISBN で突合するだけ = **live を叩かない**。
  分類 POSTPONED / ADVANCED / MINOR(±3日) / NOT_LISTED / OURS_EMPTY。層(fix_layer)も出す。
- 適用 `scripts/_apply-preorder-date-drift.py` (既定 dry-run / `--apply`)
  → `release-date-override.jsonl` 純粋追加 + PREORDER seed / 種4 seed の当該行も同値に外科的更新
  → `.cache/preorder-date-drift-stems.txt` を `_reflect-targeted.py --only` へ。
- 日次蒸留の**手順10.6**に組込済(harvest直後が一番安い)。CLAUDE.md の検出器一覧にも登録。

## ★ゲートの肝(ここを外すと誤適用する)

- ★**NDL(ISBN直引きの出版予定日)と楽天が一致した行だけ適用**。
  理由 = **±1日のズレは「NDL/MADB=奥付の発行日 / 楽天=店頭に並ぶ日」の既知の仕様差**。
  初回実測で19件(KADOKAWA/秋田)が該当し、機械的に楽天へ寄せていたら**19件を誤って書き換えていた**。
  NDL がこちらの値を支持している = **変更しないのが正解**。
- ★楽天 salesDate の「**頃**」= 楽天も日付を確定できていない印(**ハーベストの43%**)。
  ただし**単独では棄却しない**(頃つき10件のうち8件はNDLが同じ日を持つ=実在の予定日)。
- NDL に記録が**無い**のは「食い違い」ではなく「未登録」。現在値も楽天由来(PREORDER seed /
  種4 source:rakuten)と seed で確認できれば**同一源のリフレッシュ**として採る(`src: rakuten-only` と記帳)。
- 層が CANONICAL / edition-overrides の行は保留(override が最終値に効かない経路
  = [[release_date_change_side_effects]] ②)。同ISBNが複数頁に在る行も触らない。

## 初回実測 (2026-09-04)

芯30 → **36巻 / 30頁を適用**。ISBN消失0・増加0(検算済)。
- すてごろブッチ! 2026-08-28 → 2026-09-28
- さくらいろダイアローグ2 2026-07-15 → 2026-11-16(124日) / おせん 和な女7 → 2027-03-24(212日)
- 諸星大二郎短編集成 = **配本順の変更**。1巻が「第12回配本(2027-11)」から先頭(2026-11-30)へ、
  7〜12巻が1枠(2か月)ずつ後退。楽天/NDLとも一致し、隔月の連なりが破綻なく揃う。
- NOT_LISTED 3件(楽天ハーベストに居ない)= しずくちゃん45 はNDLが本番と一致で問題なし、
  残り2件(加害者家族の真実2 / 魔王様、溺愛しすぎです！2)は要人裁定。

## 副産物 = ★未着手の宿題

予約頁 seed の **year_started が「ハーベストした年」**になっている頁が **2,029中218頁**。
実例 おせん 和な女 = 1巻2023-01なのに year_started 2026 / 9番目の武蔵 = 2020なのに2026。
今回日付を直した7頁だけは巻の最古年へ是正済。残り**211頁は未適用**(機械で min(巻年) に直せる)。

関連: [[release_date_change_side_effects]] [[wikipedia_release_date_is_authoritative]]
[[orphan_series_promote_is_srcpage_driven]] [[feedback_cover_oddity_signal]] [[feedback_one_bug_means_a_class]]

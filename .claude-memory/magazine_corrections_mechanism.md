---
name: magazine_corrections_mechanism
description: 【新設】掲載誌の per-case 上書き seed = magazine-corrections.yml。種3のmagazineは根拠なしのAI fillで誤りが多い。スーパージャンプ調査で空欄106/別誌20を検出(未着手)
metadata: 
  node_type: memory
  type: project
  originSessionId: 164c5cf9-b3fb-40f8-a19c-7cc4f6403843
  modified: 2026-08-07T00:51:21.710Z
---

2026-08-07 新設。夢幻の如く(スーパージャンプ連載)が `weekly-young-jump` になっていた件から。

## 機構
- **`data/seeds/magazine-corrections.yml`**(slug→{magazine, source, evidence, added_at})。
  promote が `_MAG_CORR` で読み、種3/brand推定より**最優先**で上書き。
- ★値は **`data/magazines.yml` のキー**であること。未登録キーは**警告を出して無視**する安全弁つき
  (誤キーが本番に漏れない)。スーパージャンプは雑誌マスターに無かったので `super-jump` を新規登録した。
- なぜ要るか= magazine は種3(series-supplement-v2.yml)のAI fill由来で根拠がない。
  種3は純粋追加only・既存key変更禁止(月次蒸留のabort条件)なので、種3を汚さずここで上書きする。
  **status が同じ理由で不信任され `status-corrections.yml` が作られたのと同型**。

## スーパージャンプ調査の結果(調査のみ・是正は未着手)
worklist = **`docs/production-diagnostics/magazine-super-jump.tsv`**
ja.wikipedia「スーパージャンプ」掲載作品一覧 **144作** × 本番の magazine:

| 判定 | 件数 |
|---|---|
| super-jump 済 | 1(夢幻の如く=是正済) |
| **magazine が空** | **90**(題+著者が完全一致) + 16(著者から引き当て) |
| **別の雑誌が入っている** | **20**(要per-case) |
| 本番に頁が見当たらない | 16 |

★**空欄のほうが圧倒的に多い**(106件)。「誤った雑誌」より「そもそも埋まっていない」が主症状。

## ★20件を一括上書きしてはいけない理由(実地で確認)
- **移籍**(両方とも事実): ふんどし刑事ケンちゃん・赤龍王・マーダーライセンス牙 = 週刊少年ジャンプ→スーパージャンプ。
  magazine は1つしか持てないのでどちらを出すかは判断マター。
- **頁の粒度違い**: 「コブラ〜聖なる騎士伝説」は本番 `cobra`(COBRA本編・WSJ)に含まれる。
  「世紀末リーダー伝たけし!完結編」も本編頁に吸われている。
- **同名別作の疑い**: `zero`(ビッグコミック)・`jin`(ヤングジャンプ)が本当に同じ作品か未確認。
- 明らかに直すべき分= GOLDEN BOY/世紀末博狼伝サガ/緋が走る/銀のアンカー/ふぐマン/トクボウ朝倉草平 等。

## 横展開の余地
雑誌記事の「掲載作品一覧」×本番magazine の突合は**どの雑誌でも同じ手順で回せる**。
手順= Wikipedia掲載作品一覧をWebFetch → `.cache/prod-title-mag.tsv`(全頁のslug/題/magazine/著者を1パス)と
題+著者で突合 → 空欄/別誌/未特定に3分類。題の表記差は**著者軸で引き直す**と拾える(JIN・バーテンダー等が
題の完全一致では落ちた)。

関連: [[data_assets_inventory]] [[feedback_accuracy_is_the_goal]]

## 2026-11-04 一括是正(忘却バッテリー=少年ジャンプ+ のユーザ報告「類似も探して修正して」)
- 原因: 雑誌マスタに少年ジャンプ+/ジャンプSQ/月刊少年ジャンプ等が**無く**、種3のAI埋めが集英社の少年漫画をまとめて `weekly-shonen-jump` にしていた(WSJ表示1,113頁のうち434頁が他誌)。他社でも ヤンジャン↔サンデー・マガジン↔チャンピオン の取り違えあり。
- 方法(機械→割れた分だけ人): ja.wikipedia 13記事(WSJ/マガジン/サンデー/チャンピオンの連載作品一覧+ジャンプ+/SQ/月ジャン/Vジャンプ/最強/フレッシュ/YJ/UJ/増刊)の wikitext を取り、
  「記事の1行(表なら1行分)に 題 と 著者名 が並ぶ」で所属判定。 自動 = 載る一覧が1誌だけ+開始年が合う(頁年が 一覧年-1〜+3)+出版社一致+移籍注記なし。
  残りは表の注記(「←『MJ』…より継続」=初出は月刊少年ジャンプ 等)を読んで1件ずつ。
- ★誤判定の型(次にやる時の注意): ①記事の**本文(沿革の文)**に題と著者が並ぶ行も当たる(ダンダダン等=正解だったが根拠としては弱い) ②スピンオフ/続編の行に**原作として**名前が出る(怪獣8号が最強ジャンプのRELAX行に当たり「複数誌」で漏れた) ③**賞の表**(|銅||3||題||)に他社作品が当たる ④箇条書きの**説明文中の別作品**(キャプテン行の「『キャプテン2』として復活」) ⑤同題の別作品(鳥山明○作劇場1983 vs Vジャンプ1992=年で弾く)。
- 結果: 雑誌マスタに7誌追加(shonen-jump-plus / jump-sq / monthly-shonen-jump / saikyo-jump(児童) / v-jump / fresh-jump / tonari-no-young-jump)。 magazine-corrections.yml に **736頁**(うち空欄→ジャンプ+ 255)。commit 456e5abd7e / f2f99e273a / 7d42a2cd00。記録 = data/seeds/magazine-fix-changelog.jsonl、退避 = .cache/magazine-fix-bak-*。
- 未解決 = `docs/production-diagnostics/magazine-unresolved-2026-11-04.tsv`(1,414頁): 要判断40(並行連載・移籍・同名・増刊)と、**どの一覧にも当たらない**頁(YJ374/マガジン311/チャンピオン267/サンデー235/WSJ185 = 正しいかもしれないし誤りかもしれない=未確認)。 空欄で一覧に載る頁(約1,170)はジャンプ+以外は埋めていない。
- 手元の道具は scratchpad(消える)だったので、やり直す時は上の方法を再実装する(記事は API action=parse&prop=wikitext・_wiki_host のロック・UA 必須)。

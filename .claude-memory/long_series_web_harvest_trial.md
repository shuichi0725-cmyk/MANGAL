---
name: long-series-web-harvest-trial
description: "【進行中】巻数5以上・見える要素3以下 11,399頁の改善。巻数上位30頁でHaiku Web収集(element-harvest auto)+付与案の試し(2026-10-29)の数字・型・裁定待ち。流し方の罠(while read の標準入力で claude -p が固まる)"
metadata:
  node_type: memory
  type: project
  originSessionId: 167f0cda-b9f6-41b5-bc39-8d561ce1d570
  modified: 2026-10-29T09:50:33.024Z
---

2026-10-29 ユーザ「巻数が五巻以上あるのに要素が三以下(隠し以外)を改善したい」→「haikuを使って情報収集する仕組み」→「巻数の多いものから試したい」(ミナミの帝王=料理だけ、が発端)。[[element-review-queue-state]] [[element-harvest-pillar-state]] の続き。

## 実測(索引 69,789頁)
- 対象 11,399頁(max_edition_volumes>=5・索引 themes<=3)。うち見直し流し済み 7,905(手元の巻紹介文あり)/ 未=経路W 3,494(材料0字 2,808)。
- ★長期連載の型: 巻ごとの紹介文=各編の出来事 → 見直しの判定が「その編だけ」で全部落とす(ミナミ=刑事・極道・ヤクザ…全落ち、借金は4巻目以降でネタバレ扱い)。作品全体を説明する文(Wikipedia・評論)が無いのが根本。
- ミナミの料理 = `data/seeds/tag-rakuten.yml` の Food(夏の楽天あらすじ機械付与)= 誤り。tags-hide で消せる(未実施・裁定待ち)。

## 30頁の試し(置き場 .cache/element-harvest/_trial-long = EH_ROOT・本番/見直しの束に不干渉)
- 道具: `EH_ROOT=… _element-harvest.py auto <stem> --model claude-haiku-5-5` → `_element-assign.py run <stem>`(既定 Sonnet)。runner = `_trial-long/run.sh`。
- 結果: 見える要素 計45→95語(案を足した和)・4語以上 9/30。表0語のまま 6(なんと孫六・山口六平太・ゼロ=材料0字・Dreams・かりあげクン・水木大全集)= 判定が「一度の出来事/脇役/趣味の一つ」で落とす。
- 費用: 収集 Haiku 計 $0.47(1作 約8.7万読み込み・約2分)/ 付与 Sonnet 計 $2.42 = **費用の8割は Sonnet の付与**。
- 語彙に無くて隠れた語: 闇金・高利貸し・トイチ・取り立て・同心・捕り物・記者・二重生活・代打・ロードレース・熟年・逆境・魔球・番狂わせ・ブラックジョーク 等。Historical(英語のまま)2件=訳の穴。
- 気になる案: 静かなるドン=ヤクザ・任侠・極道(重なり)/ サザエさん=学習 / NARUTO 和12語(上限10超)。

## ★Web材料の器(2026-10-29 ユーザ発案「haikuがネットで集めた情報を入れる器を作ってほしい。いつ。どこで、情報をえたか。漫画ごとに情報を得るだけまず進めてみる」)
- 道具 `scripts/_web-material.py` status / run --n N / run --stems a,b [--redo] / show <stem> [--text] / import <EH_ROOT>。集めるだけ(判定・付与しない)。
- 置き場 `.cache/web-material/`(store/<stem>.json=回ごと全部残す・work/=EH_ROOT で raw 全文・runs.jsonl)。★ユーザ裁定「非公開、ローカルだけでよい」「DはつかわないでCでよい」= git に入れない・D ドライブを使わない。
- 試し30頁は import 済み。ゼロは search-titles.yml(検索用の題)で集め直し 0→2,770字。
- ユーザ「入れるのは良いという意味だがまだ色々試したい」= 30頁の付与案の適用は可だが保留中。
- ゼロの頁の穴(題「ゼロ」・原作 愛英史なし・掲載誌 big-comic→正しくはスーパージャンプ)は per-case 未着手。

## ★流し方の罠(2026-10-29 実踏)
- `while read s; do python … ; done < list` で回すと、子が一覧ファイルを標準入力に継いで claude -p が固まる(直接実行は90秒で完走)。→ 各コマンドに `</dev/null`。
- Python が書く一覧は CRLF(`open(...,'w')`)→ bash の read で stem 末尾に \r。
- 止めた bash の流れが生き残り2本並走した。止める時は CommandLine に `_trial-long|_element-` を含むプロセスを全部 taskkill /T。
- `_lean_claude.ask` の timeout が Windows で効かず30分固まった → Popen+taskkill /T に直した(commit e412c46d19)。

---
name: element-harvest
description: 要素収集して <作品>/要素収集続けて=ジャンル・要素を付ける前段の「材料集め」。AniListとWikipediaは道具が自動、百科・公式・考察・ネタバレは魚で検索し運転者は番号で指すだけ(文面は打たない)。付与しない・本番に書かない。Haiku 5.5運転前提(2026-10-08 試行中 v0.1)
---

# 要素収集 (= トリガー「要素収集して <作品名>」「要素収集続けて」)

## これは何か

ジャンルと要素を増やす工程の**前段**。Web から材料を集めて束にするだけ。

- ジャンルも要素も**付けない**(付けるのは後段の別工程)。
- 本番データ(`data/manga.v2` / `.preview-data` / seed / 索引)には**一切書かない**。反映もしない。
- 試金石 = 『やはり俺の青春ラブコメはまちがっている。』(2頁)。ここで納得が出るまで他の作品へ広げない。

## 役割分担 (★最重要)

| 道具 `scripts/_element-harvest.py` | 運転者 (Haiku) |
|---|---|
| 検索・取得・保存・同定の検査・止め札・robots・上限・束づくり | **番号で指すだけ**: どの検索結果を開くか / どの段落が材料か / 打ち切るか |

★運転者は材料の**文面を打たない・要約しない・直さない**。`pick` は段落番号だけを受け取り、文面は保存済みの本文から道具が切り出す。

## 手順 (道具が毎回「次にやること」を出す。それに従えば進む)

```
python scripts/_exists.py --title <題の一部>                      # stem(= data/manga.v2 のファイル名)を引く
python scripts/_element-harvest.py open <stem> --model haiku-5.5  # 始める(途中からの再開も同じ)
```

`open` が自動でやること: 作品カードの表示 / AniList の関連作(原作小説・アニメ)のタグ収集 / Wikipedia の記事とカテゴリの取得、「作風」「あらすじ」「登場人物」の節の採用。

続けて種別ごとに回す:

```
python scripts/_element-harvest.py search <stem> <種別>               # 魚で検索(定型クエリ)
python scripts/_element-harvest.py fetch <stem> <検索ID> <番号,番号>   # 開く頁を番号で指す
python scripts/_element-harvest.py show <stem> <出所> --range 5-12    # 段落を全文で読む
python scripts/_element-harvest.py pick <stem> <出所> <段落> --as <役割>  # 材料になる段落を指す
python scripts/_element-harvest.py unpick <stem> <採用番号>            # 指し間違えた時の取り消し
python scripts/_element-harvest.py skip <stem> <出所> --why <理由>     # 採らない頁
python scripts/_element-harvest.py none <stem> <種別> --why <理由>     # その種別は材料なし
python scripts/_element-harvest.py done <stem>                        # 束を作って報告
python scripts/_element-harvest.py status <stem>                      # いまの進み具合(「続けて」の時はここから)
```

- 種別 = `wiki` / `公式` / `考察` / `ネタバレ`
- 役割 = `物語` / `作風` / `人物` / `主題` / `展開` / `タグ`
- skip の理由 = 別作品 / 薄い / 書誌や商品情報だけ / 重複 / 本文なし / その他
- none の理由 = 検索に出ない / 出たが別作品 / 取得できない / 見たが薄い
- ★日本語の引数が通らない時は番号か英名でよい(`official` `analysis` `spoiler` / `story` `style` `people` `theme` `plot` `tags` / `--why 2`)。

## 種別ごとの進め方

| 順 | 種別 | 取れるもの | 開く頁の選び方 | 採る段落 → 役割 |
|---|---|---|---|---|
| 1 | wiki | 人物の性格・属性、他サイトの人が付けたタグ | アニヲタWiki の**作品記事**と**主人公の記事**。出なければ `search <stem> wiki --query "<主人公の氏名> アニヲタWiki"` | 「タグ一覧」の段落 → `タグ` / 概要・人物像 → `人物` |
| 2 | 公式 | 出版社・掲載誌・アニメ公式の紹介文(作品の芯) | 出版社・掲載誌・公式サイトのドメイン。電子書店の作品頁も可 | STORY・内容紹介 → `物語` / CHARACTER → `人物` |
| 3 | 考察 | 何を描いた作品かの言葉 | 1話ごとの感想より、**作品全体**を論じている頁 | 主題を述べている段落 → `主題` |
| 4 | ネタバレ | 中盤以降の展開 | 全巻・最終回まで書いた頁 | 展開の要約 → `展開`(ネタバレ印が付く) |

- 採用は各種別 **1〜2頁**(wiki は3頁まで)。1頁採れたら、2頁目は「1頁目に無い情報(人物・主題)」が在る時だけ。
- 検索は各種別3回まで(定型2 + `--query` の自由文1)。取得・字数の上限は道具が数えて止める。

## 採る段落・採らない段落

**採る**: ①どんな話か(設定・主人公の境遇・舞台) ②作風や雰囲気を述べた文 ③主要人物の性格・関係・属性 ④何を描いているか(主題) ⑤他サイトのタグ一覧

**採らない**: 発売日・巻数・ISBN・価格 / スタッフ・声優・主題歌 / 売上・ランキング・受賞の羅列 / グッズ・イベントの告知 / 書き手の近況・挨拶 / コメント欄 / **別の作品の紹介** / 目次・メニュー

- ★迷ったら採らない。
- `pick` の後に道具が「採った文の頭」を出す。思った段落と違ったら `unpick`。
- 1頁から採れるのは2,500字まで(Wikipedia は5,000字)。一度に指せるのは12段落まで。

## 同定 (別作品の混入を防ぐ)

`fetch` すると道具が判定を出す。

| 判定 | 意味 | すること |
|---|---|---|
| OK | 題と著者名が頁に在る | そのまま `pick` できる |
| 要確認 | 題は在るが著者名が無い | `--same "<語句>"` を付ける。語句は**その頁と、こちらのデータ(open で出たあらすじ等)の両方に在る4字以上**(例: 主人公の氏名)。道具が両方を検査する |
| 別作品の疑い | 題が頁に無い | 採れない。`skip --why 別作品` |

★同じ題の別作品・続編・スピンオフ・ゲーム版に注意。`open` のカード(著者・版元・年・あらすじ)と食い違う頁は skip。

## NEVER (= Haiku 安全設計)

- **WebFetch / WebSearch / `_tinyfish.py` を直接使わない**。取得は必ずこの道具から(生の文面を保存するため。直接取ると止め札も効かない)。
- 道具が「取らない」と言った頁(止め札・robots・対象外の種類)を、**別の手段で取りに行かない**。
- 材料の文面を自分で打たない。要約・言い換え・補足を書かない。
- ジャンル・要素を付けない。自分の知識で段落を選ばない(頁に書いてあることだけが材料)。
- 本番データ・seed・索引に触らない。反映(`_reflect-targeted.py`)・デプロイをしない。
- 「■ 中断」が出たら(魚・Wikipedia・AniList の失敗)**その場で止めて報告**する。繰り返し叩かない。
- 取れなかったことを `none` にしない。`none` は「開いて読んだが材料が無かった」時だけ。
- 上限を回避しない(別の種別名で取り直す等)。

## 終わったら

1. `done` の出力(「== 要素収集の報告 ==」以下)を**そのまま貼って**報告する。自分の言葉で言い換えない。
2. 台帳だけ commit+push する:
   `git add data/element-harvest/ledger.jsonl && git commit -m "要素収集: <題> (v0.1/haiku-5.5)" && git push`
3. 困った所・道具が不便だった所があれば、報告の後に箇条書きで足す(試行中なので歓迎)。

## 置き場

| 物 | 場所 | git |
|---|---|---|
| 作業中の状態・取得した本文・段落・束 | `.cache/element-harvest/<stem>/`(`state.json` `raw/` `paras/` `material.md` `material.json`) | 追跡外 |
| 台帳(1作1行・文面は入れない) | `data/element-harvest/ledger.jsonl` | 追跡 |
| やり直し前の版 | `.cache/element-harvest/_archive/<stem>-<日時>/` | 追跡外 |

## 取らないサイト (道具が断る)

- **止め札**: BookLive / BOOK☆WALKER / Amazon(`scripts/_site_gate.py` の `DENY`。足す・外すはユーザ裁定)
- **robots.txt が全クローラか Claude を拒んでいる頁**(実測 2026-10-08: ピクシブ百科事典・マンバ・ebookjapan)
- **材料にしない種類**: 二次創作・投稿小説(pixiv 等)/ Q&A・掲示板 / SNS・動画 / 海外の wiki / 売り場(`_element-harvest.py` の `NOT_MATERIAL`)
- 魚が拒まれた実績(止め札ではない・取れない時がある): ニコニコ大百科(403)/ 紀伊國屋(届かない)

可否だけ見る: `python scripts/_site_gate.py <URL>`(頁は取得しない)

## Opus 側 (試行の点検 = トライアンドエラーの回し方)

1. Haiku の報告を受けたら束を読む: `.cache/element-harvest/<stem>/material.md` と `state.json`。
2. 正解表の語が材料に在るかを数える:
   `python scripts/_element-harvest.py probe <stem> "シスコン,ぼっち,部活,自己犠牲,…"`
3. 見る点:
   - 別作品・二次創作が混ざっていないか
   - 採った段落が書誌・告知・無関係な文でないか
   - `none` の理由は妥当か / 開かずに済ませた検索結果に良い頁が無かったか(`state.json` の `searches`)
   - 道具の案内で迷った跡が無いか(同じ命令の繰り返し・上限に当たった所)
4. 直すのは道具かこの手順書。直したら `VERSION` を上げ、`open <stem> --fresh` でやり直させて比べる(旧版は `_archive` に残る)。
5. 俺ガイルで納得が出たら、型の違う既知作品を数作で同じ確認 → その後に付与の工程(別 skill)を作る。

## 関連

- 止め札・robots・サイト別間隔の門 = `scripts/_site_gate.py`
- 魚 = skill `tinyfish` / 外部アクセスの戒め = memory [[booklive_access_incident]] [[bookwalker_harvest_forbidden]]
- 経緯・決めたこと・未決 = memory [[element_harvest_pillar_state]]

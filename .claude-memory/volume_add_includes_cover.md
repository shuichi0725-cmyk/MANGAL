---
name: volume_add_includes_cover
description: 【厳守】巻を足す時は書影も一緒に足す(ユーザ指示 2026-09-09)。種4追記だけで終えない。取得は構築URL→HTTP検証→ダメなら楽天API、covers.jsonl.gzへ追記して再反映
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 814118b1-fc50-4622-83ea-59182e2023e1
  modified: 2026-09-09T12:51:11.242Z
---

2026-09-09 ユーザ指示: **「この追加のときは書影も一緒に追加して」**。

## なぜ

種4(`volumes-supplement.yml`)に巻を足すと頁には出るが、**covers seed に無いISBNは書影が空のまま**になる。
その巻だけ書影が欠けた状態で本番に出てしまう(実例: つまりそういうコト。1巻)。
**巻の追加は「書誌+書影」で1セット**。片方だけで終えない。

## 手順(巻を足す作業の一部として必ずやる)

1. 種4へ巻を追記(series_keys は既存ISBNから `.cache/db-v2.sqlite` 逆引き / imprint は既存版に合わせる)
2. ★**書影URLを取る**。手法は `scripts/_cover_gap_fill.py` と同じものを使う(自分で発明しない):
   - ①構築URL `https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/<ISBN下4桁>/<ISBN><suffix>?_ex=300x300`
     を suffix `.jpg` / `_1_2.jpg` / `_1_4.jpg` の順に **HTTP検証**(Content-Type が image かつ 2000バイト超)
   - ②全滅なら楽天API(`outOfStockFlag=1`)の `largeImageUrl` → `?` より前 + `?_ex=300x300`
   - ★**検証せずURLを組んで書かない**。実体が無ければ壊れた画像になる
   - 解像度は `?_ex=300x300`([[cover_resolution_policy]] 下げるな)
3. `data/seeds/covers.jsonl.gz` へ1行追記。**キーは `isbn13` / `cover_url`**(`url` ではない)。
   形式: `{"isbn13": "...", "cover_url": "https://..."}`。追記前に既存重複を確認・バックアップを取る
4. `_reflect-targeted.py --only <stem>` で再反映 → 全巻の cover_url が埋まったことを**数字で確認**
5. preview へコピー([[percase_fix_always_to_preview]])

## 注意

- ★`_apply-covers-stage.py` に `--help` は**実装されていない**。打つと**そのまま実行される**
  (2026-09-09 実踏: 無関係な頁に書影が1つ入った。promote 再生成で復元した)。
- ★**covers seed に在るのに promote が充填しない巻がある**(三つ目がとおる6巻 9784061087064)。
  = 書影が出たり消えたりする経路が残っている。未調査。

関連 [[cover_source_affiliate_only]] [[cover_resolution_policy]] [[volgap_fill_pipeline_2026_09]]

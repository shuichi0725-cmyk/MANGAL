---
name: voldesc_next_slice_todo
description: 巻説明つくって=/clear後の再開点。★巻数順(ファイル名順から切替)・1作ずつ完走
metadata: 
  node_type: memory
  type: project
  originSessionId: 2e629c9e-d55a-4074-a6ec-d0691965d657
  modified: 2026-07-31T06:27:39.805Z
---

★保留タスク: ユーザが `/clear` 後に「巻説明つくって」で再開する。**2026-07-31 に選定方針が変わった**。

## ★選定方針の変更(2026-07-31 ユーザ指示) = ここが最重要

- **巻数順**(未生成巻の多い作から)に切替。従来の「ファイル名順=端から」は**やめる**。
- **1作品ずつ、その作を全巻終わらせてから次へ**(ユーザ明示。[[voldesc_finish_started_series]] と同じ)。
- ★これは [[feedback_no_popularity_priority]](人気順禁止)に**反しない**。人気(AniList pop)ではなく
  巻数で並べる。理由=**歩留まりが実測で5倍以上違う**(下記)。この判断を蒸し返して
  ファイル名順へ戻さないこと。

## 実測(2026-07-31)

| 方式 | 選定 | caption有 | 歩留まり |
|---|---|---:|---:|
| ファイル名順(旧) | 33〜57作/約100巻 | 0〜12巻 | **約10%** |
| **巻数順 上位20作** | 20作/2,719巻 | **1,461巻** | **54%** |

長期連載ほど楽天の紹介文が揃っている。

## 現在地(2026-07-31 時点)

- seed `data/seeds/volume-desc-ja.jsonl` = **5,788巻 / 1,374作品**。
  ※旧メモの「11,703」は誤り。現物の行数が正。
- 材料なし台帳 `.cache/voldesc/no-material.txt` = 589件。
- 未生成の全体 = **67,106作 / 234,090巻**。
  100巻以上14作(1,765巻)/50巻以上75作/30巻以上384作(16,794巻)/10巻以上4,738作(80,828巻)。
- ★`.cache/voldesc/materials.jsonl` に**上位20作ぶん caption有1,461巻**が既に載っている(未生成)。
  ただしスライス毎に上書きされるので、再開時は下記手順で取り直すのが安全。

## 再開手順

```
python scripts/_voldesc-rank-by-volumes.py --top 1  > .cache/voldesc/rank.txt   # ★1作ずつ
python scripts/_voldesc-material.py --slugs-file .cache/voldesc/rank.txt --local-only
# → Step2 生成(100巻/batch)→ Step3 _voldesc-apply.py → commit/push
```

- `scripts/_voldesc-rank-by-volumes.py` = **2026-07-31 新設**。未生成巻数の多い順に slug を出す。
  数え方は `_voldesc-material.py` の `target_volumes()` と同規約(主版=最古standardの巻のみ/
  他版・他刷でseed済みなら完了扱い/材料なし確定は除外)。`--stats` で分布、`--top N`、`--min N`。
- ★**`--live` は使わない**(ローカル専用が既定)。材料なしは台帳行き→Sonnetアイドル運転が敗者復活。
- 書き方の規律・適用・報告形式は **skill `volume-desc`** に全部あるのでそれに従う。

## 上位20作(2026-07-31 時点の順)

golgo-13 / cooking-papa / minami-no-teiou / edomae-no-shun-ginzayanagisushisandaime /
onihei-hankachou / tenpai / tsuribaka-nisshi / oishinbo / meitantei-conan / shizukanaru-don /
patalliro / mizuki-shigeru-manga-dai-zenshuu / yowamushi-pedal / asari-chan / futari-etchi /
nijitte-monogatari / kaze-no-daichi / nanto-magoroku / soumubu-soumuka-yamaguchi-roppeeta /
tasogare-ryuuseigun

完了・不要になったらこの記憶を削除。

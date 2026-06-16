# 楽天あらすじ → ジャンル 学習記録

> 目的: 本番 manga.v2 の `genres_provisional:true`(AI暫定・低信頼)を、楽天 itemCaption(あらすじ)
> 由来の高精度ジャンルで底上げする。**先に教師あり学習で精度を測り、高精度ジャンルだけ振る**。
> 方針: [[genre_from_rakuten_story_plan]] / [[genre_quality_improvement]] / [[ai_genre_closed_vocabulary]]
>
> この文書は「**学習が後からわかる**」ための台帳。各 step の数字・判断・成果物パスを残す。
> 再利用原則: 重い join / LLM 出力は必ず永続化し、**同じソースでのやり直しをしない**。

---

## データの繋がり(誤マッチゼロの根拠)

```
楽天 itemCaption ──(ISBN13)── manga.v2 volumes ──(work)── trusted genres(ラベル)
```

- 楽天キャプションは **ISBN紐付け** = その巻に確実結合。AniList題名照合の約10%疑惑リンク
  ([[anilist_link_quality]])と違い、原理的に別作混入が起きない。
- ラベル(教師の正解)= 本番 `genres`(`genres_provisional` が立っていない work)。
  = promote が **AniList genres+themes ∪ Wiki/手動** をマージした信頼ジャンル。

---

## step0: 教師コーパス件数確定 ✅ (2026-06-16)

スクリプト: `scripts/_genre_rakuten_step0.py`
成果物: `.cache/genre-rakuten/corpus.jsonl`(caption有り全work=再利用の核) / `step0-summary.json`
入力: `.cache/rakuten-isbn.jsonl`(復元元 `data/seeds/harvest/rakuten-isbn.jsonl.gz`)+ `data/manga.v2/*.yml`

### work 分類

| 区分 | 件数 | 説明 |
|---|---:|---|
| manga.v2 総work | 66,556 | |
| trusted(信頼ラベル) | 34,389 | AniList/Wiki由来。**教師の母集団** |
| provisional(AI暫定) | 31,111 | 低信頼。**底上げ対象の母集団** |
| other単独 | 1,056 | discovery不可視の長尾 |
| genre無 | 0 | 全work≥1ジャンル |

### 楽天キャプションとの突合

| 指標 | 件数 |
|---|---:|
| 楽天 caption(≥40字)を持つ ISBN | 110,417 / 246,228 |
| caption有り work | 28,809 |
| ★**教師コーパス = trusted ∩ caption** | **20,016** |
| ★**適用対象 = provisional ∩ caption** | **8,793** |

→ 教師 20,016 件 = 学習+held-out検証に十分(plan想定1.5〜2万と一致)。
→ 今回の施策で直接埋まる候補 = provisional のうち caption がある **8,793 件**(残 provisional は
   楽天キャプション無し=この手では届かない。別源 or AI暫定のまま)。

### ジャンル別ラベル数(教師コーパス 20,016 件内)

| genre | n | | genre | n | | genre | n |
|---|---:|---|---|---:|---|---|---:|
| romance | 8,557 | | mystery | 1,456 | | mecha | 250 |
| comedy | 7,903 | | sci-fi | 1,412 | | gourmet | 227 |
| drama | 6,173 | | school | 1,177 | | yokai | 129 |
| fantasy | 5,081 | | mind-game | 980 | | baseball | 122 |
| slice-of-life | 4,822 | | horror | 881 | | mahou-shoujo | 113 |
| action | 4,098 | | sports | 840 | | soccer | 81 |
| supernatural | 2,645 | | bl | 665 | | essay | 71 |
| adventure | 2,276 | | historical | 432 | | war | 34 |
| ecchi | 1,993 | | isekai | 422 | | | |
| | | | suspense | 412 | | | |
| | | | music | 339 | | | |

ラベル数/work: 1個=3,387 / 2個=6,654 / 3個=5,437 / 4個=2,807 / 5個=1,185 / 6個=417 / 7+=129。
平均 ≈ 2.8 ジャンル/work(多ラベル前提が正しい)。

### ★step0 で判明した重要事実(設計に直結)

1. **4ジャンルは教師ゼロ = この源では学習・検証・適用すべて不可**:
   `gag` / `romcom` / `samurai` / `4-koma`(master32中)。
   理由 = trusted源(AniList語彙)が gag→Comedy / romcom→Romance+Comedy / samurai→Historical /
   4-koma=形式 に吸収され、MANGALキーに分離して出てこない。
   → これらは楽天では振れない。AI暫定 or Wikipedia等の別源に委ねる(後段判断)。

2. **強いクラス不均衡**: romance 8,557 ↔ war 34(250倍)。希少ジャンル(war/essay/soccer/baseball/
   mahou-shoujo/yokai)は held-out の正例が二桁=精度推定が不安定 → **ジャンル別閾値**で弱い源は振らない方針が必須。

3. **generic 過剰の懸念再確認**: romance/comedy/drama が突出。教師ラベル自体が広く付く語なので、
   学習器も乱発しやすい → 適合率(precision)重視の閾値設定が要。

---

## step1: train/held-out 分割 + 手法決定 ⬜ (進行中)

(環境: sklearn/numpy/tokenizer 無し = pure Python or LLM。決定待ち → 下に追記)

## step2: held-out 検証(ジャンル別 適合率/再現率)⬜

(ここに per-genre precision/recall/F1 表を入れる = 「学習の中身」の本体)

## step3: 適用(高精度ジャンルだけ provisional に振る)⬜ — ユーザGO待ち

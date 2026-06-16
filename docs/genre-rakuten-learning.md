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

## step1: train/held-out 分割 + 手法決定 ✅ (2026-06-16)

スクリプト: `scripts/_genre_rakuten_step1.py`
- 手法 = **LLM分類(option1)**。ユーザ裁定: 意味的ジャンルに強く、本番step3の適用方式と同一なので検証が本物。
- 分割: 教師20,016 を seed固定(20260616)シャッフル → **held-out 3,000 / train 17,016**。
- **学習可能28キー** = master32 − {gag, romcom, samurai, 4-koma}(step0で教師ゼロ判明)。
- **データ由来の学習**(`genre-cues.json` / `rubric.md`): train17,016 から **ジャンル別 distinctive keyword**
  を log-odds で採掘(可読・監査可)。例:
  - baseball = 野球漫画 / 甲子園 / 投手 / 球界
  - isekai = 異世界召喚 / ドワーフ / ティア
  - war = 太平洋 / 戦争 / 戦場 / 昭和
  - gourmet = レシピ / 胃袋 / 賞味 / グルメコメディ
  - bl = ノンケ / オメガバース / 発情期 / アルファ
  - 全28キーは `.cache/genre-rakuten/rubric.md`。

## step2: held-out 検証(ジャンル別 適合率/再現率)✅ (2026-06-16)

スクリプト: 分類=workflow `genre-rakuten-heldout`(75エージェント並列, caption-onlyで28キー分類)/
評価=`scripts/_genre_rakuten_step2_eval.py`。成果物 `.cache/genre-rakuten/step2-metrics.json`。

- 突合 2,999 work / 欠損1。LLMが禁止キーを使った回数(=直感的に有意なジャンル): romcom 84 / 4-koma 24 / samurai 17 / gag 13。
- **全体**: micro P/R/F1 = **0.649 / 0.598 / 0.623**、 macro-F1 = 0.560。

### ★ジャンル別 P/R/F1(support=truth正例数, pred=LLM予測数)

| genre | 名称 | support | pred | P | R | F1 | 判定 |
|---|---|---:|---:|---:|---:|---:|---|
| romance | 恋愛 | 1288 | 988 | **0.91** | 0.70 | 0.79 | ◎Tier1 |
| comedy | コメディ | 1155 | 902 | 0.77 | 0.60 | 0.68 | ○Tier2 |
| drama | ドラマ | 934 | 851 | 0.60 | 0.55 | 0.57 | △Tier2 |
| fantasy | ファンタジー | 772 | 694 | **0.87** | 0.78 | 0.82 | ◎Tier1 |
| slice-of-life | 日常 | 744 | 419 | 0.71 | 0.40 | 0.51 | ○Tier2 |
| action | アクション | 594 | 537 | 0.74 | 0.67 | 0.71 | ○Tier2 |
| supernatural | 超常 | 405 | 306 | 0.69 | 0.52 | 0.59 | ○Tier2 |
| adventure | 冒険 | 334 | 206 | 0.65 | 0.40 | 0.49 | ○Tier2 |
| ecchi | お色気 | 287 | 213 | 0.62 | 0.46 | 0.53 | ○Tier2 |
| mystery | ミステリー | 215 | 146 | 0.63 | 0.43 | 0.51 | ○Tier2 |
| sci-fi | SF | 189 | 169 | 0.73 | 0.65 | 0.69 | ○Tier2 |
| school | 学園 | 179 | 607 | 0.20 | 0.69 | 0.32 | ⚠Tier3(truth-gap) |
| mind-game | 頭脳戦 | 147 | 29 | 0.45 | 0.09 | 0.15 | ✕Tier4(LLM検出不足) |
| sports | スポーツ | 135 | 117 | **0.89** | 0.77 | 0.82 | ◎Tier1 |
| horror | ホラー | 134 | 127 | 0.70 | 0.66 | 0.68 | ○Tier2 |
| bl | ボーイズラブ | 102 | 134 | 0.57 | 0.74 | 0.64 | ○Tier2(lexical堅) |
| suspense | サスペンス | 64 | 164 | 0.26 | 0.66 | 0.37 | ✕Tier4(過付与) |
| isekai | 異世界 | 63 | 243 | 0.21 | 0.82 | 0.34 | ⚠Tier3(truth-gap) |
| historical | 歴史 | 57 | 157 | 0.24 | 0.65 | 0.35 | ✕Tier4(過付与) |
| music | 音楽 | 54 | 67 | 0.63 | 0.78 | 0.69 | ○Tier2(lexical堅) |
| gourmet | グルメ | 32 | 91 | 0.23 | 0.66 | 0.34 | ⚠Tier3(truth-gap) |
| mecha | メカ | 29 | 22 | **0.91** | 0.69 | 0.78 | ◎Tier1 |
| yokai | 妖怪 | 19 | 36 | 0.19 | 0.37 | 0.26 | ✕Tier4 |
| mahou-shoujo | 魔法少女 | 18 | 17 | **0.82** | 0.78 | 0.80 | ◎Tier1(支持薄) |
| baseball | 野球 | 18 | 19 | **0.90** | 0.94 | 0.92 | ◎Tier1(支持薄) |
| essay | エッセイ漫画 | 13 | 47 | 0.21 | 0.77 | 0.33 | ⚠支持薄 |
| soccer | サッカー | 11 | 14 | **0.79** | 1.00 | 0.88 | ◎Tier1(支持薄) |
| war | 戦争 | 4 | 49 | 0.06 | 0.75 | 0.11 | ✕Tier4(過付与/支持極薄) |

### ★最重要の発見 = 測定精度は「下限値」(truth が不完全)

FP(LLM予測したが truth に無い)を本文サンプリングしたところ、**多くが LLM 正解で truth 側の取りこぼし**だった:
- **gourmet**: 「中華料理に大革命」「夜食レシピ」「らーめんガール」= 料理漫画。truth(AniList)が未ラベル → P0.23 は大幅過小評価。
- **isekai**: 「乙女ゲーム世界に転生」「クズ男に転生」= 教科書的転生もの。truth が保守的 → P0.21 は過小評価。
- **school**: 「転校生」「学園内」「高校生」= 明確に学園。AniList が school を genre 化しない方針 → P0.20 は過小評価。
- 対して **war / historical / suspense** は「戦・軍」「昭和・戦国」「デスゲーム」への**真の過反応**(LLMが誤って広く付ける)。
  ※ war は AniList が "War" theme を意図的に除外([[genre_quality_improvement]])する設計と整合 = truth/LLM 双方が信用できない。

帰結:
1. **lexicalに根拠が明確なジャンル(gourmet/isekai/school/baseball/sports/music/mecha/bl)は、測定Pが低くても実精度は高い**。truthの欠落が見かけのPを下げているだけ。
2. **真の過付与ジャンル(war/historical/suspense/yokai)は適用しない**。
3. mind-game は LLM が検出不足(R0.09)=この源では拾えない。
4. → 適用可否は「測定P閾値」だけで決めず、**truth-gap型 と 過付与型 を区別**する必要がある(下記Tier)。

### 適用Tier(step3の振り分け案)

- **Tier1 = そのまま適用OK**(測定P≥0.80, lexical堅牢): romance / fantasy / sports / baseball / soccer / mecha / mahou-shoujo
- **Tier2 = 適用可(中精度)**: comedy / action / sci-fi / horror / supernatural / mystery / music / ecchi / bl / slice-of-life / adventure / drama
- **Tier3 = 実精度は高い疑い(truth-gap)= 本文再判定で救済してから適用**: gourmet / isekai / school
- **Tier4 = 適用しない**(過付与 or 検出不能): war / historical / suspense / yokai / mind-game / essay

---

## タグ(要素)検証 ✅ (2026-06-16)

ジャンルと**同一の held-out 3,000 work・同一あらすじ**で実施(同一作で突合可)。
- 教師 = AniList theme tags(Demographic 除外)。closed vocab = support≥50 の **85種**(和訳=tag-i18n.yml)。
- スクリプト: `_genre_rakuten_tag_step1.py` / 分類=workflow `tag-rakuten-heldout`(75agent) / 評価=`_genre_rakuten_tag_step2_eval.py`。
- 評価母数 = held-out のうち trusted theme tag を持つ **1,127 work**。
- **全体**: micro P/R/F1 = **0.556 / 0.398 / 0.464**(ジャンルより低い=語彙大・希少・truth-gap大)。

### ★タグの教訓 = 「具体タグは当たる/抽象タグは無理」

具体的・lexicalなタグは高精度。抽象的・主観的タグは壊滅。仮説どおり。

- **適用OK(P≥0.70 & R実用)**: Boys'Love(0.95) / Yuri(0.88) / Animals動物(0.84) / Martial Arts格闘技(0.80) /
  Henshin変身(0.80) / Food料理(0.78) / Autobiographical自伝(0.77) / Drawing絵漫画(0.72) / Youkai妖怪(0.72) /
  Isekai異世界(0.71/R0.82) / Band(0.70) / Baseball(1.00) / Yakuza(0.65/R0.73)
- **高P・低R(付ければ正しいが取りこぼし多=安全に適用可)**: Guns銃(1.00/R0.18) / Gore残酷(0.77/R0.20) /
  Cute Girls美少女日常(1.00/R0.12) / Meta(0.75) / Educational学習(0.71) / Writing執筆(0.75)
- **中(P0.5-0.7・truth-gap疑い)**: Reincarnation転生(0.52/R0.77) / Revenge復讐(0.65) / Death Gameデスゲーム(0.64) /
  Police警察(0.59) / Acting演劇(0.62) / Medicine医療(0.52) / Survival(0.48/R0.68)
- **不可(抽象/主観=壊滅)**: Philosophy哲学(0.00) / Tragedy悲劇(0.09) / Coming of Age成長(0.26) /
  Iyashikei癒し系(0.29) / Surreal Comedy(0.10) / Unrequited Love片思い(0.04) / Found Family疑似家族(0.14) /
  Slapstick(0.00) / Cohabitation同棲(0.13) / LGBTQ+(0.24)
- 全85行は `.cache/genre-rakuten/tag-step2-metrics.json`。

### ★ジャンル⇄タグ クロス確証(同一作で突合)

タグ結果がジャンルの **Tier3 truth-gap 仮説を裏付け**:
- **Food料理 P0.78** → ジャンル gourmet(measured P0.23)の低さは truth-gap で、実精度は高い、を独立に確証。
- **Isekai異世界 P0.71/R0.82** → ジャンル isekai(P0.21)も同様に truth-gap。実は高精度。
- → gourmet / isekai は **Tier3救済の必要なし=Tier1相当で適用可**と判断できる(タグ側が真値の代理検証になった)。

## step3: 適用(高精度ラベルだけ振る)⬜ — ユーザGO待ち

### ジャンル(対象 = provisional ∩ caption = 8,793 work)
- 適用 = Tier1 + Tier2 + **gourmet/isekai(タグで確証)**。`genres_rakuten` 印、trusted/手動は上書きしない。
- school は要素タグに直接対応なし→保留(genre school は付与過剰気味なので慎重)。
- 不適用 = war / historical / suspense / yokai / mind-game / essay。

### タグ(要素・additive。対象 = caption有り work でタグ未保有 or 補完)
- 適用 = 上記「適用OK」+「高P低R」群の約20タグのみ。中・不可群は振らない。
- 表示 = 要素欄(tag-i18n 和訳)。

GO後、同分類器を本番対象に流して高精度ラベルのみ純粋追加 → promote で焼込。

---
name: voldesc_next_slice_todo
description: 巻説明つくって=/clear後の再開点。★巻数順(ファイル名順から切替)・1作ずつ完走
metadata: 
  node_type: memory
  type: project
  originSessionId: 3e3a9f98-da9d-4815-a148-8c58f6e055f6
  modified: 2026-08-08T23:36:54.006Z
---

★保留タスク: ユーザが `/clear` 後に「巻説明つくって」(=「巻情報つくって」も同義)で再開する。

## 選定方針(2026-07-31 ユーザ指示)

- **巻数順**(未生成巻の多い作から)。ファイル名順=端からは**やめた**。歩留まりが実測5倍以上違う。
- **1作品ずつ、その作を全巻終わらせてから次へ**([[voldesc_finish_started_series]])。
- [[feedback_no_popularity_priority]](人気順禁止)には反しない(人気ではなく巻数)。

## 現在地(2026-08-09 セッション終了時)

- seed `data/seeds/volume-desc-ja.jsonl` = **8,452行**(このセッション開始7,760 → **+692巻**)。
- 材料なし台帳 `.cache/voldesc/no-material.txt` = 1,406件。

### 2026-08-09 セッション(ユーザ「五時間連続で」)で完走・消化した作

ギャラリーフェイク全40完走 / **史上最強の弟子ケンイチ全61完走** / 絶対可憐チルドレン+57(v29/33/34材料なし・v30-32付録のみ) /
彼岸島48日後+52(v11/12は話数タイトルのみ・v43材料なし) / スーパーマリオくん+54(v34-40共通惹句のみ) /
金瓶梅24 / オーイ!とんぼ13 / ゴッドハンド輝15 / 新コボちゃん12 / **夕焼けの詩(三丁目の夕日)+57(v16-72)** /
**ハヤテのごとく!全52完走** / K2+38(v1-7,v9-15は共通惹句+話数のみ) / **ちはやふる全50完走** /
めしばな刑事タチバナ+44 / 酒のほそ道22 / 剣客商売24 / スキップ・ビート27 / 空手小公子7 / **BE BLUES!全49完走**

### ★次の着手先(材料収集済み・未着手。`--slugs`で即書ける)

- **battle-studies 48**(medcap181) / **q-e-d 50**(medcap79=薄い) / **glass-no-kamen 49**(medcap87=薄い) /
  **mairimashita-iruma-kun 38**(medcap109) / kureyon-shin-chan 4
- 材料0で台帳送り済み(飛ばす)= golgo-13 / minami-no-teiou / nijitte-monogatari / inochi-no-utsuwa / zero /
  g-defend / marugoshi-deka / patalliro / shizukanaru-don / tsurikichi-sanpei / ginga-densetsu-weed /
  kobo-chan / kootaroo-makaritooru / ashita-tenki-ni-naare / wataru-ga-pyun / keirin-yarou /
  alfheim-no-kishi / dokaben-puroyakyuuhen / 4p-tanaka-kun / kougyou-aika-volley-boys / sazae-san / kariage-kun

## ★材料の型(判定してから書く。2026-08-09で確定)

1. **小学館ビッグ/サンデー系(中央値600字超)= あらすじ+本巻の特徴+収録話**が最良。1巻250-350字で欠落ゼロ。
   夕焼けの詩(3話分あらすじ)・ケンイチ・ギャラリーフェイク・絶チル・ハヤテ・とんぼが該当。
2. **煽り帯+収録話リスト型**(講談社/秋田/日本文芸社系。中央値100-350字)= 帯の内容部分から120-250字で書ける。
   彼岸島・めしばな・酒のほそ道・剣客商売・BE BLUES!・スキビが該当。**シリーズ共通の前振りは捨てる**。
3. **共通惹句のみ / 話数タイトルだけ** = **書けない**(欠落表へ)。K2 v1-15・マリオ v34-40・サザエさん・かりあげクン。

## ★丸写しゲート(50字連続一致)は**短いcaptionほど当たる**

このセッションで実測**約40件**reject。全て再投入で通過。効く直し方は
**①主語を変える ②文の順番を入れ替える ③体言止め/連体修飾を分解する**。
特に「表題作は〜。ほかに、A、B、C」の列挙部分がそのまま一致しやすいので、列挙の順序を変える。

## 再開手順

```
python scripts/_voldesc-rank-by-volumes.py --top 40 2>/dev/null > .cache/voldesc/rank.txt
python scripts/_voldesc-material.py --slugs <上の未着手slug> --local-only
# → 材料をUTF-8ファイルにdumpしてRead(コンソール直出しは文字化けする)
# → Step2 生成 → python scripts/_voldesc-apply.py ".cache/voldesc/out/batch-*.jsonl" → commit/push
```

- ★**`--live` は使わない**。材料なしは台帳→Sonnetアイドル運転(柱⑦ `--recheck-nomaterial`)が敗者復活。
- 書き方の規律・報告形式は skill `volume-desc` に従う。

完了・不要になったらこの記憶を削除。

---
name: voldesc_next_slice_todo
description: 巻説明つくって=/clear後の再開点。★巻数順(ファイル名順から切替)・1作ずつ完走
metadata: 
  node_type: memory
  type: project
  originSessionId: 3e3a9f98-da9d-4815-a148-8c58f6e055f6
  modified: 2026-08-09T08:05:02.433Z
---

★保留タスク: ユーザが `/clear` 後に「巻説明つくって」(=「巻情報つくって」も同義)で再開する。

## 選定方針(2026-07-31 ユーザ指示)

- **巻数順**(未生成巻の多い作から)。ファイル名順=端からは**やめた**。歩留まりが実測5倍以上違う。
- **1作品ずつ、その作を全巻終わらせてから次へ**([[voldesc_finish_started_series]])。
- [[feedback_no_popularity_priority]](人気順禁止)には反しない(人気ではなく巻数)。

## 現在地(2026-08-09 セッション終了時)

- seed `data/seeds/volume-desc-ja.jsonl` = **10,617行**(このセッション開始7,760 → **+2,857巻**)。
- 材料なし台帳 `.cache/voldesc/no-material.txt` = 累計3,656件。
- ★終了理由 = **セッション上限**(JST17時リセット)。並列19ジョブ中に一斉failした。

## 2026-08-09 セッションで消化した作(直列ぶん)

ギャラリーフェイク40完走 / 史上最強の弟子ケンイチ61完走 / 絶対可憐チルドレン+57 / 彼岸島48日後+52 /
スーパーマリオくん+54 / 金瓶梅24 / オーイ!とんぼ13 / ゴッドハンド輝15 / 新コボちゃん12 / 夕焼けの詩+57 /
ハヤテのごとく!52完走 / K2+38 / ちはやふる50完走 / めしばな刑事タチバナ+44 / 酒のほそ道22 / 剣客商売24 /
スキップ・ビート27 / 空手小公子7 / BE BLUES!49完走 / バトルスタディーズ+43

### 並列ラン(1時間ぶん)で +514

美味しんぼアラカルト49 / あずみ48 / ガラスの仮面48 / Q.E.D.50 / 頭文字D48 / 白竜HADOU47 / 新テニス47 /
ベイビーステップ46 / 入間くん38 / 結界師31 / ヒカルの碁23 / チキンドロップ前夜20 / 嘘喰い17 / 華麗なる食卓2

### 並列ラン(5時間ぶん・上限で中断)で +1,608

七つの大罪41 / ヒロアカ41 / 仮面ライダーSPIRITS41 / テニスの王子様42 / DAYS42 / 築地魚河岸三代目41 /
ドラゴンボール41 / リボーン42 / アオアシ40 / 高校鉄拳伝タフ(tetsu-bon)40 / じゃじゃ39 / みい子39 /
HUNTER×HUNTER39 / おおきく振りかぶって38 / 新宿スワン38 / ブルーロック33 / グリコ34 / 境界のRINNE30 /
ろくでなしBLUES25 / HOTEL25 / GS美神22 / 遊☆戯☆王22 / からくりサーカス22 / でめきん17 / カバチ19(p2のみ) /
今日から俺は18 / キャプテン翼18(p2のみ) / SAMURAI DEEPER KYO15 / ダイの大冒険13(p1のみ) / ぼのぼの5 ほか

## ★次の再開点(材料は `.cache/voldesc/par/` に生成済み=すぐ流せる)

上限failで**未完のジョブ**(par/配下のtxtはそのまま在る):
`kabachi-p1` / `gang-king-p1,p2` / `komi-san-wa-komyushou-desu-p1,p2` / `magi-p1,p2` /
`tonikaku-kawaii-p1,p2` / `one-punch-man-p1,p2` / `satanophany-p1,p2` / `hana-yori-dango-p1,p2` /
`captain-tsubasa-p1` / `dragon-quest-daino-daibouken-p2` / `gantz` / `ryuurouden` / `tsugumomo` /
`hanma-baki` / `hotel`済 / `kamakura-monogatari` / `nobunaga-no-chef` / `tenpai-gaiden` / `pikupiku-sentarou` /
`kirin` / `tough` / `arukimedesu-no-taisen-p1,p2` / `baribari-densetsu` / `black-clover-p1,p2` /
`hatarakanai-futari-p1,p2` / `bar-lemon-heart` / `mahou-sensei-negima`
→ ★**再開は「材料収集からやり直さず、この par/*.txt をそのままエージェントに渡す」**のが最速。

## ★並列運転の型(2026-08-09 確立。これで seed 競合ゼロ)

1. **材料は親が一括収集**(`_voldesc-material.py --slugs ... --local-only`)。★`materials.jsonl` は毎回**上書き**
   されるので、次を回す前に `materials-RN.jsonl` へ退避(`_par_check.py` が `materials*.jsonl` を全部読む)。
2. `python scripts/_par_prep.py 22` = 型を測って `.cache/voldesc/par/<slug>[-pN].txt` に分割
   (相異caption率<0.5 or 平均<55字は SKIP。long/mid/short を判定)。
3. エージェントは **JSONLを書くだけ**。★`_voldesc-apply.py` 実行とgit操作は**禁止**と明記(並列でseedを叩かせない)。
4. 親が `python scripts/_par_check.py <name...>`(ISBN↔材料照合/60字/改行/ISBN重複)→ **直列apply** → commit/push。
5. 実測: **同時20が上限**(21本目は "Concurrent subagent limit reached")。1ジョブ≒20巻で2〜6分。
   全セッション累計 reject **23件のみ**(全部書き直して通過)、ISBN取り違え0。

## ★エージェントへの指示で効いたこと / 失敗したこと

- ★**失敗**: 「話数タイトルの羅列だけの巻はスキップ」と書くと、**類型2(共通惹句+収録話)を丸ごと捨てる**。
  頭文字Dで全24巻スキップ → 「**収録話タイトルは事実。これを使って書く。スキップするな**」と明示して48巻回収。
- ★**先に型を測る**: `_par_prep.py` が出す `相異caption率 / 平均字数` を見てから字数レンジを指定する
  (long=250-380 / mid=150-280 / short=80-180)。short型に300字を要求すると水増しになる。
- 丸写しゲート対策(**①主語替え ②文順入替 ③体言止め分解**)は**プロンプトに明記すれば効く**(reject率0.8%→ほぼ0)。

## ★材料の型(判定してから書く)

1. **小学館ビッグ/サンデー系(中央値600字超)= あらすじ+本巻の特徴+収録話**が最良。1巻250-350字。
2. **煽り帯+収録話リスト型**(講談社/秋田/日本文芸社系。100-350字)= 内容部分から120-250字。共通前振りは捨てる。
3. **共通惹句のみ / 刊行案内・特装版グッズ案内だけ** = **書けない**(欠落表へ)。

## 再開手順

```
python scripts/_voldesc-rank-by-volumes.py --top 40 2>/dev/null > .cache/voldesc/rank.txt
python scripts/_voldesc-material.py --slugs <未着手slug20件> --local-only
cp .cache/voldesc/materials.jsonl .cache/voldesc/materials-RN.jsonl
python scripts/_par_prep.py 22        # → par/*.txt
# → エージェント20並列 → _par_check → 直列apply → commit/push
```

- ★**`--live` は使わない**。材料なしは台帳→Sonnetアイドル運転(柱⑦ `--recheck-nomaterial`)が敗者復活。
- 書き方の規律・報告形式は skill `volume-desc` に従う。

完了・不要になったらこの記憶を削除。

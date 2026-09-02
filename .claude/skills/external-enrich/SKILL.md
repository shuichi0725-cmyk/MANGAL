---
name: external-enrich
description: 外部エンリッチして/外部エンリッチ続けて=楽天captionが枯れた層(旧作・完結長編)に、Wikipedia API+魚(TinyFish)で拾った一次情報を材料にキャッチ/詳細/ジャンルを付与する。掲載境界と材料なしは書かずに台帳へ。Opus運転前提
---

# 外部エンリッチ (= トリガー「外部エンリッチして」「外部エンリッチ続けて」)

skill `enrich-catch-synopsis` の**材料源を差し替えた柱**。
あちらは楽天itemCaptionが前提だが、**旧作・完結長編ではcaptionがほぼ存在しない**
([[enrich_newest_seam_exhausted]] = 2026-08-06に「新しい順」柱が枯れた)。
本skillは **Wikipedia API → 出版社公式/電子書店(魚)** を一次情報として使い、同じ規律で書く。

★**字数規格・役割分担・丸写し禁止・1巻頁の扱いは `enrich-catch-synopsis` と完全に同じ**。
差分は「材料をどこから取るか」と「境界/材料なしの捌き方」だけ。

## 0. 現在の対象リスト(= どこまでやったかは memory [[external_enrich_state]])

| リスト | 生成コマンド | 状態 |
|---|---|---|
| 5巻以上×2010年以降 | `--min-vols 5 --since 2010 --basis any` | 消化済(残は保留のみ) |
| 5巻以上×2009年以前 | `--min-vols 5 --until 2009 --basis latest` | **進行中** |

```
python scripts/_enrich-backlog-scan.py --min-vols 5 --until 2009 --basis latest --missing any \
  -o docs/production-diagnostics/enrich-backlog-5vol-pre2010.tsv
```
`--basis first|latest|any` × `--since/--until` で層を切る。`--missing both|any`。
出力列 = first_date / latest_date / n_vols / slug(**SRC stem**) / title / missing / genres / authors。

## 1. 作業行を開く(巻数の多い順=リスト順)

```
WL_TSV=docs/production-diagnostics/enrich-backlog-5vol-pre2010.tsv \
  python scripts/_enrich-worklist.py 19 36
```
末尾の `PUBS=...` をそのまま次に渡す。**1回18〜20行が実用単位**。

## 2. 材料収集(この順で降りる。上で取れたら下は叩かない)

1. **楽天キャッシュ**(外部照会ゼロ):
   `python scripts/_enrich-captions.py --slugs "<PUBSの中身>" --src data/manga.v2`
   ★`--slugs` は **公開slug** で照合する。SRC stem を渡すと**無言で素通り**する。
   旧作層の歩留まりは実測ほぼ0〜1割。1〜2巻のcaptionが無ければ次へ。
2. **Wikipedia**: `python scripts/_wiki-extract.py "題名" "題名2" --chars 700`
   (あらすじ/ストーリー/概要節を優先表示。作品記事が無い時は作者記事に飛ぶことがある=題名を変えて再試行)
3. **魚(TinyFish)**: `python scripts/_tinyfish.py search "「題名」 作者 あらすじ"`
   出版社公式・電子書店(コミックシーモア/ピッコマ/BookLive)・書店の作品紹介が拾える。
   必要なら `fetch <URL>` で本文を取る(公式の作品紹介ページが最良)。
4. NDLは**書誌**用(題/巻/著者/版元)。あらすじは持っていない。叩くなら `scripts/_lookup.py`(1.3s/req・429即中断)。

## 3. 書く(規律は enrich-catch-synopsis と同一)

- キャッチ **48〜74字**(規格50-70±2) / 詳細 **78〜114字**(規格80-110±4)。
- ★**体感より4〜6字短く出る**。最初から**52〜58字狙いで3節構成**にすると一発で通る
  (`[フック]。[状況]。[ジャンル/締め]。` の各節を「1文相当」にする)。
- 丸写し禁止(8gram≥0.4でblock)。**材料テキストをそのまま `s<N>.json` に入れる**こと=検査が効く。
- 詳細は**1〜2巻の範囲**。最終巻・結末は書かない。続編頁は「その巻から何が始まるか」を書く。
- ジャンルは master32 から選ぶだけ。既存genre有りの頁には applier が書かないので、
  足したい時は `data/seeds/genre-append.yml`(純粋追加・union)へ。

## 4. 検算 → 適用

```
python scripts/_enrich-batch-build.py 9436 > .cache/in9436.json   # 字数リント(NG=0にしてから進む)
python scripts/_enrich-web-batch.py 9436 < .cache/in9436.json     # 字数/丸写し/頭20字/キー不一致
python scripts/_apply-enrich-batch.py 9436 --apply                # 純粋追加(既済はskip)
```
- 入力3点は `.cache/s<N>.json`(材料) `.cache/c<N>.json`(catch) `.cache/y<N>.json`(syn)。キーは**SRC stem**。
- **既に catch/syn が入っている頁は skip される**。差し替えたい時だけ `--requeue`。
- ★**バッチ番号は 9401番台以降**(既存0001-0380/9104-9107/9200番台と衝突しない)。使用済みは memory を見る。

## 5. 反映

```
python scripts/_reflect-targeted.py --only <SRC stem,...> --push -m "エンリッチ(外部材料)…"
```
★**ISBN消失ゲートが鳴ったら止めて調べる**。実際に2026-09-01、promote側の別変更で
実在巻が消えたのをこのゲートが検知した。心当たりが無いのに `--allow-loss` を付けない。

## ★捏造しない = 書かない判断(この柱の肝)

材料が取れない/掲載境界の頁は**空のまま**にして、**必ず**理由付きで台帳に残す:
`docs/production-diagnostics/enrich-hold.tsv`(列 = slug / title / at / batch / reason)。
書かずに黙って飛ばすと、次の周回で同じ頁をまた調べ直すことになる。

### 掲載境界の見分け(機械証拠が先。魚は割れた分だけ)
CLAUDE.mdの掲載scopeに照らして**enrichせずhold → dropはユーザ裁定**。決定的signal:

| signal | 出所 | 意味 |
|---|---|---|
| 著者欄が「アンソロジー」「◯◯編集部」「出版社名」 | 楽天item.author | アンソロジー/セレクション |
| seriesName が `My First BIG` / `◯◯mook` / `トップコミックスWIDE` / `Qコミックス` | 楽天item.seriesName | コンビニ廉価・ムック |
| subTitle が「傑作選」「傑作集」 | 楽天item.subTitle | 再録集 |
| 巻題が「(1＋2巻)」 | 楽天item.title | 合本 |
| 巻ごとに著者が違う(NDLで確認) | NDL SRU | 同題アンソロジー(叢書) |
| ShoPro Books 等のアメコミ邦訳 | 頁のimprint | scope外 |

★**本番のimprintは化けることがある**(泣ける!ゴルゴ13=実体はMy First BIGなのに頁は`Golgo 13 special`)。
imprint文字列だけの網を信用せず、**楽天のseriesName/authorを見る**。

### 機械証拠の一括算出(全件を同じ濃度で魚に投げない)
候補が数件を超えたら、楽天キャッシュ(1.2GB)を**1パス**で舐めて候補ISBNのitemだけ集め、
著者/seriesName/subTitle/captionを一覧化してから、割れた分だけ魚に回す([[feedback_agent_fanout_token_cost]])。

## ★別作品のcatch/synが既に入っている型(見つけたら直す)

この柱の副産物として頻出する。**1件見つけたら型と疑う**([[feedback_one_bug_means_a_class]]):
- `boy` に「親の再婚で集められた五人の兄弟姉妹」= 別作品のキャッチ
- `duel-masters-2015`(VS=勝太編)に 2017年版(ジョー編)のキャッチ
- `pokkapoka` のあらすじが「3人の幼い娘たち」(実際は3人家族・娘は1人)
- `soredemo-bokura-wa-yattenai` のあらすじが「10話の追加エピソードを含む。」= 書誌メモ
→ `--requeue` で上書き。**あらすじは anilist_id キーの synopsis-ja.json が優先層**なので、
applier に任せる(slug側だけ直しても頁に出ない = [[synopsis_ja_seed]])。

## 罠(実踏)

- ★**`_enrich-web-batch.py` は `PYTHONUTF8=1` を付けて走らせる**。stdin リダイレクトだと Windows の
  既定コーデック(cp932)で読まれ、**全件が字数違反・頭20字一致に化ける**(2026-09-02 実踏。
  build 側は c53 y99 と出しているのに web-batch が catch97 と言い出したら、まずこれを疑う)。
  `_apply-enrich-batch.py` / `_reflect-targeted.py` も同様に付けておくと安全。
- ★**既存ジャンルが明らかに誤りでも genre-append では消せない**(union only)。誤りは `source:` 欄に
  「既存 X はAI推定の誤りの疑い」と書き残し、ユーザへ報告する(除去機構は現状なし)。

- ★**catch/syn の join キーは「源頁 `data/manga/<stem>.yml` の slug」**。ファイル名と違う頁がある
  (`tales-of-the-abyss-rei2006` の源頁slugは `tales-of-the-abyss-rei`)。stemキーで書くと**無警告で頁に出ない**。
  `_enrich-web-batch.py` がこの不一致を検査するので、そこで止まったら指示どおりのキーに直す。
- **1巻頁はキャッチ/詳細を書かない**(2026-07-14裁定=ジャンルのみ)。
- 楽天captionが後半巻しか無い頁は、premiseが取れないので**書かない**(hold)。
- 生成物は git 追跡: `data/enrich-out-2026-07/batch-NNNN.json`。材料は `.cache/enrich-batches/batch-NNNN.json`。

## 関連
- 材料が楽天中心の本流 = skill `enrich-catch-synopsis`(字数規格・役割分担の正本)
- 照会の作法 = skill `external-data-access` / `tinyfish`
- 反映 = skill `reflect-targeted` / 進捗と残件 = memory [[external_enrich_state]]

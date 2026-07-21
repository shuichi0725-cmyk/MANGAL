---
name: volume-desc
description: 巻説明つくって=単行本(巻)単位の説明文を楽天itemCaptionから生成しseedへ純粋追加。ストーリーは欠落なく長く・人物紹介コーナー禁止・丸写し禁止。Opus 4.8運転前提(2026-07-19新設)
---

# 巻説明生成 (= トリガー「巻説明つくって」「単行本説明つくって」)

**単行本(巻)単位**の説明文を、その巻の楽天紹介文(itemCaption+contents)から生成して蓄積する。
★**Opus 4.8 運転前提**(opus.bat セッションで回す。fable側はレビュー/反映担当)。

## ★表示 = 実装済み(2026-07-20 確定。B2方式・ISBN基準)
- **出し方 = B2(冒頭2行チラ見せ+2行目フェード+「続きを読む」)**。`components/VolumeCoverflow.tsx` の `VolDesc`
  (専用パネルで囲い・赤アクセント「あらすじ」ラベル。選択中の1巻ぶんだけDOM出力)。
- **結線 = ISBN基準**。`_promote-bulk-v2.py` の `_desc_for(isbn13)` が最終pass(書影・発売日と同じ場所=
  canonical再構築の後)で `volume.description` に充填。schemaの既存 `description` フィールドを使用。
- ★**巻番号基準に広げない(ファイナルアンサー・ユーザ裁定)**: 説明は**そのISBN(版バージョン単位)にだけ**出す。
  同じ巻でも別版(元祖/文庫/ワイド)には出さない。理由=①版で冊数が違うと巻番号がズレて内容不整合
  (文庫18巻 vs 新装版34巻型)②同一ページ内の文言重複はSEO不利。**この判断を再発明しない**。
- 反映は**週次蒸留**(コード変更のため週次ルート)。preview確認は reflect-targeted → .preview-data。

## 書き方の規律 (= 2026-07-19 ユーザ裁定・最重要)

- ★**ストーリーはなるべく欠落なく長く**: captionが語る出来事・展開・引き・状況設定を**全部拾って**再構成する。
  目安 **150〜400字**(材料が薄い巻は短くて可。★**水増し・引き伸ばしは禁止**=材料に無いことを足して長くしない)。
- ★**登場人物の紹介コーナーは書かない**(「登場人物: ○○=…」型の列挙・全員紹介は不要)。
  文中で**自然に人物名を使うのはOK**(むしろ使う。「主人公」「ヒロイン」等のぼかしより名前)。
- ★**丸写し禁止**(著作権配慮): 言い換え・再構成で書く。固有名詞・作中用語はそのまま使ってよい。
  apply側に**50字連続一致ゲート**があり丸写しはrejectされる。
- ★**捏造禁止** [[feedback_accuracy_is_the_goal]]: captionに無い展開・結末・因果を推測で書かない。
  材料なしの巻は**空のまま**(生成しない)+欠落表で報告。
- **ネタバレ範囲 = その巻のcaptionが明かす範囲まで**。巻単位説明なのでその巻の内容はOK、
  ただし次巻以降のcaptionから先回りして書かない(材料は当該巻のものだけを使う)。
- **宣伝定型は落とす**: 「大人気御礼!」「TVアニメ化!!」「早くも第◯弾!」等の煽り・刊行宣伝・
  メディア化告知はストーリー説明に含めない。`contents`(収録話)は展開の補強材料にだけ使う。
- 文体: 平叙・現在形基調の客観描写。「〜!?」等の煽り記号は使わない(captionの疑問形の引きは
  「〜が明らかになる」等に言い換えて残す=情報は落とさない)。

## 手順

### Step1: 材料収集 (★2026-07-21 ユーザ指示=**ローカル専用が既定。liveを叩かない**)
```
python scripts/_voldesc-material.py --local-only                          # ★auto: 裸の「巻説明つくって」はこれ
python scripts/_voldesc-material.py --slugs a,b,c --local-only            # 対象指定時
python scripts/_voldesc-material.py --slugs-file list.txt --local-only    # 大量時
```
- ★★**`--live` は使わない**(2026-07-21 ユーザ指示「次からはローカルの情報から作り出す」)。
  理由=分業: **材料収集(live照会含む)はSonnetのアイドル運転が担当**(柱⑦ `--recheck-nomaterial` が
  「材料なし」台帳をlive再照会で敗者復活)。Opus/Fableの生成セッションはローカル在庫
  (予約キャッシュ+`rakuten-isbn.jsonl`+`rakuten-isbn-delta.jsonl`+`recovered.jsonl`)だけで書く。
  ローカル未収の巻は「材料なし」台帳に記録されて後日Sonnet側が回収する=**待てば材料が来る**。
  liveを使うのはユーザが明示した時だけ。
- ★**auto** = slug無し時、ファイル名順(=端から全件・人気順禁止 [[feedback_no_popularity_priority]])に
  seed未生成の巻を `--take`(既定100巻)ぶん自動選定。**再実行=自動で続きから**(seed除外が実質cursor・cursorファイル不要)。
- キャッシュ順=予約キャッシュ→**ローカル楽天2本を1パス**(`rakuten-isbn.jsonl` 373MB全件harvest + `rakuten-isbn-delta.jsonl` 828MB新着差分。別カバレッジなので**両方舐める**=数秒)。★救済分 `.cache/voldesc/recovered.jsonl` も材料に含める。
- seed既存ISBNは自動除外(純粋追加運用)。slugは**SRC stem名**で渡す。
- 出力 `.cache/voldesc/materials.jsonl` = {slug, title, authors, vols:[{vol,isbn,edition,caption,contents}], missing:[...]}

### Step2: AI生成 (Opus 4.8)
- materials.jsonl を読み、**1巻=1説明**を上の規律で書く。
- 同一巻が複数版にある場合は **standard(初出単行本)のISBNを優先**(文庫/新装は同文流用しない=別ISBNは別caption)。
- ★許容例外(うる星型 2026-07-20追認): **頁在ISBNにcaptionが無く、同一作品・同一巻番号の別版(新装版等)にだけある**場合、
  その版のcaptionを材料に**頁在ISBNキー**で書いてよい(内容は同じ巻。巻構成が版間で一致する時のみ)。
- 出力 `.cache/voldesc/out/batch-NNN.jsonl`: 1行= `{"isbn13":"9784...","slug":"...","vol":3,"desc":"..."}`
- **100巻/batch**。PUA文字混入時はPython経由で生キー書き出し(種3 fillと同じ注意)。

### Step3: seed適用 + commit
```
python scripts/_voldesc-apply.py ".cache/voldesc/out/batch-*.jsonl"
git add data/seeds/volume-desc-ja.jsonl && git commit -m "巻説明 +N件(volume-desc)" && git push
```
- 検証ゲート内蔵: isbn13形式 / desc≥60字 / 丸写し(50字連続一致・照合元=**captions-cache.jsonl 永続キャッシュ**) / 既存ISBN=dup skip。
  ★materials.jsonlはスライス毎に上書きされるため照合元にしない(2026-07-20: 並列運転で48件素通りした穴を封鎖済)。
- 毎バッチ `applied=N, dup_skip=K, rejected=M, overwrites=0` を確認して報告
  (= 月次蒸留の保護策と同形式。rejectedはバッチを直して再apply)。
- 報告形式: `🎉 Batch NNN 完了 (= X巻 / 欠落Y巻) [JST YYYY-MM-DD HH:MM:SS]`

## 運用ノート
- **材料なし台帳** `.cache/voldesc/no-material.txt` は bulk 速度用のカーソル。★ただし `--local-only` は
  ローカル harvest 履歴(全楽天ではない)に無い=材料なしと記録するため**偽陰性を含む**(2026-07-20 実測10%が実はlive有)。
- ★**偽陰性の回収 = recheckモード(Sonnet/アイドル向き)**:
  ```
  python scripts/_voldesc-material.py --recheck-nomaterial 300   # 台帳先頭300件をlive再照会・救済
  ```
  captionが在れば `captions-cache.jsonl` + `recovered.jsonl` に回収し台帳から除去(冪等・逐次保存・1.2s/req・429即中断)。
  救済分(recovered.jsonl)は**Opusが説明生成**→`_voldesc-apply`。台帳が尽きるまで繰り返す。
- ★**別版caption(うる星型)**: 頁在ISBN(標準版)のcaptionが空でも、同一巻の別版(文庫/新装)に在ることがある
  (うる星1巻=標準版空・文庫版62字)。材料scriptは頁の**全edition ISBN**を舐めるので yml に別版があれば拾う。
  yml に無い版だけに在る場合は per-case で `_lookup.py --creator` 補完。
- ★`--local-only` が**常に既定**(2026-07-21 ユーザ指示。per-caseでも live を使わない)。ローカル未収の巻は
  「材料なし」台帳行き→**Sonnetアイドル運転(柱⑦)がliveで敗者復活**→captions-cacheに入り次回のローカル収集で拾える。
  材料scriptは層1.5でcaptions-cache(救済分含む)を読む(2026-07-21追加)。liveはユーザ明示時のみ。

## NEVER
- 表示結線(promote/UI)を勝手にやらない(表示方法はユーザが後で決める)
- seed既存行の編集・削除(純粋追加のみ。直したい時はユーザ裁定)
- captionに無い内容の創作 / 全員分の人物紹介列挙 / caption丸写し
- live照会の自前再実装(材料scriptに封じ込め済。単発照会は `_lookup.py`)

## 関連
- 材料の series単位版 = skill enrich-catch-synopsis(キャッチ/詳細=作品単位。本skillは巻単位で別物・別seed)
- seed: `data/seeds/volume-desc-ja.jsonl` (isbn13キー・git追跡・高価なAI生成物=synopsis-ja.jsonと同格)

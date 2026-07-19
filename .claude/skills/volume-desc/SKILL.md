---
name: volume-desc
description: 巻説明つくって=単行本(巻)単位の説明文を楽天itemCaptionから生成しseedへ純粋追加。ストーリーは欠落なく長く・人物紹介コーナー禁止・丸写し禁止。Opus 4.8運転前提(2026-07-19新設)
---

# 巻説明生成 (= トリガー「巻説明つくって」「単行本説明つくって」)

**単行本(巻)単位**の説明文を、その巻の楽天紹介文(itemCaption+contents)から生成して蓄積する。
★**Opus 4.8 運転前提**(opus.bat セッションで回す。fable側はレビュー/反映担当)。
★**表示方法は未定** = このskillの仕事は seed `data/seeds/volume-desc-ja.jsonl` に中身を貯めるまで。
promote/UI結線は別途設計(勝手に結線しない)。

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

### Step1: 材料収集
```
python scripts/_voldesc-material.py --slugs a,b,c --live
python scripts/_voldesc-material.py --slugs-file list.txt --live   # 大量時
```
- キャッシュ順=予約キャッシュ→**rakuten-isbn-delta 1パス(830MB・数分)**→live(1.2s/req・429即中断)。
- seed既存ISBNは自動除外(純粋追加運用)。slugは**SRC stem名**で渡す。
- 出力 `.cache/voldesc/materials.jsonl` = {slug, title, authors, vols:[{vol,isbn,edition,caption,contents}], missing:[...]}

### Step2: AI生成 (Opus 4.8)
- materials.jsonl を読み、**1巻=1説明**を上の規律で書く。
- 同一巻が複数版にある場合は **standard(初出単行本)のISBNを優先**(文庫/新装は同文流用しない=別ISBNは別caption)。
- 出力 `.cache/voldesc/out/batch-NNN.jsonl`: 1行= `{"isbn13":"9784...","slug":"...","vol":3,"desc":"..."}`
- **100巻/batch**。PUA文字混入時はPython経由で生キー書き出し(種3 fillと同じ注意)。

### Step3: seed適用 + commit
```
python scripts/_voldesc-apply.py ".cache/voldesc/out/batch-*.jsonl"
git add data/seeds/volume-desc-ja.jsonl && git commit -m "巻説明 +N件(volume-desc)" && git push
```
- 検証ゲート内蔵: isbn13形式 / desc≥60字 / 丸写し(50字連続一致) / 既存ISBN=dup skip。
- 毎バッチ `applied=N, dup_skip=K, rejected=M, overwrites=0` を確認して報告
  (= 月次蒸留の保護策と同形式。rejectedはバッチを直して再apply)。
- 報告形式: `🎉 Batch NNN 完了 (= X巻 / 欠落Y巻) [JST YYYY-MM-DD HH:MM:SS]`

## NEVER
- 表示結線(promote/UI)を勝手にやらない(表示方法はユーザが後で決める)
- seed既存行の編集・削除(純粋追加のみ。直したい時はユーザ裁定)
- captionに無い内容の創作 / 全員分の人物紹介列挙 / caption丸写し
- live照会の自前再実装(材料scriptに封じ込め済。単発照会は `_lookup.py`)

## 関連
- 材料の series単位版 = skill enrich-catch-synopsis(キャッチ/詳細=作品単位。本skillは巻単位で別物・別seed)
- seed: `data/seeds/volume-desc-ja.jsonl` (isbn13キー・git追跡・高価なAI生成物=synopsis-ja.jsonと同格)

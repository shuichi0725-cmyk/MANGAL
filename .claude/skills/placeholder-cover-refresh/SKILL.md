---
name: placeholder-cover-refresh
description: 仮書影直して=発売前に付いた「文字だけの書影(.gif)」を楽天に実物が出たら差し替える。逐次保存・自然停止・冪等再開。Sonnet運転前提(アイドル運転の柱⑩)
---

# 仮書影の差し替え (= トリガー「仮書影直して」/ アイドル運転の柱⑩。2026-08-02 ユーザ発見で新設)

## 何の問題か

楽天は発売前・発売直後の本に**「著者名と書名を並べただけの画像」**を返す。実物が用意されると
★**URL自体が別物に変わる**★ため、こちらが引き直さない限り**永久に仮のまま出続ける**。
ユーザ報告「本物の書影が登録されたら勝手に変わるのかと思っていたらどうやら違うらしい」。

## 判定は URL の形だけで確実にできる (= 実測で裏取り済み)

```
本物 = .../{ISBN}_1_9.jpg    ← サフィックス _N_N 付き
仮   = .../{ISBN}.gif        ← サフィックス無し・拡張子 gif
```

実証(2026-08-02 live): HUNTER×HUNTER 39 は本番 `.gif` → live で `_1_9.jpg` が返った。
100万の命24・100億婚2 も同様。一方 0マン(1997)・100万回聞かせてよ(1999)は live でも `.gif` のまま。
= **新しい本は実物に差し替わり、旧作は絶版で永久に .gif**。

初回実測: 本番 **10,063巻**が `.gif`。うち **2025年以降=1,752巻**が対象(既定)。
2019年以前の約8,300巻は引いても無駄なので既定で除外(`--since-year` で変更可)。

## 運転 (= Sonnet。判断は要らない)

```
python scripts/_placeholder-cover-refresh.py --limit 200   # 1バッチ(~4.5分)。再起動で続き
python scripts/_placeholder-cover-refresh.py --stats       # 現在地
python scripts/_placeholder-cover-refresh.py --build-queue # 月1でqueue再算出=★次の周回の起点(これはOpus作業)
```

- ★**1バッチ終わったら同じコマンドを再起動**して続きを回す(④⑤⑦⑨と同型)。
- queue が尽きたら「消化済み(自然停止)」と出て終わる。**待たない・調べない**。
- **429 は script が backoff(2-45s)で自動吸収**し、連続429(実スロットル)だけ中断する
  (2026-08-03 偽429恒久対策: 旧の文字列マッチはJSON崩れの「column 429」を誤検知して停止していた。
  瞬断/JSON崩れは1件skipで走り続ける)。楽天レートは `_rate_gate` が
  ホスト単位で直列化するので、他の柱と並走してよい。
- 成果は `data/seeds/cover-override.jsonl` に**1件ごと追記**(停止しても残る)。
- 進捗は `.cache/placeholder-cover/done.json`(冪等再開の済み集合)。

### 締め (= バッチ後)
```
git add data/seeds/cover-override.jsonl && git commit -m "仮書影→実物 差し替え N件" && git push
```

## ★このskillが「やらない」こと

- **頁への反映はしない**。seed に書くだけ。実際に頁の書影が変わるのは上位モデルの
  「**反映して**」(reflect-targeted)か週次蒸留。Sonnetは seed 追記まで。
- **旧作(2019年以前)は既定で触らない**。引いても `.gif` のままで無駄撃ちになる。
  やるなら明示的に `--build-queue --since-year 2000`(Opus判断)。
- 書影URLの**構築はしない**(ISBNからパス/サフィックス/拡張子は推測不可=実URLのみ。
  2026-07-09 の実害で確立した規律)。

## 実測の目安

試走12件で**実物7件(約6割)**。1,752件を200件/バッチ=9バッチ、合計~40分で一巡する見込み。

## NEVER

- 楽天の呼び方を自分で組み直さない(★`Referer`+`Origin` ヘッダが無いと **403**。
  2026-08-02 に実際に踏んだ。script内の `rakuten_by_isbn` が正)。
- 429 で待機しない(他の柱を回す。[[idle-run]] の共通ルール)。
- `--build-queue` を毎バッチ走らせない(66k頁走査で数分かかる。月1でよい)。
- ★**「一巡完了」は終わりではない**(2026-08-03 ユーザ指摘で周回設計を実装): 実物への差し替わり時期は
  不定なので、「まだ仮のまま/no_item/error」だった巻も**次周回で全部引き直す**。--build-queue が
  done.json を自動rotateし、seed(cover-override.jsonl)在籍分だけを除外して再出発する(reflect前の
  二重照会防止)。= 月1の --build-queue → queue枯れまでバッチ再起動、の繰り返しが恒常運転。

## 関連

- 常設運転=skill idle-run(柱⑩) / 頁反映=skill reflect-targeted / 書影の全体計画=[[cover_harvest_plan]]
- 同種の「実URLのみ」規律=skill daily-distill の A2-7

---
name: backward-distill
description: 後退蒸留して <年>=過去年をNDLで発見→仕分け→AI worksheet→preview新規頁生成。掲載ゲート=必須メタ完備+楽天書影
---

# 後退蒸留して <年>

トリガー語: **「後退蒸留して 2024」** のように年付き。

## 手順 (= scripts/_distill_backward.py の3段)
1. `python scripts/_distill_backward.py <年> --discover` — NDL live(NDC726.1・月分割・**1.2秒/req・429=即中断**)。逐次保存=中断再開可
2. `--plan` — 仕分け: 漫画性フィルタ(_promote_drop_patterns.py) → A route(既存作の巻=種4化) / B route(新規作) → 楽天cache enrich → **掲載ゲート**(必須メタ: title/kana/romaji/authors/year/status/demographic/genre≥1 + 楽天書影v1) → AI worksheet + **欠落表**
3. worksheet 記入(AI): 新規登録protocol厳守(下記) → `--emit` — preview新規頁生成(検証: closed vocab/slug衝突/demographic enum/Zodミラー/日付pad/publisher master正規化/L1 booksGenreId/L2 tags)

## 新規登録protocol (= 順番固定・CLAUDE.md「新規登録 protocol」)
①全巻回収が先(単巻先行禁止) ②題確定=NDL×楽天突合(勝手命名禁止) ③ヨミ/著者=NDL典拠(不明=報告) ④一括登録 ⑤enrich=1巻基点・ネタバレ禁止 ⑥作れない物=欠落表(捏造して載せない)

## NEVER
- 429連打・捏造・単巻先行・closed vocabulary外のgenre・最終巻あらすじ丸写し
- 被覆台帳=distill-coverage.json を更新し忘れない
- 本番化はユーザ確認後(preview で見せて GO を待つ)

## 済み範囲
2022-2024は取得済(台帳確認)。重複は series_key/ISBN dedup が守るが、走る前に `--plan` の差分レポートで確認。

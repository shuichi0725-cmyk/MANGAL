---
name: productionize-drafts
description: 「本番化して」= 確認済み予約ドラフトをpreorder-pages(恒久)へ昇格+preview解放。次の週次蒸留で本番R2公開。トリガー「本番化して」。
---

# 本番化して (= 確認済み予約ドラフトの本番化。2026-07-09 ユーザ設計)

ユーザが preview で確認を終えた予約ドラフト(②③④)を、**週次蒸留で本番に載る状態**にする。
狙い: 日次蒸留で溜めたドラフトを恒久保管庫へ移し、**テスト環境を解放して別作業に移れる**ようにする。

## いつ使うか
- トリガー語「**本番化して**」(完全一致でなくてよい: 「本番化」「preorder載せて」「確認したので本番化」も同義)。
- 前提: ユーザが preview を**確認済み**(この skill 起動=確認完了の意思表示)。特定作のみなら slug 指定。

## やること (1コマンド)
```
python scripts/_preorder-productionize.py            # preview上の全予約ドラフトを本番化
python scripts/_preorder-productionize.py --slugs a,b # 指定分のみ本番化(残りはpreviewに据置)
python scripts/_preorder-productionize.py --keep-preview  # 本番化するがpreviewにも残す
```
内部で順に:
1. `_preorder-promote-drafts.py` = 各ドラフトを **`data/seeds/preorder-pages/`(git恒久・フルpromoteで合流)** + `data/manga.v2`(即時データ) へ。`_preorder_draft`注記を除去。**本番既存slug衝突はskip**。
2. 本番索引 `_build-list-index.py data/manga.v2 data --update <promoted>` 増分更新。
3. **previewから除去**(テスト環境解放) + preview索引再構築(`--keep-preview`で残せる)。

## 締め (必須)
```
git add data/seeds/preorder-pages data .preview-data   # ★data/manga.v2はgitignore対象=addに入れると失敗してchainが切れる(2026-07-11)
git commit -m "予約ドラフト本番化 N件(preorder-pages恒久・週次で公開)"
git push
```
- 変更slugは `.cache/preorders/last-promoted.json` に出る。commitメッセージに件数を入れる。

## この skill が「やらない」こと (= 誤解防止)
- ★**R2ライブ公開はしない**。preorder-pages/manga.v2(データ+git)まで。**実際に本番サイト(mangal-r2)に出るのは「週次蒸留して」**(フルpromote+R2 sync)。ユーザ設計どおり「溜める→週次でまとめて公開」。
- 即時に本番サイトへ出したい時だけ、続けて「**差分反映して**」(diff-deploy=部分ビルド→R2 PUT)。

## なぜ preview から除去するか
- 確認済み分は preorder-pages に**恒久保管**されるので preview に残す必要がない。
- ★除去で**テスト環境が空く**=次の日次蒸留(増加分だけ)や別作業がクリーンにできる(ユーザ要望「確認が終わったら別作業」)。
- ★増加分ゲート(`_preorder-increment.py`)が **preorder-pages の題を除外**するので、次の日次蒸留で**再カウントされない**(未promoteドラフトの再登場問題を根絶)。

## 報告形式
- 本番化 N件 / 衝突skip M件 / preview解放(残 K件) / 「次の週次蒸留で本番公開」を明示。
- 保留(hold)されていたドラフトは対象外(previewにも出ていない)=そのまま残る。

## 関連
- 生成=skill daily-distill(手順5がこの本番化) / 本番R2公開=skill weekly-distill / 即時=skill diff-deploy / per-case反映=skill reflect-targeted(予約ドラフトには使えない=SRC前提)

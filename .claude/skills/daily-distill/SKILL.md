---
name: daily-distill
description: 日次蒸留 — 前回以降のNDL新着漫画を取得し、掲載ゲート(必須メタ完備+楽天書影v1)を通る作品だけ掲載準備、足りない物は欠落表で報告する。トリガー「日次蒸留して」。
---

# 日次蒸留

前回カーソル以降の NDL 新着だけを処理する軽量ラン(通常数分)。実体は後退蒸留と同一コア。

## NEVER(禁止)

- **NDLが429/throttleを返したら即中断して報告**。リトライ連打・並行リクエスト禁止(レートは1.2s/req厳守)。
- **捏造禁止**: 著者/ヨミ/genre等が確定できない作品を推測で埋めて掲載しない → 欠落表へ(fail-closed)。
- **単巻先行登録禁止**: 巻不連続の作品は掲載せず「全巻回収要」として欠落表へ。
- worksheet の genre は **closed vocabulary(data/genres.yml の32キー)のみ**。新語禁止。
- catch/synopsis は**1巻の内容基点・ネタバレ禁止**。途中巻あらすじの丸写し禁止。

## 手順

1. `python scripts/_distill_daily.py --discover`
   - NDL live で当月分を取得(1.2s・resumable)。★出力に「429/throttle検知」が出たら中断・報告して終了。
2. `python scripts/_distill_daily.py --plan`
   - オフライン。**日次レポート**(新規掲載可 N / 新規欠落 M / 累計)が出る。カーソル自動更新。
3. 新規掲載可が有れば: `.cache/backward/<年>/ai-todo.jsonl` の該当 TODO を記入
   - `is_manga`(非漫画なら false) / `slug`(規則: ヘボン式・ハイフン区切り・勝手命名禁止=NDL/楽天ヨミ基点) / `genres`(closed vocab) / `demographic`(shounen/shoujo/seinen/josei/kids/general) / `catch` / `synopsis`(60-120字・ネタバレ無し) / `tags`(要素タグ=AniList流英語名1-3個・caption基点・**確信あるもののみ**、無理に付けない)
   - ★Layer1(自動): 楽天booksGenreIdが demographic裏取り(001001001=少年/002=少女/003=青年/004=レディース)+001021=BL自動付与。demographic空ならL1が埋める。
   - ★Layer2の参考rubric: `.cache/genre-rakuten/genre-cues.json`(学習済み特徴語)。
4. `python scripts/_distill_backward.py <年> --emit`
   - 検証(closed vocab/slug衝突/demographic enum)を通った作品だけ **preview生成(テスト先行)**。
5. preview索引更新 + push → **ユーザ確認 → GO後に本番化**(種2へINSERT-only=`--commit`ステージ※実装待ち)。
6. 報告: 掲載N件(題一覧) / 欠落M件(何が足りないか) / カーソル日付。

## 成功判定(機械照合)

- --plan が「カーソル更新」を出力している。
- --emit が「preview生成: N / 検証NG skip: M」を出力し、skip理由に想定外が無い。
- 掲載ゲートを通らない作品が preview に出ていない(欠落表と重複しない)。

## 関連

- 後退蒸留(過去年の一括版): `python scripts/_distill_backward.py <年> --discover|--plan|--emit`
- 掲載ゲート/欠落表の設計: CLAUDE.md「新規登録 protocol」+ memory distill_2026_pipeline

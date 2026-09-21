---
name: cover_tooling_traps_2026_09
description: "【道具の穴・両方修正済】書影2ツールの罠= covers --build が非冪等(14,909件消失) / fill-covers の Referer 旧ドメイン固定で全403"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3819afb2-c9d0-4149-93f3-a0615b0c157d
  modified: 2026-09-21T02:23:24.904Z
---

2026-09-21 月次1.2.20 の頁化で両方踏んだ。どちらも**静かに失敗する**タイプ。

## ① `_apply-covers-stage.py --build` は非冪等だった

既存 `data/seeds/covers.jsonl.gz` を**丸ごと上書き**し、入力の2キャッシュ
(`rakuten-isbn-delta.jsonl` / `rakuten-isbn.jsonl` + Kobo)に無い出所
(cover-override / live補充 / 仮書影差替)の書影を落としていた。
**実測 319,021 → 304,112 = 14,909件消失**(`git checkout` で即復元)。

→ 是正: キャッシュ側を優先しつつ**既存seedにしか無い分を継承**する純粋追加に変更
(復元後の再build = 319,394件 / 継承15,282)。
★**seed を全置換する `--build` 系は「既存の継承」を必ず確認**してから回す。

## ② `_rakuten-fill-covers.py` は Referer が旧ドメイン固定で全リクエスト403

`ORIGIN = "https://mangal.shuichi0725.workers.dev"` がハードコードされており、
楽天アプリ登録の参照元(mangal-db.com)と食い違って **20/20 が HTTP 403**。
→ `.env.local` の `RAKUTEN_REFERER` を使うよう修正(`_lookup.py` の `rakuten_live` と同じ出所)。
修正後は 19/20 取得(1件は楽天ヒット0)。

## 運用メモ

- この収穫器は**先に本番66k+previewのISBNを全走査**するので起動が重い(>15分)。
  少数の新頁だけ埋めたい時は `call_api` を import して対象ISBNだけ回す方が速い(実測30秒)。
- 書影が無い新刊は「楽天に無い」だけのことがある = **否定記録にしない**([[feedback_no_negative_record_on_failure]])。

関連: [[cover_harvest_plan]] [[rakuten_cover_data_asset]] [[cover_release_refresh_can_downgrade]]

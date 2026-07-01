---
name: reflect_protocol_fast
description: 【必ず使う】反映=targeted反映(数分)。per-caseにフルpromote(3時間)使うな。書影はpromote統合済。トリガー「反映して」
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1c2cd3c3-946e-46bd-ad68-956f057eed08
---

2026-07-01 ユーザ「反映が時間かかりすぎ」→恒久高速化。**per-case修正にフルpromoteは禁止**([[feedback_efficiency_first]])。

## 「反映して」= targeted反映 (既定)
```
python scripts/_reflect-targeted.py --only <変更stem,...> [--drop <削除stem,...>] [--push -m "msg"]
```
- 変更N頁だけ: drop削除→`promote --only`→索引`--update/--remove`(本番data+preview)→preview同期→push。**数分**。
- `--only`/`--drop` は **manga.v2ファイル名(=SRC slug)**。 slug-override頁もSRC名(夜明け=yoshida-akimi)。
- 触ったslugを列挙する(edition-overrides key / seed変更 → 対応slug)。詳細はCLAUDE.md「反映 protocol」。

## 書影はpromote統合済 (旧cover stage廃止)
- `_promote-bulk-v2.py` が書込直前の最終passで `covers.jsonl.gz`→null cover充填(`_cover_for`)。edition-canonical/override後に走り全経路カバー。
- 旧`_apply-covers-stage.py`の66k再走(~50分)不要。covers seed再生成時だけ `--build`。

## フルpromoteは月次蒸留の時だけ
- 引数無=全66k(~110分)。Windows完了後ハング→ログ「art-books (別ストリーム)」到達 or ファイル数で判定しkill。実行中manga.v2覗かない。[[promote_hangs_on_exit_windows]] [[monthly_distill_real_pipeline]]

## 本番R2 (重い別工程)
- next export→out/→`_r2-sync.py --bucket mangal-site`(差分・要R2認証)。テストは.preview-data pushで自動デプロイ(targeted反映が済ます)。
- 高速化候補(未): repoをDefender除外で全I/O短縮。

## 今回(2026-07-01)フル反映で確定した実測
- フルpromote~110分 / 旧cover stage~52分 / 全索引~10分 = 3時間。これをtargetedで数分に。golgo-13 targeted反映=書影220/220+177/177が~2分で付与実証。

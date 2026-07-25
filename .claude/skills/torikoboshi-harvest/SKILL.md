---
name: torikoboshi-harvest
description: 取りこぼしして/取りこぼし続けて=サイトに出ていない孤児作品(44,533件)の書誌を楽天からISBNで回収。cache→liveの2段・resumable・429即中断。Sonnet運転前提
---

# 取りこぼしハーベスト (= トリガー「取りこぼしして」「取りこぼし続けて」)

**サイトに1巻も出ていない作品**(= 孤児series)の書誌を、ISBNで楽天から回収する**素材収集**の柱。
頁化はしない(= 材料を貯めるだけ)。★read-only: 種2も本番もseedも書かない。

## なぜ在るか (= [[orphan_series_promote_is_srcpage_driven]])
promote は **元頁駆動**(`data/manga/*.yml` + `preorder-pages`)で **DB駆動ではない**ため、種2に在っても
元頁が無い作品は永久にサイトへ出ない。2026-07-25 実測 **44,533件**(全期間・成人/コンビニ本/非漫画/画集は除外済)。
種2は題・著者・巻しか持たないので、頁化に要る **正式題/題ヨミ/著者ヨミ/出版社/レーベル/発売日/書影/紹介文** を
楽天から取っておく。 [[new_manga_registration_order]] の「全巻回収→題→ヨミ→一括登録」の材料になる。

## 手順 (= これだけ)

```
python scripts/_torikoboshi-harvest.py --status              # 残数確認
python scripts/_torikoboshi-harvest.py --cache               # ①巨大キャッシュ1パス回収(数分)
python scripts/_torikoboshi-harvest.py --live --limit 500    # ②残りをlive(1.3秒/req)
```

- **①を先に**。 rakuten-isbn.jsonl(356MB) + -delta.jsonl(790MB) の1パス走査で大半が埋まる
  (2026-07-25 初回: 44,533中 **29,451件(66%)を回収**、残 15,082)。 ISBN毎に開き直さないこと。
- ②は `--limit` 単位で小分け。 **resumable**(出力済みISBNは自動skip)なので何度呼んでもよい。
  15,082件 × 1.3秒 ≒ **5.4時間** = アイドル運転で少しずつ消化する想定。
- 出力 = `.cache/torikoboshi/harvest.jsonl`(1行=1 ISBN、追記のみ・冪等)
  `{"isbn":..., "src":"cache|live|miss", "item":{楽天itemそのまま}}`

## NEVER / 罠
- ★**live呼出を自前で書かない**。 endpoint/header/`outOfStockFlag=1`/レートは `_lookup.py` に封じ込め済で、
  本scriptは `rakuten_live()` を import して使う。 コピペ実装は 400/429 の元 [[external-data-access]]。
- ★**1.3秒/req を縮めない**(429/IP遮断の実績)。 `_rate_gate` でホスト単位に直列化されるので、
  他の柱と並走しても合算429にならない。 **例外が出たら即中断**(連打しない)= script実装済。
- ★`--limit` 無しの一括実行はしない(数時間ブロックする)。 既定300。
- ★**この柱では頁を作らない**。 頁化は [[new_manga_registration_order]] の順番固定protocol
  (全巻回収→題確定→ヨミ確定→一括登録→enrichは登録後)に従い、**ユーザGO後**に別工程で行う。
- 対象リストの再生成が要る時は `python scripts/_audit-orphan-new-series.py --rebuild`(promote後は必須)。

## 進捗の見方
`--status` が `対象 / 取得済(実データ) / 残` を出す。 miss(楽天にヒットなし)も1行記録されるので
「取得済」には miss を含む。 実データ件数が別掲される。

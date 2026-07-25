---
name: torikoboshi-ndl
description: 取りこぼしNDLして/取りこぼしNDL続けて=楽天で埋まらなかった孤児作品をNDL(ISBN直引き)で補完。★NDLの題ヨミ(transcription)が取れる。resumable・429はbackoff吸収。Sonnet運転前提
---

# 取りこぼし第2パス = NDL補完 (= トリガー「取りこぼしNDLして」「取りこぼしNDL続けて」)

第1パス([[torikoboshi-harvest]] = 楽天)で埋まらなかった分を **NDL の ISBN直引き** で補う。
頁化はしない(= 素材収集)。★read-only: 種2も本番もseedも書かない。

## なぜ在るか
楽天は**在庫商品DB**なので、絶版の古書・極小出版は載らない。 2026-07-25 実測:
44,533件中 **1,989件が楽天ヒット無し**(2000年より前が835件 / 極小出版 / 外国ISBN111件)。
★ただし **NDLでは実在**(9784系10件をサンプル照合 → 10/10 実在・種2の題と一致) = 「無い作品」ではない。

★**NDLは `dc:title` 内の `dcndl:transcription` = 題ヨミ(分かち書き)を持つ**。
これは [[furigana_ndl_audit]] の通り ground truth で、**slug生成と索引ガードの土台**になる
(種2は title_kana が NULL のものが多く、それが頁化の障壁だった)。 2026-07-25 に `_lookup.ndl_live` へ抽出を追加。

## 手順
```
python scripts/_torikoboshi-ndl.py --status                  # 残数確認
python scripts/_torikoboshi-ndl.py --run --limit 300         # 1.3秒/req ≒ 7分/300件
python scripts/_torikoboshi-ndl.py --run --limit 300 --mode nokana   # 楽天ヒット有だがヨミ欠け(30件)
```
- `--mode miss`(既定) = 楽天ヒット無し **1,989件**(全部で約43分) / `nokana` = ヨミ欠け / `all` = 両方
- 出力 = `.cache/torikoboshi/ndl.jsonl`(追記のみ・冪等)
  `{"isbn":..., "hit":bool, "rec":{title,title_kana,series,series_kana,date,pub,creators,vol}}`
- **resumable**(取得済ISBNは自動skip)。 何度呼んでもよい。

## NEVER / 罠
- ★**live呼出を自前で書かない**。 `_lookup.ndl_live_retry()` を import して使う
  (endpoint/レート/ヨミ抽出の正本は `_lookup.py`。 コピペ実装は禁止 [[external-data-access]])。
- ★**長時間ジョブで `ndl_live()`(対話用)を直接使わない**。 429 で即 `sys.exit` するため
  一時スロットル1回で柱が止まる(2026-07-25 に楽天側で実害。 [[rakuten_long_job_needs_retry]])。
  retry版は backoff (3/10/30/90秒)。 ★NDLの回復は楽天より遅い(時間単位)ので待ちが長い。
- ★**1.3秒/req を縮めない**([[ndl_access_rate_method]] burst=429/IP遮断の実踏)。 連続8件失敗で中断。
- ★**NDL不在 ≠ 不存在**(BL/小出版は収録が弱い)。 埋まらないものは**埋めない = 登録保留**にする。
  推測で題やヨミを作らない [[feedback_accuracy_is_the_goal]]。
- ★**この柱では頁を作らない**。 頁化は [[new_manga_registration_order]] の順番固定protocolに従い、
  **ユーザGO後**に別工程で行う。

## 進捗の見方
`--status` が `対象 / 取得済(NDL実在) / 残` を出す。 NDL不在も1行記録するので「取得済」には不在を含む。

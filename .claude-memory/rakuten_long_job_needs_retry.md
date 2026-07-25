---
name: rakuten_long_job_needs_retry
description: 楽天長時間ジョブは rakuten_live_retry を使う。対話用 rakuten_live は429で即exit=柱ごと止まる
metadata: 
  node_type: memory
  type: project
  originSessionId: dff8a305-89f9-41d1-baa4-d9b9d0478784
  modified: 2026-07-25T04:55:03.087Z
---

★**楽天を叩く長時間ジョブは `_lookup.rakuten_live_retry()` を使う**(2026-07-25 確立)。

## 何が起きたか
取りこぼしハーベストを Sonnet に回させたら **3,147件(約73分)で停止**。「規制がかかった」ように見えたが、
恒久BANではなく**一過性のスロットル**(直後に単発照会は正常応答)。並走柱も無く合算レートでもなかった。

## 原因 = レートでなく **再試行の有無**
- `_lookup.rakuten_live()` は **429で即 `sys.exit(2)`**。 これは**対話照会としては正しい**安全設計(連打→IP遮断を防ぐ)。
- しかし数千件のループで使うと **1回の429で柱ごと死ぬ**。
- 3日連続で回せていた既存柱(`_rakuten-fill-covers.py`)は **3回リトライ+バックオフ(2秒→5秒)** を持っていた。
  間隔はむしろそちらの方が短い(1.05秒 vs 1.3秒)。 ★差はレートでなく再試行。

## 対処(適用済)
- `_lookup.py` に **`rakuten_live_retry(env, backoff=(2,5,15,45), **kw)`** を新設(単一ソース)。
  `rakuten_live` には `exit_on_429=False` を追加し、その時は `_lookup.Throttled` を送出。
- 長時間柱を横展開で切替: `_torikoboshi-harvest.py` / `_kana-digit-harvest.py`(アイドル⑧) /
  `_completion-judge.py`(アイドル④) / `_preorder-capture-captions.py`。
- 取りこぼし柱は **連続10件失敗で初めて中断** = 一過性スロットルと本当の遮断を区別。

## 教訓(型)
「対話用の安全設計」を**そのまま一括処理に流用すると必ず止まる**。 新しい長時間ジョブを書くときは
必ず retry 版を使う。 [[external-data-access]] [[long_job_ops]] [[orphan_series_promote_is_srcpage_driven]]

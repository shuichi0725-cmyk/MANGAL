---
name: lookup-isbn-live-cached-skip
description: "【道具の罠】_lookup.py --isbn --live はキャッシュに題があるとliveを叩かない(日付欠けの再照会に使えない)。NDLはimportしてndl_live(\"isbn=…\")直叩き。楽天が年しか持たない巻=発売未確定で載せない"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f8fa63b4-3ce7-45e1-b2ab-f3f4fbab02f4
  modified: 2026-09-03T23:56:50.607Z
---

**罠1**: `python scripts/_lookup.py --isbn <isbn> --live` は「即答層(isbn-title-map)に題がある」ISBNでは楽天/NDL live を
呼ばずに終わる(2026-09-03 実踏: 日付が空の8ISBNを再照会したら何も出なかった)。**日付だけ欠けたキャッシュ済ISBN**の補完には使えない。
→ NDLは `_lookup.py` を importlib で読み込み `ndl_live("isbn=9784…", maximum=5, exit_on_429=False)` を直接呼ぶ
(scratchpad/ndl_isbn.py の型。レートは `_rate_gate` が共有するので安全)。楽天は `rakuten_live_retry(env, isbn=…)`。

**罠2**: 楽天キャッシュの salesDate が「2024年」のように**年だけ**の巻は、告知だけで発売未確定/未登録の型
(デスサイズキューティー2/男子の品格2/夜の世界は美しい2…はNDLにも無い)。**載せない**。日次蒸留の予約ハーベストが
実発売日つきで拾うのを待つ。

**罠3**: 旧キャッシュ `.cache/rakuten-isbn.jsonl`(2026-06)は delta と食い違う誤記録がある(スポ×ちゃん4 と ひもろぎ守護神3 の題取り違え)。
複数ISBNをまとめて引くなら delta→旧の順に1パスで読む(scratchpad/rk.py の型)。決着は **NDL by ISBN**(スポ×ちゃん!4=2013.5で確定、
種2=MADB側が同ISBNを別作に付けていた)。

**Why**: 1ISBN=1パス(828MB)の `_lookup.py` を数十回回すと時間だけ溶ける。まとめ読み+NDL直叩きに切り替える。
**How to apply**: 日付欠け/題の食い違いは `_lookup.py --isbn --live` を信じず、キャッシュ1パス+NDL直叩きで裁く。[[external_data_access]] [[ndl_access_rate_method]]

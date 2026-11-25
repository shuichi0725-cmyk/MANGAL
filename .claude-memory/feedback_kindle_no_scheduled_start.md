---
name: feedback_kindle_no_scheduled_start
description: Kindle収穫は予約起動(sleepで時刻待ち)しない。ユーザが直接「回して」と言った時にその場で起動する
metadata:
  type: feedback
---
Kindle収穫(_kindle-asin-harvest.py)を「○時まで待ってから起動」の予約で仕掛けない。ユーザが直接頼んだ時にその場で起動する。

**Why:** 2026-11-25 ユーザ「直接頼むから予約はしないで」(429後1時間あけるため15:30予約をHaiku経由で仕掛けたら止められた)。
**How to apply:** 429直後に頼まれて1時間経っていなければ、予約せず「何時以降なら回せる」と伝えて待つ。運転条件の最新ユーザ指定 = Haikuで運転・KINDLE_ASIN_PACE=12・KINDLE_ASIN_BUDGET=0(上限なし)・KINDLE_ASIN_STOP_ON_ANY_ERROR=1(200以外1回で即停止、厳守)。関連 [[kindle_link_browser_not_app]]

---
name: bot-surge-2026-10-hold
description: 2026-10 ボット急増(OAI-SearchBot/AionBot)= robots.txt 対策はユーザ裁定で保留(実害が出るまで放置)
metadata:
  node_type: memory
  type: project
  originSessionId: 90be7524-8d30-456c-a82a-82daa7839fda
  modified: 2026-10-17T09:26:11.715Z
---

2026-10-16 のアクセス 約8.9万/日(人間は1日30〜80訪問)の大半がボット: OAI-SearchBot 25.8k(主に RSC の `.txt`)、
AionBot 23.7k(正体不明・97%が `/compass?from=…` = 作品頁ごとの羅針盤リンク約7万通り)、Semrush 7.0k、Ahrefs 4.9k、Reflectionbot 3.6k。
提案した robots.txt 4案(`/compass` 禁止・`/*.txt$` 禁止[IndexNow鍵はAllow]・SEO業者bot禁止・AionBot名指し)は
**ユーザ裁定「実害がまだ無いならほっとく」(2026-10-17)で保留**。

**Why:** 費用は Workers Paid の枠内(月1,000万req に対し月150万前後)、エラー率 0.001%、人間の閲覧に影響なし。
**How to apply:** 再提案するのは実害が出た時だけ = Worker の日次が数十万に達する / エラー率上昇 / 請求に従量が出る / 人間の表示が遅い。
数字は必ず `_cf-analytics.py`(eyeball のみ数える版)で取る = [[cf-analytics-unk-artifact]]。

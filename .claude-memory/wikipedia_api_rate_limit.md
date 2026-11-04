---
name: wikipedia_api_rate_limit
description: ja.wikipedia API の 429 の出方(本文50件まとめ取り17回目・存在確認だけでも10回)と回避 = 記事の有無は全題名ダンプで手元判定、本文は在る分だけ10件ずつ3秒間隔
metadata:
  node_type: memory
  type: reference
  originSessionId: 775cf950-3482-4109-9494-9364cc5fd0aa
  modified: 2026-11-04T02:35:26.596Z
---

2026-11-04 の連載誌検証(候補2,030頁の作品記事を引いた)で実測。

- `action=query&prop=revisions&rvprop=content` を **50題ずつ・1.2秒間隔** → **17回目(850題)で HTTP 429**。
- 60分の冷却明けに **存在確認だけ**(本文なし・50題ずつ・1.5秒)でも **10回目で再び429**。 = 回数そのものに天井がある(重さだけではない)。
- 429 を受けたら `_wiki_host.cooldown_set(60)` で共有の冷却を焼く(他の柱も止まる)。 冷却中は叩かない。

## ★回避の型(これで済んだ)
1. **記事の有無は全題名ダンプで判定**: `https://dumps.wikimedia.org/jawiki/latest/jawiki-latest-all-titles-in-ns0.gz`(16MB・248万題・リダイレクト込み・門は可)。
   照合キー = 空白→`_`、 先頭の英小文字→大文字。 APIで「無い」と出た題とダンプの食い違いは0件だった。
   → 1,766題の変種(全角！？・「 (漫画)」・副題落とし)を **API 0回** で「無い」と確定。
2. 本文は **在る分だけ**、 **10件ずつ・3秒間隔**(54記事を6回で取れて429なし)。
3. 手元の `.cache/wiki-sweep/`(9月の発売日掃引で取った1万記事)と `.cache/jawiki-title-hits.json`(頁→記事名)を先に使う。

## 罠
- 冷却待ちの自動再開で、 中断前に「記事あり」と記録した題を「処理済み」とみなして本文を取らずに飛ばした(55題)。 再開処理は「本文を持っているか」で判定する。
- UA にユーザのメールは入れない(既定の作法)。

関連: [[site-gate-robots-claude-denied]](Wikimedia API は門の対象外・作法で使う)[[magazine_corrections_mechanism]] [[data_assets_inventory]]

---
name: feedback_extract_full_source_data
description: 【戒め】リンクをもらったら要約でなく全明細を抜く(ユーザに貼り直させない)
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1c2cd3c3-946e-46bd-ad68-956f057eed08
---

ユーザにWikipediaリンク等の情報源をもらった時、**要約プロンプトで概要だけ取ってはいけない**。巻別ISBN/発売日の全表・全エディションの明細など、**必要な全データをその場で抜き切る**。

★失敗例(2026-06-30): ドラえもんWikiをもらったのに WebFetch を「各版の総巻数を簡潔に」で投げて要約だけ取得→てんとう虫45巻の巻別ISBN表を抜けず、ユーザに手で貼らせてしまった(「最初に張ったwiki見れなかったの?全部乗ってるよ」)。

**How to apply**:
- 情報源リンクをもらったら、WebFetch のプロンプトを「**全巻のISBN・発売日を一覧で漏れなく**」等、明細抽出型にする。要約語(簡潔に/概要)を使わない。
- 1回で足りなければ版ごとに分けて複数回 WebFetch する。表が大きくても全部取る。
- ユーザに「貼って」と言わせない=手元の源から自分で抜く([[acquire_all_obtainable_info]]と同根)。

関連: [[acquire_all_obtainable_info]] [[feedback_accuracy_is_the_goal]]

---
name: genre-disagree-adjudication-state
description: "ジャンル検品の不一致514を全裁定(2026-07-20): essay/4koma 86適用・回付37・保留391はWeb裏取り待ち。Gemini幻覚テンプレ注意"
metadata: 
  node_type: memory
  type: project
  originSessionId: f4071c28-d0c4-41f1-84b0-8f783d97925c
  modified: 2026-07-20T09:05:34.331Z
---

2026-07-20、Gemini検品の不一致(genre-verify-disagree.tsv=514行=Gemini案と現行が完全非重複)をOpusが全裁定。seedまで(週次で本番反映)。

## 裁定結果(514全件に処分)
- **適用86** → `data/seeds/genre-rakuten.yml` additions追記(promoteで`genres_rakuten:True`=provisional解除・確定)。**work_typeで構造的に確実な分のみ**: essay_manga 82 + 4-koma 4。現行のstory系(comedy/drama=題名推測)が明白な誤り。
- **回付37** → `docs/production-diagnostics/genre-route-nonmanga-artbook.tsv`。掲載可否の別工程(art_book 10=画集/原画集/ファンブック、non_manga 5=絵本/実用書/攻略本、教科書/評論/対談集/空提案22)。=ジャンルでなく[[non_manga_drop_cleanup]]/[[art_book_inclusion]]領域。
- **保留391** → `docs/production-diagnostics/genre-held-webverify.tsv`(story 289/short 91/educational 11)。

## ★保留の理由 = Gemini幻覚テンプレート
story_mangaにGeminiが確信度highのまま出す幻覚パターンが散見:「近未来を舞台にしたSFアクション作品」を無関係な題(アップル・シンデレラ等)に量産、「女子高生と教師の恋愛を描いた学園ラブコメディ」テンプレ乱発。現行も題名推測provisionalだが、幻覚ジャンルへの一括置換はskill(鵜呑み禁止=[[method_ai_generate_plus_webverify]])+[[feedback_accuracy_is_the_goal]]に反する。→保留391は**Web裏取り(NDL/楽天/魚)経由の個別 or 高品質再検品**が要る。ユーザ指示があれば裁定続行。

## 注意
- 検品レポート(`--report`)はverify-results.jsonlのgenres_now凍結値で分類=適用後も再verifyまで同じ514を表示(snapshot)。適用86は次のGemini再verifyでagree化して自然に消える。
- 正本skill=[[gemini_genre_audit]](gemini-genre-audit)。closed vocab=[[ai_genre_closed_vocabulary]]。

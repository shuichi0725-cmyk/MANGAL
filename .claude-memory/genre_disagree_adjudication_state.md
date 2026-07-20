---
name: genre-disagree-adjudication-state
description: "ジャンル検品の不一致514を全裁定(2026-07-20): essay/4koma 86適用・回付37・保留391=幻覚テンプレ。★Geminiジャンル検品はアイドル常設柱から退役(2026-07-20 ユーザ裁定)"
metadata: 
  node_type: memory
  type: project
  originSessionId: f4071c28-d0c4-41f1-84b0-8f783d97925c
  modified: 2026-07-20T09:20:24.242Z
---

## ★2026-07-20 ユーザ裁定: Geminiジャンル検品を退役
不一致514の**76%(391件)が幻覚テンプレ**という実績から、`gemini-genre-verify`(と連鎖のprobe)を
**アイドル運転の常設柱②から外した**([[idle_run]]の起動リストから削除)。理由=story系ジャンルの
Gemini判断は信用できず、使えたのは形式判定(essay/4コマ)だけ=常設で回す価値が薄い。
- **scriptは残す**: genre:other新バッチ等の**個別依頼時のみ**手動起動。採用は3ゲート+Web裏取り(鵜呑み禁止)。
- 既裁定の適用86(essay82+4コマ4)/回付37は週次で本番反映。保留391はGemini置換せず現行provisional据置。
- 代わりに柱⑦=巻説明recheck(volume-desc)を追加。

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

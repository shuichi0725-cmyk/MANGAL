---
name: seo-index-coverage-state
description: GSC「検出-未登録」6.65万対策=索引ハブ3点実装済(2026-08-31)。公開は週次待ち・効果はラグあり
metadata: 
  node_type: memory
  type: project
  originSessionId: bd02af38-42f4-4acb-9f59-ae607bc37eeb
  modified: 2026-08-31T10:02:33.900Z
---

GSC で 6.65万頁が「検出 - インデックス未登録」(初検出 2026-07-11、= クロール未着手バケット)。
診断 = ①新規ドメイン(mangal-db.com 2026-07-10〜)の信頼度不足 ②内部リンク網の弱さ
(/browse・/list はクライアント描画=静的HTMLにリンク0、作品頁の回遊リンクは /browse?query= 形式=クロール行き止まり)。

**2026-08-31 実装済(commit 6a866a37d)**:
1. sitemap 増強: 著者頁20,215(out/author 実在一覧から=lib/authors のキー計算を再実装しない)+ /titles 351 + /authors,/titles → 計90,041 URL
2. `/titles` 題名50音索引ハブ新設: `_gen-titles-pages.py` → `titles-pages.json` が**単一ソース**(app/titles と _gen-sitemap.py の両方が読む=分類二重実装のURL不一致根絶)。週次step1に `titles-pages` step(★list-index の後=索引から導出)
3. 関連作品の穴埋め: 孤立頁(強シグナル0件≈8%)に同誌→同ジャンル×発表年の近い順で8件充填。ロジックは `lib/related.ts`(vitestがJSX非対応のため.tsxから分離)。人気順でなく**年の近さ**で選ぶ=被リンクを無名頁にも回す設計

**残レバー**: ①外部被リンク=ユーザ側作業(効果大) ②sitemap lastmod=見送り(信頼できる per-URL 更新日が無い。誤lastmodは逆効果) ③本番公開=次回週次蒸留(CODE週フルビルド)待ち。
**期待値**: 効果はハブがクロールされてから芋づる式・数週間〜数ヶ月ラグ。週次後の GSC で「検出→クロール済み」への移動を見る。
関連: [[browse_ssr_shell_and_seo]]

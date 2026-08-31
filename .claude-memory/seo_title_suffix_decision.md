---
name: seo-title-suffix-decision
description: 2026-08-31 全頁titleサフィックス=「| 漫画・コミックのMANGAL」に変更(ユーザGO)。作品頁titleへの「(漫画)」直挿しはB案として見送り
metadata: 
  node_type: memory
  type: project
  originSessionId: 5c11eb8b-0ad8-4376-a82d-b5754dc90f42
  modified: 2026-08-31T14:55:55.396Z
---

2026-08-31 ユーザGOで確定したSEO title方針:

- **A案採用**: `app/layout.tsx` のtitleテンプレート = `%s | 漫画・コミックのMANGAL`(全66k頁に「漫画」「コミック」が乗る。シーモア型=ブランドサフィックスにキーワードを背負わせる定石)。
- **C案採用**: 作品頁のfallback description に「漫画全巻一覧」(catch/synopsis有りの頁は対象外)。
- **B案見送り(ユーザ裁定)**: 作品頁titleに「(漫画)」を直接挿す案は不採用。再提案しない。
- /shinkan のtitle = 「漫画コミック 新刊発売日一覧」(検索クエリ「漫画 発売日」狙い)。
- 同日、ページ側で「| MANGAL」を自書きしていた7頁(shinkan/color-manga/contact/rankings/sansedai-archive/adult-triage/zenshuu)の**二重サフィックスバグ**を是正済(templateが付けるのでページ側は書かない)。app/browse と app/page.tsx にはこの旨のコメントが元から在る。
- **注意**: サイト全体のtitle変更なのでGoogle再評価で順位が数週間揺れうる。「順位が下がった」報告が来たらまずこの変更日(2026-08-31、本番反映は次の機能蒸留/週次)を思い出す。

**Why:** 「漫画コミック探すならMANGAL」的な露出をユーザが希望。詰め込み(漫画コミック連結を毎頁)はGoogleのtitle書き換えを招くためサフィックス集約にした。
**How to apply:** 新ページのmetadataでは「| MANGAL」を書かない(templateに任せる)。titleへのキーワード追加提案はA/C路線の範囲で。関連: [[seo_index_coverage_state]]

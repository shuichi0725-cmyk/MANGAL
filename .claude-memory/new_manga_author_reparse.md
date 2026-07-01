---
name: new_manga_author_reparse
description: 新刊著者の連結バグ(矢立肇富野由悠季型)を源creators_roledから再パースで是正+seed化+promote結線。蒸留で再発しうる
metadata: 
  node_type: memory
  type: project
  originSessionId: 40db3460-5533-4358-8d06-8214ea9ecaea
---

蒸留の新刊で**著者が連結表示**される問題(2026-06-26是正)。例: `オノ・マサユキ阪元裕吾`(2名連結)/`大野木寛ストーリー協力`(役割連結)/`ジジ&amp;ピンチ`(未デコード)/`矢立肇富野由悠季`。

## 根本原因
源データ `creators_roled`(NDL discovery)は **共著者を「, 」(カンマ)区切り**(姓名は「・」結合)で持つ: `オノ・マサユキ, 阪元裕吾:原作/八貫徹世:漫画`。だが `_distill_preview.py parse_authors` は **`∥／` でしか分割せず**カンマを分割しない→連結。役割空時の名前末尾役割(`大野木寛 ストーリー協力`)も未分離+`&amp;`未デコード。

## 修正(再パース)
`scripts/_reparse-new-authors.py`(dry-run/--apply): 源roled(ISBN/題名で突合)を再パース。①共著者を `,、∥／` で分割(★`・`は名前内[オノ・マサユキ]なので温存) ②空role時に末尾役割を分離=ブラケット`[著]〔著〕`+スペース`ストーリー協力/コミック/まんが/スーパーヴァイザー`等(ROLEW正規表現)→credits or 原作へ ③`html.unescape`で`&amp;`デコード。安全=**著者ゼロ化skip**・**名前喪失なし**(役割者はcreditsへ移すだけ)・backup(`.cache/authors-bak-*`)。**55作**適用(preview+本番manga.v2)。

## 永続化(durability)= 2層
1. **seed** `data/seeds/author-reparse-2026.json`(slug→{authors,original_authors,credits})。
2. **promote結線** `_promote-bulk-v2.py`(build_yml後にseedで上書き、★`enrich_author`を通すので分割後の名前にもヨミ/romaji付与=実証 阪元裕吾→サカモトユウゴ)。次promoteで`著者修正(新刊・連結是正): 55`。種2不変のまま表示是正。

★源突合できない新刊(55外)は触らない=別途NDL再fetchで救済可。蒸留で再発したら同手順。関連=[[author_pollution_overlay_fix]](旧作の役割剥離)・[[distill_2026_pipeline]]。

---
name: author-name-space-conventions-conflict
description: 【✅裁定済】著者名の空白=照合側で吸収(authorKey)。表記は触らない。一括機械是正は禁止
metadata: 
  node_type: memory
  type: project
  originSessionId: e65fec7d-934a-44f5-8087-f90ac21cce9c
  modified: 2026-07-21T12:34:36.591Z
---

著者名表記に**2つの流儀が併存**していることが2026-07-21の日次蒸留検品で確定:

- **旧MADB系**(本体67k頁の大半) = 無空白(高橋留美子/蟹沢ちひろ)。
- **2026新刊系**(daily-distillドラフト→preorder-pages) = 楽天authorの「姓 名」空白を保持(670/2476名)。本番索引全体では空白入り950名。

**実害**: 同一人物が空白違いで別著者に分裂する(実証=蟹沢ちひろ: 本番に無空白で既存+新ドラフトが「蟹沢 ちひろ」)。著者頁・著者フィルタが割れる。

**★一括機械是正は禁止**(2026-07-21に一度誤適用して学習):
- 「ユズキ カズ」等、**空白が公式表記のペンネーム**がある。
- 欧文名(Ark Performance/Crazy Raccoon/Mr.General Store/Oda Kogane/Team Argo等)の空白は正当。cacheドラフトへの一括除去で6名壊し、楽天源泉から復元した。残り要確認3件=`.cache/preorders/drafts/_REVIEW-NOTE-latin-names.txt`。
- 是正するなら「日本語姓名かつ本番に無空白同名が既存」の分裂ケースに限定するか、著者indexの照合キー側で空白を無視する(表記は触らない)のが安全。

**★裁定(2026-07-21ユーザ承認=推奨案)**: 表記は触らず**照合側で空白無視**。実装済み:
- lib/filters.ts の authorKey() = 空白除去キー。著者フィルタ(applyFilters)/50音索引(authorsWithKana)/uniqueAuthors/関連作品(RelatedWorks)が空白違い横断で束なる。表示名は無空白形優先。
- ドラフト生成器(_preorder-gen-preview/-midfill)= 日本語のみ著者名の楽天「姓 名」空白を除去(欧文保持)+midfill year=最古巻年。
- 本番950名の表記自体は不変(是正不要=照合で吸収)。新規の著者名照合を書く時は必ず authorKey を通すこと。関連 [[feedback-accuracy-is-the-goal]]

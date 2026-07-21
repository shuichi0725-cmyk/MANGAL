---
name: author-name-space-conventions-conflict
description: 【未決】著者名の空白=2流儀衝突(MADB系無空白 vs 2026新刊楽天系「姓 名」空白)。一括機械是正は禁止・ユーザ裁定待ち
metadata: 
  node_type: memory
  type: project
  originSessionId: e65fec7d-934a-44f5-8087-f90ac21cce9c
  modified: 2026-07-21T12:02:45.612Z
---

著者名表記に**2つの流儀が併存**していることが2026-07-21の日次蒸留検品で確定:

- **旧MADB系**(本体67k頁の大半) = 無空白(高橋留美子/蟹沢ちひろ)。
- **2026新刊系**(daily-distillドラフト→preorder-pages) = 楽天authorの「姓 名」空白を保持(670/2476名)。本番索引全体では空白入り950名。

**実害**: 同一人物が空白違いで別著者に分裂する(実証=蟹沢ちひろ: 本番に無空白で既存+新ドラフトが「蟹沢 ちひろ」)。著者頁・著者フィルタが割れる。

**★一括機械是正は禁止**(2026-07-21に一度誤適用して学習):
- 「ユズキ カズ」等、**空白が公式表記のペンネーム**がある。
- 欧文名(Ark Performance/Crazy Raccoon/Mr.General Store/Oda Kogane/Team Argo等)の空白は正当。cacheドラフトへの一括除去で6名壊し、楽天源泉から復元した。残り要確認3件=`.cache/preorders/drafts/_REVIEW-NOTE-latin-names.txt`。
- 是正するなら「日本語姓名かつ本番に無空白同名が既存」の分裂ケースに限定するか、著者indexの照合キー側で空白を無視する(表記は触らない)のが安全。

**How to apply:** 方針はユーザ裁定待ち。裁定までは新規ドラフトの著者表記を勝手に変えない(検品で分裂実証がある個別ケースのみ報告ベースで)。関連 [[feedback-accuracy-is-the-goal]] [[feedback-one-bug-means-a-class]]

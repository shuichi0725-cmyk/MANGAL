---
name: project-architecture-seeds
description: MANGAL の 種1 / 漫画家マスター / 種2 / 種3 / 種4 / 本番 DB のピラミッド構造
metadata: 
  node_type: memory
  type: project
  originSessionId: 0f064c18-034b-4d7f-b14a-3625a848da25
---

# MANGAL data pipeline 構造 (= ユーザ確認済)

```
種1 (= MADB raw: cm101.csv / metadata101.json)  +  漫画家マスター (= data/seed/mangaka.csv, 6,751 名)
                    ↓ build (= 4 層 adult filter / publisher 名寄せ 等)
種2 (= .cache/db-v2.sqlite, 約 166,000 series)
                    ↓ AI fill (= Claude が magazine / genres / synopsis / alt_titles.en / anime / status / title_kana を補完)
種3 (= data/seeds/series-supplement-v2.yml, 76,435 entries)
                    ↓ merge (= 種2 の構造 + 種3 の補完 + 種4 の巻補完)
本番 DB (= data/manga/<slug>/index.yml 群、 Next.js frontend が静的読み込み)
```

- **種4** (= data/seeds/volumes-supplement.yml) = MADB 取込もれ巻の **手動補完** (= 種3 と独立、 本番生成時に load)。 詳細は CLAUDE.md 「種4」 節。
- **最終目的** = Amazon アフィリエイトサイト (= PA-API 承認後)。

## 注意

- `data/seed/mangaka.csv` は **種1 ではなく 漫画家マスター** (= 種1 の sibling input)。 「種1 = mangaka master」 と短絡しない。
- 種2 `series.qid` は **作者QID** (= 作品QIDでない)。 → [[shu2-qid-is-author]]
- フリガナは 2 形式 (= HP表示用 / slug生成用)。 → [[shu3-kana-two-forms]]

関連: [[openbd-eol-amazon-required]]

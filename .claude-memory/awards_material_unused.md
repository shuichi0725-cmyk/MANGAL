---
name: awards_material_unused
description: 【宿題】受賞歴データは2026-07-17に採取済みで .cache に眠ったまま未使用(著者196/作品68)。Wikidataは作品側にP166を持たず著者側にある。wiki infoboxのaward抽出は出力schemaが落としている
metadata:
  type: project
---

2026-09-18、mangaseek のうる星やつら頁と突き合わせて発見。

## 事実

mangaseek は作品頁に **小学館漫画賞(第26回)〔1980年〕/ 星雲賞(第18回)〔1987年〕** を出している。
MANGAL は表示ゼロ。**だが素材は既に採ってある**:

`.cache/enrich-material/awards-authors.jsonl`(2026-07-17 収集)
```
Q219948 高橋留美子 → 小学館漫画賞(1981) / 星雲賞 コミック部門(1987,1989) /
                     紫綬褒章(2020) / アイズナー賞 殿堂(2018) / インクポット賞(1994) 他8件
```

- 被覆: **作品 68/5,534(1.2%) / 著者 196/6,751(2.9%)**。薄いが高名作は入っている。
- ★**Wikidata は作品側に賞を持たない**。実測 `Q715723`(うる星やつら)の P166 = **0件**、
  著者 `Q219948` = **8件**。賞は著者に付いている。作品側を埋めたいなら別ソースが要る。
- ★`_material-harvest.py` は Wikipedia infobox の `受賞` 正規表現を持っているのに、
  **出力schemaが award を落としている**(`wiki-extract.jsonl` 3,478行のキーは
  slug/article/magazine/volumes_total/hiatus_mention だけ。受賞らしき値は9行・しかも
  「公式サイト」「サイン」への誤マッチ)。**ここを直せば作品側が埋まる可能性がある。**

## なぜ記憶に残すか

`.cache` は **gitignore = GitHub非バックアップ**。CLAUDE.md が警告している
「簿記は走ったのに出力が .cache に落ちて消え、あるはずなのに無い」事故の予備軍がここに在る。
2ヶ月眠っていた。

## 着手するなら

1. `_material-harvest.py` の wiki infobox 抽出で award を出力schemaに乗せ直す(誤マッチも直す)
2. 素材を git 追跡の seed へ移す(`.cache` に置きっぱなしにしない)
3. 頁に出す(著者頁 or 作品頁。作品側はWikidataが持たないので著者経由の表示が現実的)

★私の初読は誤りだった: row[0] だけ見て「全部空」と報告しかけた。**jsonl は1行目で判断しない**。
[[feedback_sanity_check_tool_warnings]] [[acquire_all_obtainable_info]]

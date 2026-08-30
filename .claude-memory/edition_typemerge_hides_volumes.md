---
name: edition_typemerge_hides_volumes
description: promoteは同typeの版を1タブに畳むため別出版社の版が合流し巻番号衝突で巻が消える。233頁976巻。検出器あり
metadata:
  type: project
---

promote の版タブ生成は既定で **`group_key = effective_type`**（standard/bunkobon…）だけで束ねる。
そのため種2が**別々の edition として持っている版**が1タブに合流し、
**巻番号の衝突で負けた側の巻が本番から丸ごと消える**。番号は埋まるので**「巻抜け」にすら見えない**。

**Why:** 隻眼の竜（2026-08-30、コンビニ掃引 bucket B）で発覚。「Akita top comics wide が6巻で
主版5巻より多い」として挙がったが、中身はリイド社SPコミックスのISBN（978-4-8458）で
秋田書店のレーベル名を名乗っていた。種2の4版が standard 2版・bunkobon 2版に合流し、
**秋田文庫4巻と秋田版2巻が丸ごと不可視**だった。

**How to apply:**
- 検出 = `python scripts/_audit-edition-typemerge-loss.py` → `docs/production-diagnostics/edition-typemerge-loss.tsv`。
  初回実測 **233頁タブ / 976巻消失**（最大 shaman-king 59巻、風雲児たち23、百鬼夜行抄22）。
  LOST=0 の542件はレーベル名が混ざっただけで巻は失っていない＝優先度低。
- ★判定は**名前でなく出版社の実体**（ISBN→種1 metadata101 schema:publisher）。
  imprint文字列比較だと X の「あすかコミックス / ASUKA COMICS」型の表記ゆれを誤検出する。
  isbn→出版社355,408件は `.cache/isbn-publisher.tsv` に焼いて再利用。
- ★是正は**per-case で canonical seed を起こす**（隻眼の竜が型見本）。共有ロジックは触らない:
  - `group_key` を (type×imprint) にすると ARMS型の表記ゆれを誤って割る [[imprint_split_arms_type]]
  - `separate_editions`(series-merge.yml) は **sid単位**の分離なので、1つのsidが複数版を持つ形には効かない

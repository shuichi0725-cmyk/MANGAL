---
name: promote_merge_respects_drop
description: promoteのfind_related_series_idsがdrop済series(non-manga-drop)をmerge clusterから除外するようになった(2026-06-16)。drop=単独ページ化停止だけでは同題merge経由で巻が他ページに混入していた構造バグの修正
metadata: 
  node_type: memory
  type: project
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

★**2026-06-16 修正**: `scripts/_promote-bulk-v2.py` の `find_related_series_ids` が、merge cluster から **drop済 series_key(non-manga-drop.yml)を除外**するようになった(`_DROP_SERIES_KEYS` グローバル + 末尾フィルタ、main自身は必ず保持)。

**直した構造バグ**: それまで `non-manga-drop` は「そのseriesを**単独ページの主にしない**」だけで、`find_related_series_ids` の**同題auto-merge**(qid一致/title一致/kana一致)経由では drop済seriesの巻が**実ページに混入**していた。

**実例(コナン映画)**: 映画フィルムコミック(`qid:Q313945|name:名探偵コナン 世紀末の魔術師` 等)をdrop登録しても、同題のコミカライズページ(`qid:Q11657721|…`)に film の上/下巻が merge され、**film+comicalize 混在ページ**になっていた。修正後、世紀末ページは comicalize VOL1/2/3 のみにクリーン化。

**含意**: 外国版drop([[non_manga_drop_cleanup]])・雑誌drop なども今後 merge に混入しない。drop は「ページ化停止」+「merge除外」の二重効果になった。**drop追加後は再promoteで他ページへの混入解消も効く**。

関連: コナン映画の漫画版/フィルムコミック分離方法は [[conan_movie_filmcomic_method]]。

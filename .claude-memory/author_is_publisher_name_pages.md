---
name: author_is_publisher_name_pages
description: 【宿題】著者欄が出版社名(小学館/講談社等)になっている本番頁9件=楽天placeholder型。予約経路はゲート済、本番側は未是正
metadata: 
  node_type: memory
  type: project
  originSessionId: 450de73b-b605-4986-907d-85f528e9a408
  modified: 2026-09-02T11:36:31.140Z
---

2026-09-02 日次蒸留で発見。楽天は著者未登録の本で `author` に**出版社名**(「小学館」等)を返す(みにくい小鳥の婚約(1) 9784098736386 = live照会でも「小学館」)。
予約ドラフト生成器には「著者=出版社名→保留」ゲートを焼いた(`_preorder-gen-preview.py` 2026-09-02)。

**本番側の残**: 一覧索引で著者名が 小学館/講談社/集英社/秋田書店 と一致する頁が **9件**
(enueichikee-darwin-ga-kita / houkago-pedal / crows-kaizokuban / houkago-no-iruma-kun / shin-yokohama-de-aimashou /
houkago-pedal-hai-keidensu / pon-no-michi / long-pass-kawajirou-tanpenshuu / unmei-no-hito-zettai-ni-kotatsu-no-futonmitaina-outer-kitenai)。
**Why:** 著者欄が出版社名=誤データ(著者不明を埋めた形)。著者索引/著者頁にも「小学館」という著者が立つ。
**How to apply:** 各頁の巻ISBNで NDL/楽天(_lookup.py)から実著者を取り、`author-role-corrections.yml` の remove+add で是正。
判明しない頁は著者空のまま(捏造しない)。他の出版社名(KADOKAWA/白泉社等)も同じ手で索引を掃く。[[feedback_never_default_author_role]] [[author_data_map]]

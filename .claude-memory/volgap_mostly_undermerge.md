---
name: volgap_mostly_undermerge
description: 巻抜け(vol_gap)の大半は取込もれでなく「種2に在るが別クラスタで未merge(under-merge)」or「別作(spinoff/homonym)」。NDL→種4は真の取込もれだけ安全収穫、registerが種2既存ISBN除外で過剰統合回避
metadata: 
  node_type: memory
  originSessionId: 04923414-a96f-48e2-b7f4-5622fc881e58
---

2026-06-29。本番診断の巻抜け712作をNDLで調査した結論。

**NDL→種4パイプライン**: `_gen-volgap-ndl-drafts.py`(欠番巻をNDL title検索・出版社prefix制約・既存ISBN→db-v2 series_keyでbind) → `.cache/seed4-drafts.yml` → `_register-seed4-ndl.py --apply`(検証して volumes-supplement-auto.yml 登録)。書影は楽天ISBN直引き。NDL先(楽天でない)=[[ndl_volume_completion_better_than_rakuten]]。

**★決定的発見(batch40で87件中)**: 登録OK **1** / **種2に既存ISBN 86**。つまり欠番巻の大半は:
- ①**under-merge**: 巻は種2に実在するが**別sid(別クラスタ)で この作品ページに未merge**(例: 空手バカ一代vol18=別sid)。
- ②**別作(homonym/spinoff)**: NDL title検索が拾うが実は別作(例: こち亀vol2の正体は「秋本治のナイス!なチョイスこち亀」spinoff)。**追加したら過剰統合**。
- ③真の取込もれ(種2に無い)=少数(~1/87)。

**★registerの検証が安全網**: 「種2に既存ISBN→pending(取込もれでない)」「series_keys bind不可→pending」「巻番号既存→pending」で、**真の取込もれだけ登録**し②の過剰統合を自動回避。だから全712を流しても安全(genuine だけ拾う)。

**帰結**:
- 巻抜けは NDL→種4 では**少数しか直らない**(大半が取込もれでない)。
- ★主因の under-merge(同一作が別sid)は**別途 慎重なmerge**が要(著者一致確認でhomonym回避=[[shared_isbn_overmerge_homonym_guard]] [[merge_needs_external_proof]])。spinoff(ナイス!チョイス型)は別ページが正しいので触らない。
- 多版作の片edition gap(こち亀文庫版等)は番号が他editionに在れば register が重複skip。

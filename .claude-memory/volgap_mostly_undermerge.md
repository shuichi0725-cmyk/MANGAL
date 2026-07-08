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

## ★qidベース系統抽出=不可(2026-07-08 実証)
under-merge(別クラスタに実在)を自動で拾おうと「同qid配下に欠番巻がISBN付き実在」で313作走査→83候補。だが**qid=著者**([[shu2_qid_is_author]])なので**大半が同著者の別作品の誤検出**:
- 特選OL進化論←OL進化論本編(特選=廉価版=別プロダクト) / Bartender←ソムリエール(別作) / カイジ←黙示録・破戒録(別部) / キングダム←紛れた日本の歴史vol9の幻。
- 題名正規化(新装版/特選/カタひら吸収)で絞っても18作全て誤検出(白のフィオレンティーナ←海の綺士団等)。
- ★結論: **安全な本編分裂の自動一括抽出は無理**。per-caseで外部確証(Wiki/NDL/ISBN連番+日付連続)を取ってから統合するしかない。
- ★**成功例=かりあげクン**(2026-07-08): variant題が全て「かりあげクン」(ほんにゃらゴッコ→ほんにゃらごっこ→かりあげクン=題名変遷)で、ISBN連番(9784575943-945)+発売日連続で本編確証→全69巻統合(双葉社アクションコミックス)。**variant題が主題名の派生(同一作の題名変遷)である**時だけ安全。別作/廉価版/別部は除外。
- ★真の取込もれ(種4-addable)も稀=最近の連載中作品の最新刊のみ(俺だけ不遇スキルvol16/交際vol2=NDL照会で発見)。古典はpre-ISBN(放置)。

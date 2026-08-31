---
name: konbini-sweep-2026-08-state
description: コンビニ廉価/抜粋版の全DB掃引(2026-08-30〜31)の完了状態と、残るユーザ裁定待ち3件
metadata: 
  node_type: memory
  type: project
  originSessionId: 6f8d0133-4fb3-4b84-85b2-cbf93735fe72
  modified: 2026-08-31T02:32:35.789Z
---

コンビニ掃引 = **検出器 `scripts/_audit-konbini-editions.py` が正本**(HIGH=確定レーベル/SETTLED=シロ裁定の固定/3条件ゲート)。出力=`docs/production-diagnostics/konbini-triage.tsv`。

**完了(2026-08-31時点)**: 第1波(Opus) A49版+B/D後続8版 → 第2波(見直し) 網の穴追補で13版/8頁drop(Comic魂別冊系・King series漫画スーパーワイド・SPポケットワイド)+洗礼の同type合流解体+短編集3巻補完。現況 **A/B/D=0、C(単独版)99・E(シロ)57のみ**。

**重要な学び**:
- ★セレクション版しか無い頁は「コンビニ再刊」と限らない: **ゴータマ/もんもんアカデミー=YJCセレクションが初単行本**(NDLに他版なし)=keepが正。原版有無をNDL creator束縛で確認してから裁く。
- ★洗礼型: コンビニ版ISBNが同type合流で原版の巻に接ぎ木される→単純dropすると原版が消える。canonical解体が正。[[edition_typemerge_hides_volumes]]

**ユーザ裁定待ち(未着手)**:
1. **男花田秀治郎**(otoko-hanada-hidejirou): 原版=『花田秀治郎くん』立風書房1976全2巻+立風漫画文庫1978(NDL確認済)。頁題がセレクション再刊題のまま=改名(slug rename)を伴うためGO待ち。
2. **短編集**(tanpenshuu): title=総称「短編集」・kana=モウチャンワツヨカッタ(1巻題の読み)は破損。正=「ちばあきお名作集 短編集」系への改名裁定待ち(巻補完は適用済)。
3. **nippon-chinbotsu頁の別作品同居疑い**: 一色登希彦版(ビッグコミックス15巻・主版)とさいとう・たかを版(1973チャンピオン/SPコミックス/講談社版)が同一頁=別作画者の別作品→ギャラ式頁分離のGO待ち。

**保留(証拠不足)**: Goma books(2019劇画復刻・POD/廉価の別が未確定)=子連れ狼8巻/ダミー・オスカー2巻は残置。

---
name: volgap_fill_pipeline_2026_09
description: 【機構・再利用】巻抜けを「ローカル楽天種→NDL→under-merge結線」の3段で埋めるパイプライン。決定打はISBN連番ゲート
metadata: 
  node_type: memory
  type: project
  originSessionId: a6e17d72-d62d-4a2e-a121-36a8fd75a363
  modified: 2026-09-06T15:52:15.957Z
---

2026-09-07 ユーザ指示「ローカルの楽天で巻抜けが補完できる物があるか一つずつ調べて修正して。無ければndl」。
468頁 → **408頁**(旧模型)/実測 430頁(版単位是正後)まで詰めた。**128巻を補完**(楽天58+NDL46+under-merge24)。

## 道具(この順に回す)
1. `scripts/_volgap-gap-targets.py` — 残gap頁 → 「どの版の何巻を埋めるか」の表。
   ★**版(edition)単位**で穴を取る + 先頭欠け(LEAD)も出す + **経路**を判定
   (`seed4` / `canon:volumes` / `canon:compact` / `canon:extra[i]` / `overrides`)。
   ★canonical結線頁は promote が最後に editions を丸ごと置換するので**種4に書いても出ない**
   = canonical本体に書く。 edition-overrides に editions を持つ頁も同じ。
2. `scripts/_volgap-local-fill-v2.py` — 楽天ローカル種(delta 828MB + old 373MB = 818,420item)を1パス。
   題variant(ルビ括弧を落とす)で引く。 旧 `_volgap-rakuten-local-fill.py` は先頭欠けを扱えず
   751巻を取りこぼしていた。
3. `scripts/_volgap-ndl-harvest2.py` → `_volgap-ndl-match.py` — 楽天で埋まらない頁をNDL SRUで収穫
   (354頁・11分・5,546レコード)。 ISBN10→13変換 / 「第N巻」「題. N」の巻抽出 / 和暦・[年]の日付解釈。
4. `scripts/_volgap-adjudicate.py` — 追加ゲートを当てて APPLY/HOLD/DROP を決める(共通)。
5. `scripts/_volgap-exists-split.py` → `_volgap-undermerge-fill.py` — EXISTS層の仕分けと第3段。
6. `scripts/_volgap-apply-fill.py` — 種4 / canonical へ純粋追加(可逆backup + changelog)。

## ★ゲート(効いた順)
- **G5 ISBN連番 = 決定打**。 `前巻ISBN < 候補 < 次巻ISBN`(先頭欠けは `< 次巻`)。
  版元prefixだけでは落とせない **同じ社の別レーベル**(プレミア=文庫版ISBNが通常版の穴に来た)と
  **別年代版**(復讐の兇獣=1982年版 / ハード&ルーズ=原版のISBN)を機械で落とす。
  逆に、日付ゲートが外れても連番が通れば採る(熱笑!!花沢高校 トクマ版= 820115→820122→820139→820207)。
- G1 既存ISBN(本番索引+種2) / G2 版元prefix / G3 発売日 / G4 著者
- G6 版元名一致(頁の版元が判る時だけ。 片側「不明」は判定不能=保留)
- G7 同じISBNが複数の版に提案 → 証拠の多い方だけ採る
- G8/G8b/G8c 同じ頁の別版との二重化防止 → [[volgap_edition_split_double_add]]


## ★2026-09-10: 「1冊だけ欠け」層は NDL では枯れた

残343頁のうち**欠番1個=179頁**を NDL で全数照合した実測:
```
ACCEPT 0 / REVIEW 0 / REJECT_EDITION 1 / EXISTS 6 / NOHIT 162(138頁)
```
**新規に採れる巻はゼロ**。1980年代以前・小出版社が多く、NDLに一次資料が無い層。
★**「NDLで調べれば埋まる」と再提案しない**。次に動かすなら Wikipedia / 出版社公式 / JPRO、
あるいは「ISBN以前は数えない」等の裁定見直し([[volgap_skip_isbnless_edition]] の拡張)。

★**EXISTS は「直せる印」ではない**。6件を個別に割ったら本物は2件だけで、
4件は**別版/別作品のISBN**だった(唇役主丞乾いて候=deluxe版5巻 / 椰=講談社KCデラックス3巻 /
聖=2016新装版3巻 / 人狼ゲーム=別作品クレイジーフォックス2巻)。ゲートが正しく弾いていた。
私は一度「6件直せます」と誤報した = [[feedback_raw_count_is_not_worklist]] の再演。

## 数字の読み方(2026-09-07 実測)
- ターゲット 1,718巻/468頁。 内訳= **NOHIT 1,272巻/307頁**(楽天ローカルにもNDLにも無い)/
  **EXISTS 251巻/107頁**(自前DBに在る=under-merge)/ ACCEPT 94 / REJECT_EDITION 53 / REVIEW 48。
- ★**楽天ローカル種は全網羅ではない**: NOHIT 354頁のうち 210頁は「その題の本が1冊も無い」。
  著者ハーベスト由来(2026-06-27)なので旧作・ニッチ作が丸ごと落ちている。
- ★**巻抜けの主因は取込もれでない**([[volgap_mostly_undermerge]] の再確認)。 埋まったのは1割弱。

## 残り(次の手)
- NOHIT 1,272巻/307頁 = 楽天live / Wikipedia / JPRO が次の情報源
- EXISTS の A2(自頁に別番号で在る)103巻/43頁・B1(別頁同題=頁分裂)48巻/15頁 は
  **番号付け直し / 頁統合**の領域で、巻を足す仕事ではない
- 表 = `docs/production-diagnostics/volgap-apply*.tsv` / `volgap-exists-split.tsv`

[[volgap_diagnosis_order]] [[volgap_virtual_tool_trigger]] [[harvest_match_mechanism_applied]]
[[ndl_volume_completion_better_than_rakuten]] [[feedback_efficiency_first]]

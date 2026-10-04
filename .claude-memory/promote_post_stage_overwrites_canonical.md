---
name: promote_post_stage_overwrites_canonical
description: 【型・是正済】editions-supplement の replace:true が promote後段(edisup)で canonical を丸ごと上書き。targeted反映では再現せず月次だけ巻が消える
metadata: 
  node_type: memory
  type: project
  originSessionId: 3819afb2-c9d0-4149-93f3-a0615b0c157d
  modified: 2026-09-21T02:22:53.969Z
---

2026-09-21 月次1.2.20 の ISBN消失監視で発覚（w3=手塚治虫『ワンダースリー』で9冊消失）。

## 何が起きるか

`_promote-bulk-v2.py` は **promote 内で** `edition-canonical/<SRC slug>.yml` を適用して版タブを組む。
その**後段**に `intake.py` の durability stage があり、`edisup` = `_apply-editions-supplement.py` が
`data/seeds/editions-supplement.yml` の `replace: true` エントリで **editions を丸ごと差し替える**。

→ canonical（新しい・ISBN完備）で組んだ9版が、supplement（古い手書き・ISBN null混じり）の3版に**上書き**され、
巻が黙って消える。**巻抜けにも見えない**（版ごと消えるため）。

## ★なぜ長く気づかれなかったか

- **targeted反映（`_reflect-targeted.py` → `promote --only`）は後段を走らせない** = per-case 修正直後は正しく見える。
- 壊れるのは **intake（月次のフルpromote）を通った時だけ**。つまり「直した直後は正しく、翌月の蒸留で戻る」。

## 掃引と対処

- 両方を持つ頁は **`urusei-yatsura` と `w3` の2つだけ**（2026-09-21 実測）。うる星は supplement が正本なので温存。
- w3 は supplement 側を退役（canonical が正本）。`_apply-editions-supplement.py` 再実行後も9版が残ることを確認済み。
- 新しく canonical を起こす時は **同名 slug が editions-supplement に居ないか**を必ず見る（works は7件しかないので grep 一発）。

**Why:** 同じ頁を2つの seed が別レイヤで支配していると、**どちらが後に走るか**だけで結果が変わる。
**How to apply:** 版の正本は1つに決める。canonical を使うなら supplement の同 slug を消す。
関連: [[edition_canonical_mechanism]] [[edition_typemerge_hides_volumes]] [[seed_silently_ineffective_class]]

## ★逆向きの穴(2026-10-04 週次preflightで実踏): targeted反映で seed版が剥がれる
- `promote --only`(targeted反映・書影是正の再promote等)は後段 edisup を**通らない** → editions-supplement の版が
  丸ごと消えたまま本番へ出る。9/22 の書影是正(9b41d98ee)ほかで 5頁17冊(ばるぼら/菜(sai)/ネオ・ファウスト/ふしぎなメルモ/
  ルードウィヒ・B)が2週間不可視。ISBN消失監視(週次preflight)が「理由なし」で検出。
- 対処= 5頁に絞って seed 版を再適用+`_regroup-versions.py`+promote の `_cover_for` で書影充填(backup .cache/edisup-restore-bak-20261004-101143)。
  ★`_apply-editions-supplement.py` を素で全件流すと **うる星やつらの書影が消える**(mk_edition は cover_url=None で置く)= 絞るか coverfill を後に。
- ★**恒久策=実装済(2026-10-04 ユーザ指示)**: `_promote-bulk-v2.py` の main 末尾で **--only 時だけ** ONLY_SLUGS∩版seed に
  `_apply-editions-supplement.apply_work`(版置換+regroup+`_cover_for`で書影充填)を自動適用(ログ「版補完seed 再適用(--only)」)。
  フルpromoteは従来どおり intake の edisup+coverfill。共通実体は apply_work 1本(二重実装なし)。
- ★同時に `load_works()` が **edition-canonical を持つ作品を版seedから除く**(canonical後勝ち)= うる星が該当。
  これで月次の edisup がうる星の canonical(7/4・刷タブ「初版カバー/新装版カバー」)を seed の古い版で上書きし
  書影44頁を空にした 9/22 型も封じた。検算= dry-run で7作(5作+うる星+HxH)が本番と editions 完全一致。

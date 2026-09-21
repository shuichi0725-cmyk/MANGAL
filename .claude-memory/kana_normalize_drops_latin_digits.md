---
name: kana_normalize_drops_latin_digits
description: 【型・per-case遮断済】_normalize_kana がラテン文字と数字を落とすため「サムライ Japan」と「サムライ 7」が一致し別作品が誤統合される
metadata: 
  node_type: memory
  type: project
  originSessionId: 3819afb2-c9d0-4149-93f3-a0615b0c157d
  modified: 2026-09-21T02:23:10.827Z
---

2026-09-21 さむらいJapan で実踏（ユーザGOで是正）。

## 機構

`_promote-bulk-v2.py` の `find_related_series_ids` は「title_kana が一致する series は表記揺れ」として
cluster 統合する。その比較に使う `_normalize_kana` が **ラテン文字・数字・空白を落とす**ため:

```
「サムライ Japan」(さむらいJapan/永井豪)  → 'サムライ'
「サムライ 7」   (SAMURAI 7/浅野まいこ) → 'サムライ'   ← 一致してしまう
```

片方が ASCII 題（ローマ字表記の揺れ対策）だと安全弁も効かず、**別作品が1頁に合流**する。
実害: `samurai-japan` の頁が中身ごと「Samurai 7（周防瑞孝・講談社KCDX）」に置き換わり、
本来の『さむらいJapan』(永井豪/メディアファクトリー1999・9784889918236) が本番から消えていた。

## 対処（共有ロジックは触っていない）

- per-case = `data/seeds/merge-exceptions.yml` に sid 対を追加して遮断（対称・series id）。
  今回は [47141,60739] [47141,60953] [60953,132414] [60953,60739] の4対。
- 過mergeを解く時は**頁化とセット**（[[new_page_creation_srcpage_key2slug]]）。周防版は
  `samurai-7-suou2006` で独立頁に（NDLで全2巻=上/下を確認してから）。
- ★**共有の `_normalize_kana` を直すと全DBの統合関係が動く**ので、やるなら影響件数の実測とGOが要る（未実施）。

## 疑うべき署名

「題が **カナ+ラテン** / **カナ+数字** で、カナ部分だけ同じ」作品どうし。
例: サムライJapan ⇔ サムライ7 / ラブX ⇔ ラブ2。同型を見たら merge-exceptions を先に疑う。

**Why:** 表記揺れ吸収のための正規化が、識別に必要な情報まで削っていた。
関連: [[shu2_qid_is_author]] [[merge_needs_external_proof]] [[fragmentation_overmerge_cleanup]]

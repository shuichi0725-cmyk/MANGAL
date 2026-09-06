---
name: imprint_label_leak
description: 【型・是正済】imprint欄に版ラベル(通常版/愛蔵版)が焼かれる。seedのlabel代用3経路+種2の17行。182頁是正・番人つき
metadata: 
  node_type: memory
  type: project
  originSessionId: 19c40654-3fa1-4eb7-af6e-40057dab95ee
  modified: 2026-09-06T13:28:41.112Z
---

2026-09-06 是正。 **imprint = レーベル名(奥付の叢書名)の欄なのに、版タブ名(通常版/愛蔵版/完全版)が
入っている頁が 182 頁**あった。

## 実害2つ
1. **表示**: `VolumeCoverflow.tsx` は `[publisher, imprint].filter(Boolean).join(" / ")` なので
   頁の出版社行が **「小学館 / 通常版」** と出る。 `/shinkan` の行(`ShinkanRow.tsx`)にも出る。
2. **検出器の汚染**: imprint を鍵にする監査(canonical-imprint-split / edition-run-split /
   [[unlisted_volumes_trinity_type]] の裁定表の目安)が、**プレースホルダを実在レーベルとして比較**する。
   しかも「通常版」同士が一致して**別出版社を同レーベル扱いする**逆向きの誤りも出る。

## 源は2つ
- ★**seed の label 代用 3経路**(172頁 = 通常版147/愛蔵版11/完全版3/別版ほか):
  `edition-canonical` の `canonical_imprint or canonical_label` / `extra-editions` と
  `compact_edition` の `imprint or label`。 2026-08-08 の JIN で **extra_editions だけ**
  「imprint を seed に明示できる」ようにしたが、**代用そのものは残っていた**。
  → `_promote-bulk-v2.py` に `_imprint_from_label()` を新設し、**完全一致の版ラベルだけ弾く**
  (`_LABEL_NOT_IMPRINT` = 通常版/ワイド版/文庫版/完全版/新装版/愛蔵版/デラックス版/別版/コンパクト版/復刻版)。
  ★「KCデラックス」等のレーベル名らしい label の代用は従来どおり効かせる = 保守的。
  ★canonical は種2の実imprintへ落ちるので、**空になるどころか実レーベルが埋まった**
  (ビッグコミックス / ヤンマガKCスペシャル / てんとう虫コミックススペシャル …)。
- ★**種2(MADB)のレーベル欄が「愛蔵版」そのもの**(editions 17行 → 10頁):
  → 最終passで **imprint が自分のタブ名と同じ(または前方一致)なら落とす**。 種2は書き換えない。

## 気付き方 / 再検査
```
grep -h "^\s*imprint:" data/manga.v2/*.yml | 版ラベル完全一致を数える   # 0 であること
```
新しい seed 経路(版を足す機構)を作る時は **imprint を label で代用しない**。
代用するなら必ず `_imprint_from_label()` を通す。

## 副次
再生成で **保留されていた slug-override が4頁に適用**された(drsuranpu→dr-slump /
kuroiwashi→kuroi-washi / mangakenkanryuu→manga-kenkanryu / shiitondoubutsuki→seton-doubutsuki)。
4頁とも `data/slug-aliases.yml` と `public/_redirects` に 301 が既在で切れたURLは無し。
★**長く再promoteしていない頁は、触った瞬間に溜まっていた override がまとめて効く**ので、
targeted反映の「slug変更検知」行は必ず読み、alias/_redirects の有無を確認する。

**Why:** label(タブ名)と imprint(レーベル名)は別物。 代用は「取り敢えず埋まる」ので気付きにくく、
表示と検出器の両方を静かに汚す。
**How to apply:** 版を作る seed 経路を足したら `_imprint_from_label()` を通す。
関連: [[edition_canonical_mechanism]] [[imprint_split_arms_type]]
[[edition_run_split_arms_wide_type]] [[feedback_one_bug_means_a_class]]

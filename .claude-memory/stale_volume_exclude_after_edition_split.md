---
name: stale_volume_exclude_after_edition_split
description: 【型・是正済】版を分ける前に打った「混入除去(volume-exclude)」が、版分離後は正しい巻を消している。エコエコアザラクで3冊
metadata: 
  node_type: memory
  type: project
  originSessionId: 3819afb2-c9d0-4149-93f3-a0615b0c157d
  modified: 2026-09-21T15:51:13.554Z
---

2026-09-21 「穴1冊だけ」層の per-case 調査で発見。

## 症状

頁の版タブに巻が足りないのに、**種2にも canonical seed にもその巻が在る**。
埋めようとすると充填器が「既に canonical に在る(冪等skip)」と言って何も起きない
= 消しているのは `data/seeds/volume-exclude.yml`。

## 実例(エコエコアザラク)

`volume-exclude` に3件:「激マン型混入(帯断絶×日付逆行)。真巻…に差替 **2026-07-04**」
→ 除外されていたのは **9784049200072 / 0102 / 0119**。
楽天ISBN直引きで3冊とも「**エコエコアザラク（6）（9）（10）**」古賀新一 / **角川書店** /
series=**ザ・ホラーコミックス** = 実在する別版の巻だった。

当時は4つの版(少年チャンピオン/秋田コミックス・セレクト/ホラーコミックススペシャル/ザ・ホラーコミックス)が
**1つのタブに混在**していたため、角川ISBNが秋田書店の並びに紛れた異物に見えた。
その後 canonical で版を分けたので、**同じ判断が今は誤り**になっていた。

→ 除外を解除して再生成 = ザ・ホラーコミックス版が **1〜10巻連続**に。

## 一般則

★**版構成を変えた頁は、過去の volume-exclude / 混入判定を見直す**。
「混入」判定は**その時の版構成に依存**する。版を分けた後は前提が変わる。
逆に、canonical/override で版を整えたのに巻が出ない頁を見たら、**先に volume-exclude を疑う**
(seed に在るのに出ない = 誰かが消している)。

★ついでの作法: `volume-exclude` を減らすと `_check-seeds.py` の純粋追加台帳ゲートが
**反映を止める**(719→716 で実際に止まった)。正当な退役なら
`python scripts/_check-seeds.py --allow-shrink volume-exclude.yml` で承認してから commit → 反映。

関連: [[band_intruder_fix]] [[edition_canonical_mechanism]] [[never_delete_because_broken]] [[volgap_diagnosis_order]]

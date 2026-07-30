---
name: catch_side_wrong_work_class
description: catchにも別作品混入の型が実在(初回36件是正)。検出器=_catch-audit.py・裁けない時はdropで消す方針
metadata: 
  node_type: memory
  type: project
  originSessionId: 317b315e-f85b-4abc-8dad-aced941f2d0f
  modified: 2026-07-30T09:01:32.441Z
---

あらすじ検品(synopsis-ja 全数292件裁定 2026-07-30)の副産物として、**catch 側にも「別作品の内容」型がある**ことが確定し、同設計の検出器 `scripts/_catch-audit.py` を新設して初回掃引まで完了した(93件裁定 / **fixed 36・dropped 1・ok 52・hold 2**、残flag 0)。

- ★**最初のスワップ(ばけもの夜話づくし⇔凪のお暇)は catch 層にも残っていた**: 凪のお暇のキャッチが「悩みを抱える者に扉を開く宿・雷雲亭」= 相手作品の内容。**synopsisを直してもcatchは直らない**(層が別)。
- 他の実例: HOME(内田春菊)にスペインと侍の歴史ロマンス / Dawn に疫病パンデミック / だから僕はHができない に愛犬が人間化 / 火の鳥2772 に手塚『火の鳥』本編 / BLAZBLUE に別スピンオフ / 本編の粗筋がスピンオフ頁に入る型(賭ケグルイ(仮)・ウソ婚Rosé・伝勇伝4コマ・アリスと蔵六学園・シマウマ外伝)。
- **画集頁に原作の粗筋**が入る型もある(セラフィック・フェザー/雪広うたこアートワークス)。[[work_qid_enrichment]]とは別問題。

**Why:** catch は頁上部に出るので誤りの視認性が最も高い。かつ catch と synopsis は別seed(`catch-ja.json` / `synopsis-ja.json`)なので、片方を直しても他方は残る。

**How to apply:** 検出は必ず**証拠2系統の合議**で締める(caption単独のスコアだけだと偽陽性2,718件 → 「captionとsynopsisの両方と交差しない」に絞って89件)。素材ゼロ/矛盾で正しい本文が書けない時は保留にせず `--drop` でキーを削除する(ユーザ裁定「作れないものは間違ったものが上がっているより消してok」)。やり方は skill synopsis-audit に封入済。関連: [[synopsis_ja_seed]] [[feedback_one_bug_means_a_class]] [[feedback_accuracy_is_the_goal]]

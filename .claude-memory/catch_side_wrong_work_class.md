---
name: catch_side_wrong_work_class
description: 頁のcatch(キャッチ)にも別作品の内容が入る型が実在。あらすじ検品(292件)の副産物で4件確認、catch専用の監査は未整備
metadata: 
  node_type: memory
  type: project
  originSessionId: 317b315e-f85b-4abc-8dad-aced941f2d0f
  modified: 2026-07-30T08:37:26.089Z
---

あらすじ検品(synopsis-ja 全数裁定 2026-07-30・292件)の副産物として、**catch 側にも「別作品の内容」型がある**ことが確定した。synopsis を検品していると「seed は正しく catch が誤り」というケースが逆向きに出てくる。

確認済み4件(いずれも synopsis は正しく catch が別作品):
- 罪と罰(手塚治虫・tsumitobatsu) — catch=「食糧難を救う新種が変異…救世団」= 別作品のSF
- 純情クレイジーフルーツ(松苗あけみ1983・junjou-crazy-fruits) — catch=「その後を描く」続編扱いだが頁実体は原作
- +チック姉さん(plus-chikku-nee-san) — catch=「書道部」だが実体は模型部
- THE IDOLM@STER(まな・一迅社2013・the-idolm-ster) — catch=「中性的な少年が男性アイドル」= 別作品

**Why:** synopsis-ja には検品柱([[synopsis_ja_seed]] / skill synopsis-audit)があるが、**catch には同等の監査が無い**。catch は頁上部に出るため誤りの視認性は synopsis より高い。

**How to apply:** catch の掃引を作るときは synopsis-audit と同じ設計(内容語 × 独立証拠[title+巻caption]の交差スコア → 低スコアだけAI裁定)が流用できる。個別の証拠は `docs/production-diagnostics/synopsis-audit-verdicts.jsonl` の note に残してあるので、そこから起点4件を拾える。関連: [[feedback_one_bug_means_a_class]]

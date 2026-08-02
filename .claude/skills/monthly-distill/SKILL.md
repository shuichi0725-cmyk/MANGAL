---
name: monthly-distill
description: 月次蒸留して=MADB取込→フルpromote→enrich→AI fill。Phase0前提確認→差分報告→Goサイン必須の大工程(~3時間+)
---

# 月次蒸留して

トリガー語: **「月次蒸留して」**(完全一致)。CLAUDE.md「月次蒸留 protocol」が正本——**必ず併読**。ここは運用の実体メモ。

## 大原則
種1/種2/種3は壊さない。純粋追加only。上書き/削除検出=即abort+報告。**Phase1の差分報告→ユーザGoサイン受領までPhase2に進まない**。

## 実パイプライン ([[monthly_distill_real_pipeline]])
1. Phase0 前提確認 = ★`python scripts/_monthly-phase0.py`(2026-07-10 script化。前提10項+git cleanを機械確認・欠け=exit 1=「対象Xが無いので蒸留できない」とユーザ報告して終了。目視チェックリストで代替しない)
2. MADB差分取得: サイト月次CSV(cm101+cm504のみ更新。cm103/104/105は2024-11凍結=再DL無駄) + GitHub全件JSONのdateModified比較で訂正回収
3. `clean-madb-seed` → `_build-series-v2` → `_populate-v2`(temp) → **`_distill-incremental-merge`**(series_key突合の安全純粋追加・INSERT only)
4. `python scripts/intake.py --run`(roles→merge→seed4→matcher v9→v13→v14→adult_us→trailing→foreigndrop→promote。matcher~20分・promote~110分。**Windows: promote完了後プロセス居座り=ログ最終行/ファイル数で判定しkill**)
5. enrich: AniList再フェッチ(毎回。凍結gapは毎月増える)・synopsis和訳delta(分散WF→ _apply-synopsis.py 純粋追加→commit)・作品QID(QLever)
6. AI fill batch(種3 diff→100件/batch・JST報告・commit毎)
6b. **取りこぼし頁化**(新規seriesの頁作成)= 必ず `_torikoboshi-genpages.py` 経由(★2026-07-27 3ゲート内蔵: ISBN既在skip/**vol1不在→保留**/**近似題(既存頁と包含一致)→保留**)。★**ゲート保留は自動頁化しない**——種2横断(`_ledger`/`_exists --isbn`)で彼岸島型(残巻が別clusterでdedup負け)/分裂(誤題typo・表記揺れ)/コンビニ断片を裁定し、ユーザ報告してから。手書きで源頁を作ってゲートを迂回するのは禁止
7. **月次サニティ監査**: _coverage-audit(前月差分flag)・_audit-volume-numbering(AUTO_FIXED急増=新型signal)・_furigana-audit・_audit-title-eq-author・_audit-foreign-editions・publisher新キーflag・**特装検出(新刊特装→special-edition seed追記=ベルセルク43型)**・★**_audit-solo-truncated(頁化を行った月は必須。新規頁に「途中巻だけの孤立頁」が1件でもあれば6bの裁定に戻る=2026-07-27に17頁流出した型)**
8. **stale生成物の再生成**: _build-calendar / _gen-corner-stocks / _gen-corner-auto / 本番索引
9. 最終summary(全件数+削除0確認+次月予測)

## 罠
- 再登録の別MADB-ID二重化(虚構推理vol23型)→ISBN dedup+監査
- 種4は触らない(手動add only)。retire hygiene だけ(MADB追いつき分の除去)
- ★canonical結線頁(edition-canonical/*.yml)は **overridesも種4も後負けで無効**=巻修正はcanonical本体へ(QP外伝4巻 2026-07-27実踏)
- ★コンビニ廉価再録レーベルは頁化しない(秋田トップコミックス=DROP_IMPRINT封鎖済。「◯◯スペシャル」型はtitle単位。パーフェクト・メモワール=未裁定候補)
- ★頁のdropは必ず `_reflect-targeted.py --drop` 経由(手でyml消すと索引・ストックに残骸=検索404。2026-07-27にホームズ4頁分の索引除去コミット漏れを回収した型)
- 本番R2への反映は別途「週次蒸留して」

## ★成功判定 (= 完了主張の前にこの数字を全部言えること)
- Phase0 exit 0 / **Goサイン受領の発話引用**(無しにPhase2へ進んだら違反)
- 種1/2/3 とも **削除0・上書き0**(各取込ログの `applied=N, missing=0, overwrites=0`)
- 種2 series数 = **増加のみ**(減少=即abort案件) / promote後 manga.v2 ≈ **66k+ files**(激減=事故)
- 頁化した月は **新規頁の途中巻断片(solo-truncated)=0** と **ゲート保留の裁定結果**(件数+型)を報告
- tsc/vitest **green維持**(赤転落=abort) / サニティ監査の flag件数(0でなくてよい=報告する)
- どれかが言えない=完了していない

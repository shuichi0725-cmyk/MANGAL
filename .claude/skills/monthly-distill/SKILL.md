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
2. MADB差分取得: ★release repo = **`mediaarts-db/dataset`**(CLAUDE.md旧記載のMADB-Lab-Bot-publicは404=2026-08-21実踏)。
   metadata101_json.zip + metadata504_json.zip をDL(cm103/104/105は2024-11凍結=再DL無駄)。
   差分計測は新旧metadata101のID/ISBN集合diff(旧rawは`-<旧tag>`名で温存)
3. `clean-madb-seed` → `_build-series-v2` → `_populate-v2`(temp) → **`_distill-incremental-merge`**(series_key突合の安全純粋追加・INSERT only)
4. `python scripts/intake.py --run`(★**seedlint**→roles→merge→seed4→matcher v9→v13→v14→adult_us→trailing→foreigndrop→promote→…→**isbnloss**。2026-08-26で入口=seed lint/出口=ISBN消失監視が自動abortゲート化。clean鮮度ガードもpromote前に内蔵。matcher~20分・promote~110分。**Windows: promote完了後プロセス居座り=ログ最終行/ファイル数で判定しkill**)
5. enrich: ★AniList再フェッチ=**フルダンプ**(2026-08-21確立: backup→progress消去→`_anilist-dump-v3.py`(~2.5h)→
   `_build-anilist-enrich-map.py`→`_gen-anilist-status-map.py`)。deltaは5,000capで月次には不足。
   synopsis和訳delta(新規増分のみ。9千件級バックログはエンリッチ柱=蒸留で飲み込まない)・作品QID(QLever)
6. 種3 AI fill = ★**v2機構では原則不要**(2026-08-21確認: kana=頁化時NDL確定/genre・synopsis=enrich系。
   新seriesは種3未登録のままpromote無依存)。旧v1手順(batch fill)は種3スキーマ変更時のみ復活
6b. **取りこぼし頁化**(新規seriesの頁作成)= 必ず `_torikoboshi-genpages.py` 経由(★2026-07-27 3ゲート内蔵: ISBN既在skip/**vol1不在→保留**/**近似題(既存頁と包含一致)→保留**)。★**ゲート保留は自動頁化しない**——種2横断(`_ledger`/`_exists --isbn`)で彼岸島型(残巻が別clusterでdedup負け)/分裂(誤題typo・表記揺れ)/コンビニ断片を裁定し、ユーザ報告してから。手書きで源頁を作ってゲートを迂回するのは禁止
6c. ★**頁化の後始末3点**(2026-08-22 ユーザ発見2件から確立):
   - **書影live補充**: 新規頁のISBNはcovers seed未収録が普通(1.2.19実測47/93頁欠け)→楽天live by ISBN(`rakuten_live_retry`・noimage除外)→cover-override.jsonl追記→再promote
   - **slugレビュー→公開前rename**: 生成器はヘボンfallback=外来語英綴り化(strawberry-cake型)と促音バグ(otsu-san型)が出る。previewレビューで裁定し**未公開のうちにrename**(alias不要)
   - **コンビニ/再録の目視**(コミック乱セレクション型): レーベル名題・故人作家の新刊=再録の決定的証拠→non-manga-drop
7. **月次サニティ監査**: _coverage-audit(前月差分flag)・_audit-volume-numbering(AUTO_FIXED急増=新型signal)・_furigana-audit・_audit-title-eq-author・_audit-foreign-editions・publisher新キーflag・**特装検出(新刊特装→special-edition seed追記=ベルセルク43型)**・★**_audit-solo-truncated(頁化を行った月は必須。新規頁に「途中巻だけの孤立頁」が1件でもあれば6bの裁定に戻る=2026-07-27に17頁流出した型)**・★**_audit-price-pack(猫と竜型=metadata101のalternativeHeadline/ISBN(set)走査。本番掲載の新規増加を裁定)**・★**_audit-vol0-hidden-first(泣かせたくて型=0巻の1巻が続巻到着で不可視化。HIDDEN_FIXの新規増加→--applyで楽天題ゲート適用)**
8. **stale生成物の再生成**: _build-calendar / _gen-corner-stocks / _gen-corner-auto / 本番索引
9. 最終summary(全件数+削除0確認+次月予測)

## 罠
- ★**cleanの正規パス=`.cache/madb/metadata101-clean.json`**(2026-08-22実踏): promoteの出版社導出(ISBN→schema:publisher)がこのパスを読む。新cleanを別ディレクトリに置いてintakeを回すと**新刊全部が出版社(unknown)**になる(1.2.19で1,182頁再生成の実害)。temp buildにはenv override、正規パスは**intake前に必ず差し替える**
- 再登録の別MADB-ID二重化(虚構推理vol23型)→ISBN dedup+監査
- 種4は触らない(手動add only)。retire hygiene だけ(MADB追いつき分の除去)
- ★★**種4-auto(volumes-supplement-auto.yml)は蓄積台帳=全消し禁止**(2026-08-21実害: 1.2.19で916巻全消し→種2未収録883巻が本番から消失。根本原因=`_register-seed4-ndl.py --apply` が既存を読まず全上書き)。★2026-08-26 **機械封鎖済**: ①同scriptはmerge書き込み化(非ndl-auto entryを必ず保存・parse不能なら書かずabort・.cacheへbackup) ②intake.py末尾に isbnloss stage(理由なし消失>0=abort) ③週次preflightベースラインに seed4_auto_volumes(減少=FAIL) ④clean鮮度ガード(Phase0+intake=metadata101-cleanがrawより古いとabort)。retireは「ISBNが種2に実在する巻だけ」個別除去
- ★canonical結線頁(edition-canonical/*.yml)は **overridesも種4も後負けで無効**=巻修正はcanonical本体へ(QP外伝4巻 2026-07-27実踏)
- ★コンビニ廉価再録レーベルは頁化しない(秋田トップコミックス=DROP_IMPRINT封鎖済。「◯◯スペシャル」型はtitle単位。パーフェクト・メモワール=未裁定候補)
- ★頁のdropは必ず `_reflect-targeted.py --drop` 経由(手でyml消すと索引・ストックに残骸=検索404。2026-07-27にホームズ4頁分の索引除去コミット漏れを回収した型)
- 本番R2への反映は別途「週次蒸留して」

## 罠(追補 2026-08-21/23)
- ★**seed機械追記後は必ず `yaml.safe_load` 検証**(種4はlist itemが**カラム0**=2スペで書くとparse死。1.2.19でXinobi種4が silent不着→索引まで壊れた実踏)
- merge-manifest/バックアップ名は★2026-08-26に実行時導出へ是正済(release+日付名・既存は.prevN退避=前回のrevert用manifestを上書きしない)
- 数値ペンネーム(「296」型)がint化してre.sub系がクラッシュ→promote/監査はstr()防御済。新規scriptでも `str(name)` を徹底

## ★成功判定 (= ★2026-08-26 script化: `python scripts/_monthly-postflight.py` exit 0 が条件)
- ★**postflight = `python scripts/_monthly-postflight.py`**(Phase0と対の完了側。seed lint/manga.v2≥66k/
  ISBN消失=理由なし0/種4-auto不減/publisher unknown不増/**頁化した月は新規頁のsolo-truncated=0** を機械判定。
  **exit 0 + 出力数値の引用**が完了主張の条件=自己申告の散文判定は廃止)
- postflight対象外で引き続き言うこと:
  - **Goサイン受領の発話引用**(無しにPhase2へ進んだら違反)
  - 種1/2/3 とも **削除0・上書き0**(各取込ログの `applied=N, missing=0, overwrites=0`) / 種2 series数=増加のみ
  - ★**表示カタログslug集合diff**(git HEAD索引 vs 新索引): 消失は**全件説明可能**であること
  - 頁化した月は **ゲート保留の裁定結果**(件数+型) / tsc/vitest green / サニティ監査flag件数の報告
- どれかが言えない=完了していない

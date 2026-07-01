---
name: intake-pipeline
description: 取込オーケストレーション scripts/intake.py。派生層再構築を順序立てて1コマンド化(roles→merge→seed4→detect→promote)
metadata: 
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

**`scripts/intake.py`** = 取込オーケストレーション (commit 8d02901)。 種2 rebuild後/ソース更新後の **派生層再構築 + 検出 + 本番再生成** を順序立てて1コマンド化。

**★拡張(2026-05-31, commit 603340e)**: matcher v14 + adult_us を統合。 **default=フルパイプライン**(`--run` で全ステージ)。 新依存順: `roles→merge→seed4→detect → match(v9)→match13→merge14(v14)→adultus→trailing → promote`。 ★promote が adult_us map(.cache/adult-us-map.json)を読むので **promote を最後に移動**。 `--group madb`(種2派生のみ・既存adult_us流用)/`--group anilist`(照合のみ)で部分実行可。 ※matcher ~20分。 ★en-fill/anilist_id(種3書込)は intake 対象外=deliberate。 CLAUDE.md 月次蒸留 Phase2 にも `intake.py --run` 明記。 関連 [[adult_judgment_architecture]]。

**依存順序(旧)**: `roles → merge → seed4 → detect → promote`
- ★merge(_gen-author-set-merges)の partial-overlap統合が `series_authors.role`(primary=artist/writer_artist)を使うので **role が先**。
- 各stage = 既存script を subprocess 実行: `_apply-roles-rawfiltered --apply` / `_gen-author-set-merges` / `_register-seed4-ndl --apply` / `_audit-volume-gaps --by-title` / `_promote-bulk-v2`。

**種a group** (`--group anilist`): `match`(_audit-match-v9) → `trailing`(_audit-trailing-gaps)。

**安全策**: default=**dry**(計画表示のみ)、 `--run` で実行、 db変更stage前に自動backup(db-v2.sqlite.bak-intake-*)、 stage失敗で即abort、 `--stages a,b` / `--group` で部分実行。

**使い方**:
```
python scripts/intake.py              # 計画表示(dry)
python scripts/intake.py --run        # MADB派生 pipeline
python scripts/intake.py --run --group anilist
python scripts/intake.py --run --stages roles,merge,promote
```

**本scriptの対象外(別フェーズ・手動/Go/AI要)**:
- 種1/504 delta取込 + 種2 rebuild (= 月次蒸留 Phase0-2、 CLAUDE.md protocol + Go)
- 種3 AI fill (フリガナ/ジャンル/synopsis = Claude必要)
- NDL裏取りバッチ (`_seed4-candidates --ndl` = 1時間級throttle)

**検証済**: end-to-end --run で全stage EXIT=0、 roles冪等(updated=0)、 本番42ページ変化0。 ★STEP6([[series_fragmentation_rootcause]])で merge が series_key 参照になったので、 再build後も既存mergeが壊れず本pipelineで安全に再構築できる。 ※intake後は git diff で本番yml確認 → commit。 関連 [[author_roles_state]] [[anilist_matching_state]]。

---
name: intake_manifest_ledger_live
description: 統合台帳 data/seeds/intake-manifest/ の実体(operations.jsonl + holes snapshot)。全cleanup操作の一次記憶、必ず使う
metadata: 
  node_type: memory
  type: project
  originSessionId: eead35c9-02b6-4f7c-9201-3923c98dedb6
---

統合台帳の **実体** = `data/seeds/intake-manifest/` (= [[intake_manifest_gate_design]] の Phase0 を実装したもの)。

**なぜ作った**: 簿記監査 `_intake-manifest-audit.py` は走っていたが出力が `.cache/manifest-audit/holes.jsonl`(gitignore)に落ちて消え、「あるはずなのに無い」事故が起きた。さらに cleanup 操作が18個の `*-changelog.jsonl` に散在し統合台帳が無かった。ユーザ指示で①統合②今後必ず使う を恒久化(2026-06-20)。

**構成**:
- `operations.jsonl` = 20台帳/3,725操作を集約した統合ログ `{op_source,slug,related,at,raw}`。再生成不可=git必須。生成器 `scripts/_manifest-consolidate-ops.py`。
- `holes-snapshot.jsonl.gz` + `holes-summary.json` = 全ページの穴(T0スキーマ床/T1品質blocker/T2warn)。再生成可(`_intake-manifest-audit.py`)だが.cache消失防止でgzip永続化。
- `README.md` = 運用protocol。

**忘れない仕組み**: CLAUDE.md 冒頭に「統合台帳=必ず使う」protocol を転記済(毎セッション読まれる)。新cleanup前に台帳参照→操作後にchangelog記録→consolidate→audit、の4手。

**運用**: 全操作は可逆(`.cache/*-bak-*`)・種2不変。人手可読ビュー=`docs/isbn-unmerge-ledger.md`。一次ソースは台帳。関連 [[merge_needs_external_proof]] [[feedback_complete_data_before_ship]] [[data_assets_inventory]]。

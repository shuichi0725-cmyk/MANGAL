---
name: weekly-isbn-loss-acknowledge-flow
description: preflightのISBN消失FAILは機械帰属→acknowledged台帳で消し込む(2026-08-31確立・283件実証)
metadata: 
  node_type: memory
  type: project
  originSessionId: bd02af38-42f4-4acb-9f59-ae607bc37eeb
  modified: 2026-08-31T14:07:00.632Z
---

preflight の ISBN消失監視(`_audit-isbn-loss.py`)が「★理由なし」を出したときの標準対応(2026-08-31 実証: 283件を約15分で全数消し込み・事故ゼロ確認):

1. **機械帰属が先**(1件ずつ調べない): スナップショット日以降の `git log -p -- data/seeds/` から **削除された(-行)ISBNのnet集合**を抽出し、loss listと突合。今回275/283が一致。
2. 残りは `git log -S <isbn>` で個別にコミット特定(頁dropや合流解体はseedに-行が出ない)。
3. 全件がユーザ裁定済みコミットに紐付いたら **`data/seeds/isbn-loss-acknowledged.jsonl`** に
   `{isbn13, slug_at_loss, reason, commit, at}` で記帳(**根拠コミット必須**)。監査がこの台帳を読む(2026-08-31結線)。
   純簿記=promote挙動に不影響。紐付かないISBNだけが真の事故候補=復活検討。
4. スナップショットは data/seeds/isbn-snapshot.json.gz(git追跡)。finalize が週次末に自動更新。

**Why**: 「1件ずつ調べて」を素直にやると283件×調査で数時間停止する。消失の大半は per-case 裁定作業の正当削除で、証拠は全部 git にある。[[feedback_agent_fanout_token_cost]] と同じ「機械証拠を一括算出」の応用。
関連: [[intake_manifest_ledger_live]] [[never_delete_because_broken]]

---
name: pending_r2_prune_ledger
description: 頁dropやslug renameで残るR2フォルダを台帳に積み、週次蒸留のpreflightで必ず表示する
metadata:
  type: project
---

**台帳 = `data/seeds/pending-r2-prune.jsonl`**(git追跡)。1行=`{slug, reason, at, source}`、slugは**公開slug**。

- **積む側**: per-case で頁を `--drop` した時、および `slug-overrides.yml` で slug を rename した時
  (旧slugのフォルダが残る)。skill `reflect-targeted` に明記済み。
- **見る側**: `scripts/_weekly-preflight.py` の検査8 が件数+一覧を **WARN** で必ず表示する
  (preflight は週次蒸留の必須ゲートなので見落としが構造的に起きない)。skill `weekly-distill` にも記載。
- **消し込み**: `_r2-sync.py --prune` 実行後、`.cache/r2-pruned-<日時>.txt` に載ったか1件ずつ照合して該当行を削除。
  載っていなければまだ公開されている(prune の安全弁 `--prune-max 3000` / `--prune-floor 0.9` で中止された可能性)。

★2026-08-08 ユーザ指示「週次蒸留するときにわかるようにして」で新設。初期投入=ワイルド7整理の7件。
`--prune` 自体は2026-07-26から必須だが、**どの頁が消えるべきかが分からない**のが残っていた穴だった。

関連: [[r2_orphan_pages_prune_missing]] [[drop_page_redirect_chain]] [[wild7_franchise_state]]

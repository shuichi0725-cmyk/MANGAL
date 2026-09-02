---
name: promote_hangs_on_exit_windows
description: 【事実・2026-09-02 解消】promoteの完了後居座り(Windows)は os._exit(0) で断った。intake経由でも自力終了。居座りが見えたら旧版か別プロセス=まず待つ・intake経由では絶対killしない
metadata:
  node_type: memory
  type: project
  originSessionId: b2aea090-84ca-49f7-ac76-8bc5d5c410db
---

★対処のやり方 = **`.claude/skills/long-job-ops/SKILL.md`**(完了判定は成果物とログ末尾・プロセスを待たずkill)。

## ★2026-09-02 解消
- `_promote-bulk-v2.py` 末尾(`if __name__ == "__main__"`)に `sys.stdout/stderr.flush()` → `os._exit(0)` を追加(commit e98a9b58b)。出力は全部 with で閉じ済み・スレッド/atexit 無しなので安全。`--only kimetsu-no-yaiba` で 45秒 exit 0・出力不変(popularity 差のみ=enrich map 更新由来)を確認。フルスケール(66k)は次回月次で実測。
- 原因の推定 = 1.9GB 級 heap の解放(インタプリタ teardown)。intake.py は promote を subprocess.run で待つので、旧版では終了待ち=見かけ上のハングになり、**kill すると intake が abort して durability stage(edisup/special/coverfill/isbnloss)が走らない**事故経路だった。

## 事実の記録(旧)
- `_promote-bulk-v2.py` は全yml+art-books書き終え後もプロセスが終了しない(1.9GB級で居座る)。処理は完了済み。
- 完了サイン: ログ最終「→ ...art-books.v2」/ 出力ファイル数。next build も同様に node が居座ることがある(✓ Exporting (2/2) が完了サイン)。

---
name: file_size_misread_ls_column
description: 【罠】このPCは所有者名に空白があるため ls -l の列がずれる。ファイルサイズは stat -c %s / os.path.getsize で見る
metadata:
  type: project
---

2026-09-15 週次で実踏。`ls -l out/contact.html | awk '{print $5}'` を「サイズ」として読み、
**192.5KB(上限45KBの4倍)= 共通シェルに重い物が載った回帰**と誤報告した。実測は **29.1KB**
(前週80.6KB から改善)で、回帰など無かった。

**Why:** Git Bash の `ls -l` は 所有者 `chiba shuichi`(**空白入り**)を2列に割るため、
サイズは `$5` ではなく `$6` に来る。このPCのユーザ名が空白を含む限り**常に**ずれる。

**How to apply:**
- サイズは `stat -c "%s"` か Python の `os.path.getsize` で取る。`ls -l`+awk の列指定は使わない。
- 番人(`_check-shell-wiring.py` の「最小頁の床」)は自前で正しく測っているので、**数字は番人から引く**。
- 一般則: **異常を報告する前に、測り方そのものを別手段で検算する**。[[feedback_sanity_check_tool_warnings]]

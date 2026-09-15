#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""同一slugを名乗る manga.v2 ファイルが複数ある層の検出器 (2026-09-15 新設)。

★なぜ要るか (= 2026-09-15 実害『白と黒』下崎):
  `data/manga.v2` は **ファイル名(SRC stem) ≠ 頁の `slug:` 欄(公開slug)** が正常形
  (slug-override頁)。このため「別名のファイル2つが同じ公開slugを名乗る」状態が作れてしまい、
  全索引ビルドで **同一作品が2行** 出る(実測: 索引 69,353 のうち1組が重複)。
  生まれる経路 = 頁の公開slugを変えた(年サフィックス外し等)時に **旧名のファイルが残る**。
  `data/manga.v2` は gitignore = 履歴が無いので、消えても増えても気づけない。

★既存の検出器#19(_audit-year-suffix-dup.py)では**構造的に見えない**:
  あちらは入力が `by_slug = {str(r[SI]): r for r in idx["d"]}` で、
  **同一slugの行が黙って後勝ちで畳まれる**(#19が見るのは `X-YYYY` と `X` という別slug名同士の対)。
  → だから索引ではなく **ファイル実体** を走査する。

どちらが生きているかの判定(= 消す前に必ずやる):
  `python scripts/_promote-bulk-v2.py --only <stem>` の **total:**
    total: 1 = 源あり(残す) / total: 0 = 源なし(残骸)  ※[[orphan_source_pages_restored]]
  中身の厚み(genres/catch の有無)でも裏が取れる。消す前に `.cache/` へ退避する。

使い方:
  python scripts/_audit-duplicate-slug-files.py            # 重複があれば一覧 + exit 1
  python scripts/_audit-duplicate-slug-files.py --tsv      # TSVも書く
"""
from __future__ import annotations

import argparse
import collections
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga.v2")
OUT_TSV = os.path.join(ROOT, "docs", "production-diagnostics", "duplicate-slug-files.tsv")

RE_SLUG = re.compile(r"^slug:\s*(.+?)\s*$", re.M)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tsv", action="store_true", help="TSVも書き出す")
    a = ap.parse_args()

    if not os.path.isdir(SRC):
        print("★data/manga.v2 が無い(まだ promote していない)")
        return 0

    by_slug = collections.defaultdict(list)
    n = 0
    for f in os.listdir(SRC):
        if not f.endswith(".yml"):
            continue
        n += 1
        # ★slug欄だけ要るので YAML パースしない(69k頁を10秒で走査するため)。
        #   先頭2KBに必ず在る(promote は slug を先頭付近に書く)。
        with open(os.path.join(SRC, f), encoding="utf-8", errors="replace") as fh:
            head = fh.read(2048)
        m = RE_SLUG.search(head)
        if m:
            by_slug[m.group(1).strip().strip("'\"")].append(f[:-4])

    dup = {k: sorted(v) for k, v in by_slug.items() if len(v) > 1}
    print(f"走査 {n:,} 頁 / slug欄を読めた {sum(len(v) for v in by_slug.values()):,}")
    print(f"★同一slugを名乗るファイルが複数: {len(dup)} 組")
    for k, v in sorted(dup.items()):
        print(f"   {k}  <-  {v}")
    if dup:
        print("\n  判定 = `python scripts/_promote-bulk-v2.py --only <stem>` の total:")
        print("         1=源あり(残す) / 0=源なし(残骸)。消す前に .cache/ へ退避。")
    if a.tsv:
        os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
        with open(OUT_TSV, "w", encoding="utf-8", newline="\n") as fo:
            fo.write("slug\tfiles\n")
            for k, v in sorted(dup.items()):
                fo.write(f"{k}\t{','.join(v)}\n")
        print(f"  → {os.path.relpath(OUT_TSV, ROOT)}")
    return 1 if dup else 0


if __name__ == "__main__":
    sys.exit(main())

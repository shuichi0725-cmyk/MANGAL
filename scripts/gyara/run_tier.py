# -*- coding: utf-8 -*-
"""ギャラ型 一括是正の1帯分を回す: 生成 → 反映 → 検証 → 駄目なら差し戻して記録。

  python .cache/gyara/run_tier.py <worksheet.tsv> <tier名>

安全弁(この順に効く):
  1. autofix.build が「判断が要る」と返した頁は作らない
  2. 生成後に頁のISBN集合を比較し、1件でも減っていたら seed を捨てて差し戻す
  3. 残った頁だけ採用。落とした頁は gyara-anomalies.tsv に理由つきで積む
"""
import io
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import autofix  # noqa: E402
import canon  # noqa: E402

PAT = re.compile(r"isbn13:\s*'?(\d{13})")
ANOM = os.path.join(canon.ROOT, "docs", "production-diagnostics", "gyara-anomalies.tsv")


def isbns_of(stem):
    p = os.path.join(canon.ROOT, "data", "manga.v2", stem + ".yml")
    try:
        return set(PAT.findall(io.open(p, encoding="utf-8").read()))
    except IOError:
        return set()


def reflect(stems):
    if not stems:
        return
    for i in range(0, len(stems), 120):
        chunk = stems[i:i + 120]
        subprocess.run([sys.executable, "scripts/_reflect-targeted.py",
                        "--only", ",".join(chunk)],
                       cwd=canon.ROOT, capture_output=True)


def main():
    ws, tier = sys.argv[1], sys.argv[2]
    rows = [l.rstrip("\n").split("\t") for l in io.open(
        os.path.join(canon.ROOT, ws), encoding="utf-8")][1:]
    done = {os.path.basename(p)[:-4]
            for p in __import__("glob").glob(
                os.path.join(canon.CANON_DIR, "*.yml"))}
    built, anom, before = [], [], {}
    for r in rows:
        pub = r[0]
        f, stem = autofix.src_path(pub)
        if not stem:
            anom.append((tier, pub, "", r[1], "本番ymlが見つからない(公開slugから引けない)", "", ""))
            continue
        if stem in done:
            continue
        ok, msg = autofix.build(pub, dry=True)
        if not ok:
            anom.append((tier, pub, stem, r[1], msg, "", ""))
            continue
        before[stem] = isbns_of(stem)
        autofix.build(pub)
        built.append(stem)
    print("生成 %d / 見送り %d" % (len(built), len(anom)))
    reflect(built)
    lost = {}
    for stem in built:
        miss = before[stem] - isbns_of(stem)
        if miss:
            lost[stem] = sorted(miss)
    print("ISBNが減った頁 %d → 差し戻す" % len(lost))
    for stem in lost:
        p = os.path.join(canon.CANON_DIR, stem + ".yml")
        if os.path.exists(p):
            os.remove(p)
        anom.append((tier, stem, stem, "",
                     "自動生成すると本番から巻(ISBN)が消える=種2から辿れない版が頁に載っている",
                     str(len(lost[stem])), " ".join(lost[stem][:8])))
    reflect(list(lost))
    for stem in lost:
        if before[stem] - isbns_of(stem):
            print("  !! 差し戻しても欠けたまま:", stem)
    keep = [s for s in built if s not in lost]
    with io.open(ANOM, "a", encoding="utf-8", newline="\n") as f:
        for a in anom:
            f.write("\t".join(a) + "\n")
    print("採用 %d / 記録 %d" % (len(keep), len(anom)))
    io.open(os.path.join(os.path.dirname(__file__), "_keep_%s.json" % tier),
            "w", encoding="utf-8").write(json.dumps(keep))


if __name__ == "__main__":
    main()

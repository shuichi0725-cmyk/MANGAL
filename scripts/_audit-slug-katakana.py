# -*- coding: utf-8 -*-
"""カタカナ語ヘボンfallbackの一括監査(2026-07-14 ユーザ要望=自動で決められない箇所の可視化)。
対象dirの頁ymlの題を slug生成lib に通し、katakana-english.yml に掛からずカナ転写された
断片(=英語綴りか判断保留の語)を 断片→[slug] で集計出力。
usage: python scripts/_audit-slug-katakana.py [.preview-data/manga] [--tsv out.tsv]
"""
import glob
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml

from _slug_kana_lib import FALLBACK, make_slug

target = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else ".preview-data/manga"
tsv = sys.argv[sys.argv.index("--tsv") + 1] if "--tsv" in sys.argv else None

frag2slugs = {}
for p in sorted(glob.glob(os.path.join(target, "*.yml"))):
    try:
        m = yaml.safe_load(open(p, encoding="utf-8"))
    except Exception:
        continue
    if not isinstance(m, dict) or not m.get("title"):
        continue
    make_slug(str(m["title"]))
    for fr in FALLBACK:
        frag2slugs.setdefault(fr, []).append(m.get("slug") or os.path.basename(p)[:-4])

rows = sorted(frag2slugs.items(), key=lambda kv: (-len(kv[1]), kv[0]))
print(f"辞書に掛からなかったカタカナ断片: {len(rows)}種 / {sum(len(v) for v in frag2slugs.values())}箇所 ({target})")
for fr, slugs in rows:
    ex = " ".join(slugs[:3]) + (f" 他{len(slugs)-3}" if len(slugs) > 3 else "")
    print(f"  {fr}\t{len(slugs)}件\t{ex}")
if tsv:
    with open(tsv, "w", encoding="utf-8") as f:
        for fr, slugs in rows:
            f.write(f"{fr}\t{len(slugs)}\t{','.join(slugs)}\n")
    print(f"→ {tsv}")

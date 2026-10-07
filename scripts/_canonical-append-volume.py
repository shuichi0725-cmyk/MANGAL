#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""edition-canonical 本体の通常版(top-level volumes)の末尾に新刊を1冊ずつ足す(2026-10-08 新設)。

背景: canonical 頁は promote の最後に editions を組み直すので、種4・edition-overrides に足しても頁に出ない
(CLAUDE.md 厳守6)。日次蒸留の続巻適用(_preorder-apply-zokkan.py)は canonical 頁の新刊を
「canonical固定頁…→canonical本体へ手で追記」として保留簿に出す。ここはその1行を本体へ入れる道具
(ゴルゴ13 222 = 2026-10-05 手作業 / 223・チキン49・新しいゲーム始めました5 = 2026-10-08 で道具化)。

ゲート(どれか外れたら何も書かずに理由を出す):
  - 番号 = 本体の最大巻+1..+3(遠い飛び番・既在番号は止める)
  - ISBN がどの canonical seed にも無い(版・刷・compact を含む)
  - 発売日 >= 本体の最終日(旧runの接ぎ木を止める)
書き方: 本体の volumes 末尾の行の直後に3行を差し込む(全体を書き直すと anchor/alias・引用符・コメントが崩れる)。
  読み直して「元 + その1冊」と一致することを検算してから書く。退避= .cache/canonical-append-bak-<日付>/ 、
  記帳= data/seeds/edition-fix-changelog.jsonl(op=canonical_append_volume)。

使い方:
  python scripts/_canonical-append-volume.py <stem> <number> <isbn13> <release_date> --why "根拠" [--dry]
  → 反映は _reflect-targeted.py --only <stem>(日次蒸留中は --commit-only)
"""
import sys as _sys_h
if any(_a in ("-h", "--help") for _a in _sys_h.argv[1:]):
    print(__doc__ or "(no doc)"); _sys_h.exit(0)
import copy
import datetime
import glob
import json
import os
import re
import shutil
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON_DIR = os.path.join(ROOT, "data", "seeds", "edition-canonical")
LOG = os.path.join(ROOT, "data", "seeds", "edition-fix-changelog.jsonl")
TODAY = datetime.date.today().isoformat()


def claimed_isbns():
    out = {}
    for p in glob.glob(os.path.join(CANON_DIR, "*.yml")):
        txt = open(p, encoding="utf-8").read()
        for i in re.findall(r"97[89]\d{10}", txt):
            out.setdefault(i, os.path.basename(p))
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 4 or "--why" not in sys.argv:
        sys.exit(__doc__)
    stem, num, isbn, rd = args[0], int(args[1]), args[2], args[3]
    why = sys.argv[sys.argv.index("--why") + 1]
    dry = "--dry" in sys.argv
    if not re.fullmatch(r"97[89]\d{10}", isbn):
        sys.exit(f"[stop] ISBN13 でない: {isbn}")
    if not re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", rd):
        sys.exit(f"[stop] 発売日の形が違う: {rd}")
    p = os.path.join(CANON_DIR, f"{stem}.yml")
    if not os.path.exists(p):
        sys.exit(f"[stop] canonical seed が無い: {p}")
    txt = open(p, encoding="utf-8").read()
    d0 = yaml.safe_load(txt) or {}
    if d0.get("slug") != stem:
        sys.exit(f"[stop] seed の slug({d0.get('slug')}) がファイル名と違う")
    vols = d0.get("volumes") or []
    nums = [v.get("number") for v in vols if isinstance(v.get("number"), int)]
    mx = max(nums or [0])
    if num in nums:
        sys.exit(f"[stop] 巻{num} は本体に既在")
    if not (mx >= 1 and mx + 1 <= num <= mx + 3):
        sys.exit(f"[stop] 巻が連続しない(本体max{mx}→{num})")
    cl = claimed_isbns()
    if isbn in cl:
        sys.exit(f"[stop] ISBN {isbn} は canonical {cl[isbn]} に既在")
    dates = [str(v.get("release_date")) for v in vols if v.get("release_date")]
    if dates and rd < max(dates)[:len(rd)]:
        sys.exit(f"[stop] 発売日{rd} が本体の最終日{max(dates)}より前")

    # 本体 volumes ブロックの末尾(次の top-level キー or EOF)の直前に差し込む
    lines = txt.split("\n")
    vi = next((i for i, ln in enumerate(lines) if re.match(r"^volumes:(\s|$)", ln)), None)
    if vi is None:
        sys.exit("[stop] top-level の volumes: 行が無い")
    j = vi + 1
    while j < len(lines) and (lines[j].startswith("- ") or lines[j].startswith("  ") or lines[j] == ""):
        j += 1
    while j - 1 > vi and lines[j - 1] == "":
        j -= 1   # 末尾の空行の前に入れる
    snippet = [f"- number: {num}", f"  isbn13: '{isbn}'", f"  release_date: '{rd}'"]
    new_txt = "\n".join(lines[:j] + snippet + lines[j:])
    want = copy.deepcopy(d0)
    want["volumes"].append({"number": num, "isbn13": isbn, "release_date": rd})
    if yaml.safe_load(new_txt) != want:
        sys.exit("[stop] 差し込み検算NG(読み直した内容が「元+1冊」と一致しない)。何も書いていない")
    print(f"{stem}: 本体 max{mx} → 巻{num} {isbn} {rd} を末尾へ" + ("(dry)" if dry else ""))
    if dry:
        return
    bak_dir = os.path.join(ROOT, ".cache", f"canonical-append-bak-{TODAY}")
    os.makedirs(bak_dir, exist_ok=True)
    bak = os.path.join(bak_dir, f"{stem}.yml")
    if not os.path.exists(bak):
        shutil.copy2(p, bak)
    open(p, "w", encoding="utf-8").write(new_txt)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"op": "canonical_append_volume", "slug": stem, "at": TODAY, "number": num, "isbn13": isbn,
                            "release_date": rd, "before": f"本体max{mx}", "after": f"巻{num}を末尾に追加",
                            "evidence": why, "backup": os.path.relpath(bak, ROOT), "reversible": True},
                           ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()

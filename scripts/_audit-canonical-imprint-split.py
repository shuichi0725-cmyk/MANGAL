# -*- coding: utf-8 -*-
"""版canonical/本番頁で「同一レーベルが表記ゆれで別版に割れている」型の検出 (= ARMS型。2026-08-28 新設)。

背景: ARMS で 21巻だけが別版タブに分裂していた。原因はMADBのレーベル誤記
  「少年サンデーコミ**ツ**クススペシャル」(正: コミ**ッ**クス)で、種2が別 edition 行として持ち、
  2026-08-17 の「ギャラ型是正」一括処理がその区切りをそのまま edition-canonical へ焼き込んだため。
  ★巻抜け仮想にも「21巻欠け」として現れる = 巻抜けの一因になる。

判定: 1頁の中で、imprint を正規化(小書きカナ→大書き / 中黒・空白除去 / 全角空白除去)すると
  一致する版が2つ以上ある頁を flag。★自動統合はしない(新装版/復刻版が正当に別版な場合があるため)。

出力: docs/production-diagnostics/canonical-imprint-split.tsv
  slug / title / canonical有無 / 正規化キー / 各版(type・imprint・巻数・巻番号) / 巻番号の重複有無

  python scripts/_audit-canonical-imprint-split.py
"""
import glob, io, os, sys
from collections import Counter, defaultdict
import yaml
try: from yaml import CSafeLoader as L
except Exception: from yaml import SafeLoader as L

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SMALL = str.maketrans("ァィゥェォッャュョヮヵヶ", "アイウエオツヤユヨワカケ")


def norm(s: str) -> str:
    return (s or "").translate(SMALL).replace(" ", "").replace("　", "").replace("・", "")


def main() -> None:
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml"))):
        try:
            d = yaml.load(io.open(p, encoding="utf-8"), Loader=L) or {}
        except Exception:
            continue
        eds = d.get("editions") or []
        if len(eds) < 2:
            continue
        by = defaultdict(list)
        for e in eds:
            if e.get("imprint"):
                by[norm(e["imprint"])].append(e)
        stem = os.path.basename(p)[:-4]
        for key, group in by.items():
            if len(group) < 2:
                continue
            # ★2026-08-29: 完全同名も対象に含める(旧版は「別sid分離だから」とskipしていたが、
            #   読者には同じ名前のタブが2つ並ぶ=不具合。orenosora で実踏)。型で区別して出す。
            kind = "表記ゆれ" if len({(e.get("imprint") or "") for e in group}) >= 2 else "同名"
            nums = [[v.get("number") for v in (e.get("volumes") or [])] for e in group]
            flat = [n for g in nums for n in g]
            overlap = len(flat) != len(set(flat))
            desc = " || ".join(
                "%s/%s/%d巻%s" % (e.get("type"), e.get("imprint"), len(e.get("volumes") or []), g)
                for e, g in zip(group, nums))
            out.append((stem, d.get("title") or "", kind,
                        "有" if os.path.exists(os.path.join(ROOT, "data", "seeds", "edition-canonical", stem + ".yml")) else "無",
                        key, "重複" if overlap else "相補", desc))
    dst = os.path.join(ROOT, "docs", "production-diagnostics", "canonical-imprint-split.tsv")
    with io.open(dst, "w", encoding="utf-8") as f:
        f.write("slug\ttitle\tcanonical\tnorm_key\t巻番号\t版\n")
        for r in out:
            f.write("\t".join(map(str, r)) + "\n")
    print("表記ゆれで版が割れた頁: %d 件 → %s" % (len(out), dst))
    print("  型:", dict(Counter(r[2] for r in out)))
    print("  巻番号:", dict(Counter(r[5] for r in out)))
    print("  canonical:", dict(Counter(r[3] for r in out)))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""デラックス・レーベル割れ監査 (= 2026-07-19 バーテンダー型4連発から型化)

「◯◯デラックス」がレーベル名(KCデラックス/ジャンプ・コミックスデラックス/ビーボーイ…)なのに
版種 deluxe として standard と分裂している頁を検出し3分類する:
  SPLIT   = 巻番号が相補(dx∪st=連番・交差小)         → バーテンダー型=統合候補
  DUP     = ISBN重複あり                              → 汚染(統合+dedup要)
  PARALLEL= dx/st 双方がほぼフル並走(別ISBN)          → 真の別版の可能性(旧版×新装等)=個別判断・自動統合禁止
出力: docs/production-diagnostics/deluxe-label-split.tsv
既知の正当deluxe(愛蔵版的な真のデラックス)は PARALLEL に落ちる設計。
"""
import glob
import io
import os
import sys
import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "deluxe-label-split.tsv")


def main():
    rows = []
    counts = {"SPLIT": 0, "DUP": 0, "PARALLEL": 0}
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml"))):
        try:
            raw = io.open(p, encoding="utf-8").read()
            if "deluxe" not in raw:
                continue
            d = yaml.safe_load(raw)
        except Exception:
            continue
        eds = d.get("editions") or []
        dxs = [e for e in eds if e.get("type") == "deluxe"]
        sts = [e for e in eds if e.get("type") == "standard"]
        if not dxs or not sts:
            continue
        for e in dxs:
            imp = e.get("imprint") or ""
            if "デラックス" not in imp and "DX" not in imp:
                continue  # レーベル名にデラックスを含まない真のdeluxeは対象外
            dn = {v["number"] for v in e.get("volumes") or []}
            di = {v.get("isbn13") for v in e.get("volumes") or []} - {None}
            for s in sts:
                sn = {v["number"] for v in s.get("volumes") or []}
                si = {v.get("isbn13") for v in s.get("volumes") or []} - {None}
                if not dn or not sn:
                    continue
                union = dn | sn
                inter = dn & sn
                clean = union == set(range(1, max(union) + 1))
                if di & si:
                    cls = "DUP"
                elif len(inter) <= max(1, len(union) // 5) and clean:
                    cls = "SPLIT"
                elif len(inter) >= min(len(dn), len(sn)) * 0.7:
                    cls = "PARALLEL"
                else:
                    cls = "SPLIT" if clean else "PARALLEL"
                counts[cls] += 1
                rows.append((cls, d.get("slug"), imp[:24],
                             f"{min(dn)}-{max(dn)}({len(dn)})", f"{min(sn)}-{max(sn)}({len(sn)})",
                             len(inter), len(di & si)))
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("class\tslug\tdeluxe_imprint\tdx_vols\tst_vols\tnum_overlap\tisbn_overlap\n")
        for r in sorted(rows):
            f.write("\t".join(str(x) for x in r) + "\n")
    print(f"分類: SPLIT(統合候補)={counts['SPLIT']} / DUP(汚染)={counts['DUP']} / PARALLEL(別版の可能性・自動統合禁止)={counts['PARALLEL']}")
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()

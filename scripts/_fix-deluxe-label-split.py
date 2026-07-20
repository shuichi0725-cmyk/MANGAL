#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""デラックス・レーベル割れの一括統合 (= 2026-07-19 ユーザGO「慎重に」。バーテンダー型の機械是正)

★厳格ゲート(全部満たした頁だけ統合。1つでも外れたらHOLD=手動裁定へ):
  G1 deluxe.imprint に「デラックス」or「DX」(=レーベル名)
  G2 dx巻番号 ∩ st巻番号 = 空集合(完全相補)。同番号が両方に居る頁は触らない
  G3 dx∪st = 連番 1..N (穴なし)
  G4 dx/st とも versions[] を持たない(持つ頁=多版正規化済み等=触らない)
  G5 slug が edition-overrides.json / edition-canonical 結線に未登場
  G6 dx/st の publisher 名が一致 or 片方欠落
★不変条件(適用後に全頁検証・破れたら即rollback対象):
  V1 頁の全ISBN集合が前後で完全一致(損失ゼロ)
  V2 統合standardは連番1..N・ISBN重複なし
  V3 dx/st 以外の版(bunkobon等)は無変更
出力: --dry = 計画+HOLD一覧(docs/production-diagnostics/deluxe-merge-plan.tsv)
      --apply = edition-overrides.json へ一括追記 + changelog + バックアップ
"""
import copy
import glob
import io
import json
import os
import sys
import time
import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OV_P = os.path.join(ROOT, "data", "seeds", "edition-overrides.json")
PLAN = os.path.join(ROOT, "docs", "production-diagnostics", "deluxe-merge-plan.tsv")
CANONICAL_SLUGS = {"golgo-13", "tsuribaka-nisshi"}  # edition-canonical結線=override無効(CLAUDE.md)


def volkey(v):
    return (v.get("number"), v.get("isbn13"))


def main():
    apply = "--apply" in sys.argv
    ov = json.load(io.open(OV_P, encoding="utf-8"))
    plans, holds = [], []
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml"))):
        try:
            raw = io.open(p, encoding="utf-8").read()
            if "deluxe" not in raw:
                continue
            d = yaml.safe_load(raw)
        except Exception:
            continue
        slug = d.get("slug") or os.path.basename(p)[:-4]
        stem = os.path.basename(p)[:-4]
        eds = d.get("editions") or []
        dxs = [e for e in eds if e.get("type") == "deluxe"]
        sts = [e for e in eds if e.get("type") == "standard"]
        if len(dxs) != 1 or len(sts) != 1:
            if dxs and sts:
                holds.append((slug, "HOLD_multi_edition", f"dx{len(dxs)}/st{len(sts)}"))
            continue
        dx, st = dxs[0], sts[0]
        imp = dx.get("imprint") or ""
        if "デラックス" not in imp and "DX" not in imp:
            continue  # 真のdeluxe(レーベル名でない)は対象外
        if dx.get("versions") or st.get("versions"):
            holds.append((slug, "HOLD_has_versions", ""))
            continue
        if slug in ov or stem in ov:
            holds.append((slug, "HOLD_override_exists", ""))
            continue
        if slug in CANONICAL_SLUGS:
            holds.append((slug, "HOLD_canonical", ""))
            continue
        dv = dx.get("volumes") or []
        sv = st.get("volumes") or []
        dn = {v["number"] for v in dv}
        sn = {v["number"] for v in sv}
        if not dn or not sn:
            continue
        if dn & sn:
            holds.append((slug, "HOLD_number_overlap", str(sorted(dn & sn)[:6])))
            continue
        union = dn | sn
        if union != set(range(1, max(union) + 1)):
            holds.append((slug, "HOLD_not_contiguous", str(sorted(union)[:8])))
            continue
        pd, ps = dx.get("publisher"), st.get("publisher")
        if pd and ps and pd != ps:
            holds.append((slug, "HOLD_publisher_diff", f"{pd}≠{ps}"))
            continue
        # 統合案: 巻フルコピー(volume_label/variants等も保持)、主レーベル=巻数の多い側
        merged = sorted((copy.deepcopy(v) for v in dv + sv), key=lambda v: v["number"])
        dominant = dx if len(dv) >= len(sv) else st
        new_std = {"type": "standard", "label": "通常版",
                   "publisher": ps or pd}
        if dominant.get("imprint"):
            new_std["imprint"] = dominant["imprint"]
        new_std["volumes"] = merged
        others = [copy.deepcopy(e) for e in eds if e is not dx and e is not st]
        plans.append({"slug": slug, "stem": stem, "n_dx": len(dv), "n_st": len(sv),
                      "total": len(merged), "imprint": new_std.get("imprint", ""),
                      "editions": [new_std] + others,
                      "isbns_before": sorted({v.get("isbn13") for e in eds for v in e.get("volumes") or []} - {None})})
    with io.open(PLAN, "w", encoding="utf-8") as f:
        f.write("action\tslug\tdetail\n")
        for pl in plans:
            f.write(f"MERGE\t{pl['slug']}\tdx{pl['n_dx']}+st{pl['n_st']}→1..{pl['total']} imprint={pl['imprint'][:20]}\n")
        for h in holds:
            f.write(f"{h[1]}\t{h[0]}\t{h[2]}\n")
    from collections import Counter
    hc = Counter(h[1] for h in holds)
    print(f"統合可(全ゲート通過): {len(plans)} / HOLD: {len(holds)} {dict(hc)}")
    print(f"計画 → {PLAN}")
    if not apply:
        print("(dry-run。適用は --apply)")
        return
    # ==== 適用 ====
    bak = os.path.join(ROOT, ".cache", f"deluxe-merge-bak-{time.strftime('%Y%m%d-%H%M%S')}")
    os.makedirs(bak, exist_ok=True)
    for pl in plans:
        src = os.path.join(ROOT, "data", "manga.v2", pl["stem"] + ".yml")
        io.open(os.path.join(bak, pl["stem"] + ".yml"), "w", encoding="utf-8").write(io.open(src, encoding="utf-8").read())
        ov[pl["stem"] if pl["stem"] != pl["slug"] else pl["slug"]] = {
            "editions": pl["editions"],
            "note": f"2026-07-19 デラックス・レーベル割れ一括統合(バーテンダー型・厳格ゲート): dx{pl['n_dx']}+st{pl['n_st']}→通常版1..{pl['total']}"}
    json.dump(ov, io.open(OV_P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with io.open(os.path.join(ROOT, "data", "seeds", "edition-fix-changelog.jsonl"), "a", encoding="utf-8") as f:
        for pl in plans:
            f.write(json.dumps({"slug": pl["slug"], "op": "edition_override",
                                "before": f"deluxe{pl['n_dx']}+standard{pl['n_st']}(レーベル割れ)",
                                "after": f"standard1..{pl['total']}統合",
                                "reason": "デラックス・レーベル割れ一括統合(厳格ゲート・ユーザGO慎重に)",
                                "backup": bak, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}, ensure_ascii=False) + "\n")
    io.open(os.path.join(bak, "_isbn-invariant.json"), "w", encoding="utf-8").write(
        json.dumps({pl["stem"]: pl["isbns_before"] for pl in plans}, ensure_ascii=False))
    print(f"適用: override {len(plans)}件追記 / backup={bak}")
    print("次: promote --only → _verify(V1-V3) → reflect")


if __name__ == "__main__":
    main()

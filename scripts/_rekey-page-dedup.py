"""page-dedup.yml の slug を新世界へ再キー(slug規則改訂・Stage F merge 後の整合)。

dedup entry = {drop: 旧slug, canonical: 旧slug}(6/10 ISBN混線/中身同一の裁定)。
旧slug → (旧合成ソース slug→key) → 現 key2slug → 新slug。
  - 新drop == 新canonical → merge 等で同一ページ化済み = entry 廃止
  - どちらか解決不能 → 廃止(report)
  - それ以外 → 新slugで保持
★裁定(どのペアが中身同一か)は不変。 キーの付け替えのみ。
"""
import csv
import sys
from pathlib import Path

import yaml

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**7)
ROOT = Path(__file__).resolve().parent.parent


def main():
    s2k = {}
    with (ROOT / ".cache/old-source-slug2key.tsv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            s2k[r["slug"]] = r["key"]
    k2s = {}
    with (ROOT / ".cache/apply/key2slug.tsv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            k2s[r["key"]] = r["slug"]
    # rep集約: 任意keyから新slugへ(integratedのkey→repのslug)
    key2new = {}
    with (ROOT / "data/seeds/slug-final-integrated.tsv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            s = r["proposed_slug"]
            if s and not s.startswith("("):
                key2new[r["key"]] = s

    p = ROOT / "data/seeds/page-dedup.yml"
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    rows = d.get("dedup") or []
    out = []
    st = {"kept": 0, "rekeyed": 0, "obsolete_same_page": 0, "unresolved": 0}
    for e in rows:
        ok = s2k.get(e["drop"])
        oc = s2k.get(e["canonical"])
        nd = key2new.get(ok) if ok else None
        nc = key2new.get(oc) if oc else None
        if not nd or not nc:
            st["unresolved"] += 1
            continue
        if nd == nc:
            st["obsolete_same_page"] += 1
            continue
        if nd != e["drop"] or nc != e["canonical"]:
            st["rekeyed"] += 1
        else:
            st["kept"] += 1
        out.append({**e, "drop": nd, "canonical": nc})
    d["dedup"] = out
    with p.open("w", encoding="utf-8") as f:
        f.write("# 中身同一の二重出力ページの統合裁定(2026-06-10)。 ★slugは _rekey-page-dedup.py が新世界へ追従\n")
        yaml.dump(d, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    print(f"page-dedup: {len(rows)} → {len(out)}  {st}")


if __name__ == "__main__":
    main()

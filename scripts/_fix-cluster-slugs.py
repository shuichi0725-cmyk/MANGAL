"""[修正・ログ付] 主版slug消失(無印が無く従版slugに本編)を是正。コナン以外の59作。
慎重: 「slug-final提案の主版(proposed==base)」の題と完全一致する本番ファイルが"1つだけ"あり、
無印slugが空の時だけ Type A=自動rename。複数一致/不一致(本編不在)は flag(手動)。
非破壊可逆: alias / slug-overrides / _change-log に来歴。 --apply で適用(既定dry-run)。
"""
import os, glob, json, re, unicodedata, yaml, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
APPLY = "--apply" in sys.argv
NOW = "2026-06-16"
PROD = "data/manga.v2"
LAYERS = ["data/manga", "data/manga.v2", ".preview-data/manga"]
LOG = "data/seeds/_change-log.jsonl"
OVR = "data/seeds/slug-overrides.yml"
ALI = "data/slug-aliases.yml"


def norm(t):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", (t or ""))).lower()


rows = [l.rstrip("\n").split("\t") for l in open("data/seeds/slug-final-integrated.tsv", encoding="utf-8")][1:]
from collections import defaultdict
by_base = defaultdict(list)
for r in rows:
    if len(r) > 6:
        by_base[r[4]].append(r)
prodset = set(os.path.basename(p)[:-4] for p in glob.glob(f"{PROD}/*.yml"))

typeA, flags = [], []
for base, grp in by_base.items():
    if base == "meitantei-conan":
        continue  # 適用済
    if len(grp) < 2:
        continue
    primary = [r for r in grp if r[6] == base]  # proposed==base(主版=無印提案)
    suffixed_present = [r for r in grp if r[6] != base and r[6] in prodset]
    if not primary or base in prodset or not suffixed_present:
        continue
    p = primary[0]
    ptitle, pvols = p[1], p[2]
    # base-接頭の本番ファイルで題が完全一致するもの
    cands = []
    for fp in glob.glob(f"{PROD}/{base}-*.yml"):
        slug = os.path.basename(fp)[:-4]
        try:
            d = yaml.safe_load(open(fp, encoding="utf-8")) or {}
        except Exception:
            continue
        nv = sum(len(e.get("volumes", [])) for e in d.get("editions", []))
        cands.append((slug, d.get("title"), nv, [a.get("name") for a in d.get("authors", [])]))
    match = [c for c in cands if norm(c[1]) == norm(ptitle)]
    if len(match) == 1:
        typeA.append((base, match[0], ptitle, pvols))
    elif len(match) == 0:
        flags.append((base, "本編不在(Type B)", ptitle, pvols, [c[0] for c in cands]))
    else:
        flags.append((base, "題一致が複数(曖昧)", ptitle, pvols, [c[0] for c in match]))

print(f"=== Type A(自動rename候補): {len(typeA)} ===")
for base, m, pt, pv in typeA:
    print(f"  {m[0]:<46} (題={m[1][:18]} 巻{m[2]} 著{m[3]}) → 無印 {base}")
print(f"\n=== flag(手動): {len(flags)} ===")
for base, why, pt, pv, ex in flags:
    print(f"  {base:<40} {why} 提案巻{pv} 候補{ex[:3]}")

if not APPLY:
    print("\n(dry-run。--apply で適用)")
    sys.exit(0)

# 適用
ali = yaml.safe_load(open(ALI, encoding="utf-8")) or {} if os.path.exists(ALI) else {}
ovr = yaml.safe_load(open(OVR, encoding="utf-8")) or {} if os.path.exists(OVR) else {}
ovr.setdefault("overrides", {})
logf = open(LOG, "a", encoding="utf-8")
n = 0
for base, m, pt, pv in typeA:
    oldslug = m[0]
    for ly in LAYERS:
        op = os.path.join(ly, oldslug + ".yml")
        np = os.path.join(ly, base + ".yml")
        if not os.path.exists(op) or os.path.exists(np):
            continue
        d = yaml.safe_load(open(op, encoding="utf-8")) or {}
        d["slug"] = base
        with open(np, "w", encoding="utf-8") as w:
            yaml.safe_dump(d, w, allow_unicode=True, sort_keys=False, width=10000)
        os.remove(op)
    ali[oldslug] = base
    ovr["overrides"][oldslug] = {"slug": base, "reason": "主版が従版slugに誤収容・無印復帰", "at": NOW}
    logf.write(json.dumps({"ts": NOW, "action": "slug_rename", "target": base,
                           "detected_by": "slug-final-audit", "source": "slug-final-integrated.tsv",
                           "before": {"slug": oldslug}, "after": {"slug": base},
                           "checks": ["slug-final主版提案==無印", "本番で無印消失", "題完全一致が本番に1つ", "無印slug空(衝突なし)"],
                           "confidence": "high", "undo": "slug-overrides該当削除+alias削除+ファイル名を元へ",
                           "state": "applied", "title": m[1], "vols": m[2]}, ensure_ascii=False) + "\n")
    n += 1
logf.close()
with open(ALI, "w", encoding="utf-8") as w:
    yaml.safe_dump(ali, w, allow_unicode=True, sort_keys=True, width=10000)
with open(OVR, "w", encoding="utf-8") as w:
    yaml.safe_dump(ovr, w, allow_unicode=True, sort_keys=False, width=10000)
print(f"\n適用 {n} 件 / flag {len(flags)} 件は手動。change-log+alias+override更新。")

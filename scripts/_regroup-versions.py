"""同一作品内で (type × 冊数) が一致する版を 1edition の刷タブ(versions[])にまとめる。
冊数が同じ=同内容の別刷/別社 と見なし、うる星と同じタブUIで出す。 単独版はそのまま。
usage: python _regroup-versions.py <manga.yml>
"""
import sys, yaml
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")

TYPE_LABEL = {"standard": "通常版", "bunkobon": "文庫版", "wideban": "ワイド版",
              "kanzenban": "完全版", "aizoban": "愛蔵版", "shinsoban": "新装版", "deluxe": "デラックス版"}

def yr(e):
    ys = [str(v.get("release_date"))[:4] for v in e["volumes"] if v.get("release_date")]
    ys = [y for y in ys if y.isdigit()]
    return min(ys) if ys else "9999"

def full(e):
    return all(v.get("isbn13") for v in e["volumes"]) and len(e["volumes"]) > 0

def regroup(path):
    d = yaml.safe_load(open(path, encoding="utf-8"))
    groups = defaultdict(list)
    for e in d["editions"]:
        groups[(e["type"], len(e["volumes"]))].append(e)
    out = []
    for (typ, cnt), grp in groups.items():
        if len(grp) == 1:
            out.append(grp[0])  # 単独はそのまま
            continue
        grp.sort(key=yr)  # 古い順
        default = next((e for e in grp if full(e)), grp[0])  # 完備の最古
        # 刷タブのlabel = edition.label(初版/新装版等)優先 → 無ければ出版社 → 版N
        versions = [{
            "label": e.get("label") or e.get("publisher") or f"版{i+1}",
            "year_started": e.get("year_started") if e.get("year_started") else (int(yr(e)) if yr(e).isdigit() else None),
            "volumes": e["volumes"],
        } for i, e in enumerate(grp)]
        out.append({
            "type": typ,
            "label": f"{TYPE_LABEL.get(typ, '版')}（全{cnt}巻）",
            "publisher": None,  # 出版社は各タブ(version.label)で表示
            "volumes": default["volumes"],
            "versions": versions,
        })
    # 表示順: type優先(standard→bunko→wide→他)、 次に冊数多い順
    order = {"standard": 0, "wideban": 1, "bunkobon": 2, "kanzenban": 3}
    out.sort(key=lambda e: (order.get(e["type"], 9), -len(e["volumes"])))
    d["editions"] = out
    with open(path, "w", encoding="utf-8") as f:
        f.write("# 版/刷タブ regroup 済(同type同冊数を versions[]統合)\n")
        yaml.safe_dump(d, f, allow_unicode=True, sort_keys=False)
    print("regroup:", path)
    for e in out:
        if e.get("versions"):
            print("  [%s] %s ← タブ: %s" % (e["type"], e["label"], " / ".join(f"{v['label']}({v['year_started']})" for v in e["versions"])))
        else:
            print("  [%s] %s (%d巻 単独)" % (e["type"], e.get("publisher") or e["label"], len(e["volumes"])))

if __name__ == "__main__":
    regroup(sys.argv[1])

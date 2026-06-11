"""統合TSV(slug-final-integrated.tsv)の恒久生成器。 ★適用なし=レビュー用シート。

旧版は /tmp 一回限りスクリプト(commit 3f9fc9c0)+手パッチ(ea1dbf/f591)で作られ再生成不能だった。
本スクリプトは全 layer を seed/cache から決定的に再構築する(規則改訂・蒸留後の再実行可)。

layer(後勝ち、 全て key=series_key 基準):
  1. ok_base      : .cache/slug-final.tsv(merge代表collapse+機械suffix済)
  2. c1_main/sub  : slug-collision-option1-candidates.tsv(真の別作品 option1)
  3. c2_suffix系  : slug-c2-suffix-candidates.tsv(different_works/option2/subseries)
  4. c2_merge     : slug-c2-merge-candidates.tsv verdict=merge_all(reps列=分裂耐性)
  5. c3           : slug-malformed-triage-candidates.tsv(外国orphan drop / kana補完keep)
  6. partial_drop : c2 verdict=partial の outliers(画集/アニメコミック/外国語版)
  7. c2_recluster : slug-recluster-candidates.tsv の base(巻レベル分割 → slug-volume-final)
  8. ndl_fix      : slug-fix-candidates.tsv(NDL確証の姓/junk-drop。 suffix部を新baseに載替)

検証: 非DROPページの proposed 一意(merge群内共有は正当)+ recluster新ページとの交差0。
出力 data/seeds/slug-final-integrated.tsv(旧版と同 schema + needs)。 diff統計も表示。
"""
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**7)
ROOT = Path(__file__).resolve().parent.parent
SEEDS = ROOT / "data" / "seeds"
FINAL = ROOT / ".cache" / "slug-final.tsv"
OLD_FINAL = ROOT / ".cache" / "slug-final.tsv.bak-oldrules-20260611"
OUT = SEEDS / "slug-final-integrated.tsv"

DKW = ["COLOR WALK", "RED", "アート", "画集", "アニメブック", "フィルムコミック", "How to",
       "THE 11TH", "THE 12TH", "THE 13TH", "THE 14TH"]


def dr(path):
    return list(csv.DictReader(Path(path).open(encoding="utf-8"), delimiter="\t"))


def main():
    # --- 1. base layer ---
    rows = dr(FINAL)
    rep_disp = {}    # rep -> dict(disposition, proposed, needs)
    rep_info = {}    # rep -> (title, vols, year, base)
    for r in rows:
        rep = r["rep"]
        if rep not in rep_disp:
            rep_disp[rep] = {"disposition": "ok_base", "proposed": r["final_slug"], "needs": ""}
            rep_info[rep] = (r["title"], r["vols"], r["year"], r["base_slug"])

    def set_disp(rep, disp, slug, needs=""):
        if rep in rep_disp:
            rep_disp[rep] = {"disposition": disp, "proposed": slug, "needs": needs}
            return True
        return False

    miss = Counter()

    # --- 2. c1 option1 ---
    n = Counter()
    for r in dr(SEEDS / "slug-collision-option1-candidates.tsv"):
        k = r["key"]
        if r["role"] == "drop-foreign":
            ok = set_disp(k, "c1_foreign_drop", "(DROP)", "drop適用")
        elif r["role"] == "main":
            ok = set_disp(k, "c1_main", r["new_slug"])
        else:
            ok = set_disp(k, "c1_sub", r["new_slug"], r["flag"])
        n["c1" if ok else "c1_miss"] += 1
        if not ok:
            miss["c1"] += 1

    # --- 3. c2 suffix系 ---
    for r in dr(SEEDS / "slug-c2-suffix-candidates.tsv"):
        ok = set_disp(r["key"], f"c2_{r['verdict']}", r["new_slug"], r["flag"])
        n["c2sfx" if ok else "c2sfx_miss"] += 1
        if not ok:
            miss["c2sfx"] += 1

    # --- 4. c2 merge_all (reps列) ---
    merge_groups = []
    for r in dr(SEEDS / "slug-c2-merge-candidates.tsv"):
        if r["verdict"] != "merge_all":
            continue
        reps = [x for x in (r.get("reps") or "").split("\x1f") if x and x in rep_disp]
        if len(reps) < 2:
            continue
        merge_groups.append((r["base"], reps))
        for k in reps:
            set_disp(k, "c2_merge", r["base"], "merge適用")
        n["c2merge_groups"] += 1

    # --- 5. c3 malformed (title-keyed) ---
    c3 = dr(SEEDS / "slug-malformed-triage-candidates.tsv")
    c3drop = {r["title"] for r in c3 if "drop" in r["disposition"]}
    for rep, (title, _, _, _) in rep_info.items():
        if title in c3drop:
            set_disp(rep, "c3_drop", "(DROP)", "drop適用")
            n["c3drop"] += 1

    # --- 6. partial outliers ---
    partial = {}
    for r in dr(SEEDS / "slug-c2-merge-candidates.tsv"):
        if r["verdict"] == "partial":
            partial[r["base"]] = set(filter(None, (r.get("outliers") or "").split("|")))
    for rep, (title, _, _, base) in rep_info.items():
        ols = partial.get(base)
        if not ols:
            continue
        for ol in ols:
            if ol and ol[:10] in title and any(k in ol for k in DKW):
                set_disp(rep, "partial_drop", "(DROP)", "drop適用")
                n["partial_drop"] += 1
                break

    # --- 7. recluster (base単位 → 巻レベル分割) ---
    recl_bases = {r["base"] for r in dr(SEEDS / "slug-recluster-candidates.tsv")}
    recl_slugs = {r["slug"] for r in dr(SEEDS / "slug-recluster-candidates.tsv")}
    for rep, (_, _, _, base) in rep_info.items():
        if base in recl_bases:
            set_disp(rep, "c2_recluster", "(SPLIT→slug-volume-final)", "巻分割")
            n["recluster"] += 1

    # --- 8. NDL fix overlay (suffix部を新baseに載せ替え) ---
    old_r2b = {}
    for r in dr(OLD_FINAL):
        old_r2b.setdefault(r["rep"], r["base_slug"])
    for r in dr(SEEDS / "slug-fix-candidates.tsv"):
        k = r["key"]
        if k not in rep_disp:
            miss["fix"] += 1
            continue
        if r["new_slug"] == "(DROP)":
            set_disp(k, "ndl_junk_drop", "(DROP)", "drop適用")
            n["fix_drop"] += 1
            continue
        ob = old_r2b.get(k, "")
        nb = rep_info[k][3]
        if ob and r["new_slug"].startswith(ob):
            rebuilt = nb + r["new_slug"][len(ob):]
            set_disp(k, "ndl_fix", rebuilt, r["method"])
            n["fix_rebuilt"] += 1
        elif r["new_slug"].startswith(nb):
            set_disp(k, "ndl_fix", r["new_slug"], r["method"])
            n["fix_asis"] += 1
        else:
            # base prefix と無関係な全置換型(数字二重化のNDL正式題再生成 等) → 値をそのまま採用
            # (値は新規則で維持する: 規則改訂時は fix TSV 側を更新する)
            set_disp(k, "ndl_fix", r["new_slug"], f"full({r['method']})")
            n["fix_full"] += 1

    # --- 検証: 一意性 ---
    merge_slug_groups = {b for b, _ in merge_groups}
    page_slugs = Counter()
    for rep, d in rep_disp.items():
        s = d["proposed"]
        if s.startswith("(") or not s:
            continue
        page_slugs[s] += 1
    dups = {s: c for s, c in page_slugs.items() if c > 1 and s not in merge_slug_groups}
    cross_recl = recl_slugs & set(page_slugs)
    print(f"layer適用: {dict(n)}")
    if dict(miss):
        print(f"key不一致(miss): {dict(miss)}")
    print(f"★一意性: ページslug {len(page_slugs):,} / 不正重複 {len(dups)} / recluster交差 {len(cross_recl)}")
    for s, c in list(dups.items())[:20]:
        print(f"   DUP x{c}: {s}")
    for s in list(cross_recl)[:10]:
        print(f"   RECL-CROSS: {s}")

    # --- diff vs 旧統合TSV ---
    old_int = {}
    if OUT.exists():
        for r in dr(OUT):
            old_int[r["key"]] = r["proposed_slug"]

    # --- 出力(全keyごと、 rep の disposition を反映) ---
    diff = Counter()
    with OUT.open("w", encoding="utf-8", newline="") as f:
        f.write("key\ttitle\tvols\tyear\tbase_slug\tdisposition\tproposed_slug\tneeds\trep\n")
        for r in rows:
            rep = r["rep"]
            d = rep_disp.get(rep)
            if not d:
                continue
            f.write(f"{r['key']}\t{r['title']}\t{r['vols']}\t{r['year']}\t{r['base_slug']}\t"
                    f"{d['disposition']}\t{d['proposed']}\t{d['needs']}\t{rep}\n")
            o = old_int.get(r["key"])
            if o is None:
                diff["new_key"] += 1
            elif o == d["proposed"]:
                diff["same"] += 1
            else:
                old_n = re.sub(r"ou|oo|uu", lambda m: m.group(0)[0], o)
                new_n = re.sub(r"ou|oo|uu", lambda m: m.group(0)[0], d["proposed"])
                if old_n == new_n or o == new_n:
                    diff["long_vowel"] += 1
                elif o.replace("wo", "o") == d["proposed"] or o.replace("-wo-", "-o-") == d["proposed"]:
                    diff["wo_to_o"] += 1
                else:
                    diff["other"] += 1
    total = sum(diff.values())
    print(f"\n=== 旧統合TSVとの diff(全{total:,} key)===")
    for k, v in diff.most_common():
        print(f"  {k}: {v:,} ({v*100//max(total,1)}%)")
    disp_c = Counter(d["disposition"] for d in rep_disp.values())
    print(f"\ndisposition(rep単位 {len(rep_disp):,}): {dict(disp_c.most_common())}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

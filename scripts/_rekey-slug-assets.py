"""slug規則改訂(2026-06-10: 長音保持/ヲ=o)に伴う、旧baseキー資産の繋ぎ直し。

base slug が変わると base 名で繋がる検証済み資産が dangle する。 rep(series_key)は不変
なので rep 経由で旧base→新base を機械再キーする(裁定・証拠は不変=純粋キー更新)。

対象(in-place 更新、 git 履歴が旧版を保持):
  1. data/seeds/slug-c2-merge-candidates.tsv : base 再キー + ★reps 列追加
     (merge_all は群全 reps を保持 = 長音分裂で衝突が解けても merge 意図を失わない)
  2. data/seeds/slug-recluster-candidates.tsv: base 再キー + slug の base-prefix 置換
  3. data/seeds/slug-volume-final.tsv        : base 再キー + final_slug の base-prefix 置換

入力: .cache/slug-final.tsv.bak-oldrules-20260611 (旧) / .cache/slug-final.tsv (新)。
★適用なし(seed 候補ファイルの更新のみ)。 分裂(1旧base→複数新base)は flag して報告。
"""
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**7)
ROOT = Path(__file__).resolve().parent.parent
OLD = ROOT / ".cache" / "slug-final.tsv.bak-oldrules-20260611"
NEW = ROOT / ".cache" / "slug-final.tsv"
SEEDS = ROOT / "data" / "seeds"


def load_final(path):
    """rep→(base, final)(rep単位 dedup)。"""
    rep2 = {}
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            rep2.setdefault(r["rep"], (r["base_slug"], r["final_slug"]))
    return rep2


def main():
    old2 = load_final(OLD)
    new2 = load_final(NEW)
    old_r2b = {k: v[0] for k, v in old2.items()}
    new_r2b = {k: v[0] for k, v in new2.items()}
    old_final2rep = {}
    for rep, (_, fin) in old2.items():
        old_final2rep.setdefault(fin, rep)
    new_bases = {b for b, _ in new2.values()}
    new_finals = {f for _, f in new2.values()}
    new_r2f = {k: v[1] for k, v in new2.items()}

    # 旧base → reps / 旧base → 新base集合
    oldbase2reps = defaultdict(list)
    for rep, b in old_r2b.items():
        oldbase2reps[b].append(rep)
    ob2nb = {}
    for ob, reps in oldbase2reps.items():
        nbs = sorted({new_r2b[r] for r in reps if r in new_r2b})
        ob2nb[ob] = nbs

    def remap_one(ob):
        """1:1 のときだけ新baseを返す。 分裂/消失は None。"""
        nbs = ob2nb.get(ob, [])
        return nbs[0] if len(nbs) == 1 else None

    # ---- 1. c2 merge candidates ----
    p = SEEDS / "slug-c2-merge-candidates.tsv"
    rows = list(csv.DictReader(p.open(encoding="utf-8"), delimiter="\t"))
    out = []
    stats = Counter()
    for r in rows:
        ob = r["base"]
        reps = [x for x in oldbase2reps.get(ob, []) if x in new_r2b]
        if not reps:
            stats["c2_lost"] += 1
            out.append({**r, "reps": "", "rekey": "LOST_NO_REPS"})
            continue
        by_nb = defaultdict(list)
        for x in reps:
            by_nb[new_r2b[x]].append(x)
        # ★key 自体が「|」を含むため、 reps の区切りは \x1f (unit separator) を使う
        if len(by_nb) == 1:
            nb = next(iter(by_nb))
            tag = "" if nb == ob else "REKEYED"
            stats["c2_same" if nb == ob else "c2_rekeyed"] += 1
            out.append({**r, "base": nb, "reps": "\x1f".join(reps), "rekey": tag})
        elif r["verdict"] == "merge_all":
            # ★同一作の群が長音で base 分裂 → 衝突は解けても merge 意図は維持(全reps保持)
            nb = max(by_nb, key=lambda k: len(by_nb[k]))
            stats["c2_split_mergeall"] += 1
            out.append({**r, "base": nb, "reps": "\x1f".join(reps), "rekey": "SPLIT_KEEP_ALL_REPS"})
        else:
            # suffix系は「まだ衝突している部分」のみ意味を持つ → 新baseごとに行を分ける
            stats["c2_split_other"] += 1
            for nb, sub in sorted(by_nb.items()):
                out.append({**r, "base": nb, "reps": "\x1f".join(sub), "rekey": "SPLIT_SUBSET"})
    fields = [c for c in rows[0].keys() if c not in ("reps", "rekey")] + ["reps", "rekey"]
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        w.writeheader()
        w.writerows(out)
    print(f"1. c2: {len(rows)}行 → {len(out)}行  {dict(stats)}")

    # ---- 2. recluster candidates ----
    p = SEEDS / "slug-recluster-candidates.tsv"
    rows = list(csv.DictReader(p.open(encoding="utf-8"), delimiter="\t"))
    st2 = Counter()
    for r in rows:
        ob = r["base"]
        nb = remap_one(ob)
        if nb is None:
            st2["flag_split_or_lost"] += 1
            r["rekey"] = "REVIEW"
            continue
        if nb != ob:
            st2["rekeyed"] += 1
            if r["slug"].startswith(ob):
                r["slug"] = nb + r["slug"][len(ob):]
            r["base"] = nb
            r["rekey"] = "REKEYED"
        else:
            st2["same"] += 1
            r["rekey"] = ""
    fields = list(rows[0].keys())
    if "rekey" not in fields:
        fields.append("rekey")
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    print(f"2. recluster: {len(rows)}行  {dict(st2)}")

    # ---- 3. volume-final (ISBN→ページslug) ----
    p = SEEDS / "slug-volume-final.tsv"
    rows = list(csv.DictReader(p.open(encoding="utf-8"), delimiter="\t"))
    st3 = Counter()
    for r in rows:
        ob = r.get("base", "")
        if not ob:
            st3["no_base"] += 1
            r["rekey"] = ""
            continue
        nb = remap_one(ob)
        if nb is not None:
            if nb != ob:
                st3["rekeyed"] += 1
                if r["final_slug"].startswith(ob):
                    r["final_slug"] = nb + r["final_slug"][len(ob):]
                else:
                    st3["prefix_mismatch"] += 1
                    r["rekey"] = "REVIEW_PREFIX"
                    continue
                r["base"] = nb
                r["rekey"] = "REKEYED"
            else:
                st3["same"] += 1
                r["rekey"] = ""
            continue
        # base が slug-final の base に無い → 別系統の参照を順に判定
        if r["final_slug"] in new_finals or ob in new_bases:
            st3["already_current"] += 1     # 既に新規則の明示ページ名(魔法科map等)
            r["rekey"] = ""
        elif ob in old_final2rep:
            # base欄に旧final(接尾辞付)が入っている行 → rep経由で新finalへ
            rep = old_final2rep[ob]
            nf = new_r2f.get(rep)
            if nf and r["final_slug"].startswith(ob):
                r["final_slug"] = nf + r["final_slug"][len(ob):]
                r["base"] = new_r2b.get(rep, ob)
                st3["rekeyed_via_final"] += 1
                r["rekey"] = "REKEYED_FINAL"
            else:
                st3["flag_split_or_lost"] += 1
                r["rekey"] = "REVIEW"
        else:
            # 本番ページ名(旧promote由来)参照 → slug適用時に本番→新slug表で解決
            st3["apply_time"] += 1
            r["rekey"] = "REVIEW_APPLYTIME"
    fields = list(rows[0].keys())
    if "rekey" not in fields:
        fields.append("rekey")
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    print(f"3. volume-final: {len(rows)}行  {dict(st3)}")

    # ---- 4. 新triage の衝突群に c2 裁定が無いもの(=新規レビュー対象)を報告 ----
    tri = ROOT / ".cache" / "slug-collision-triage.tsv"
    verd = {r["base"] for r in out}
    missing = []
    with tri.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["category"] in ("merge_miss", "year_suspect") and r["base"] not in verd:
                missing.append((r["category"], r["base"], r["pages"][:80]))
    print(f"4. 新triage(merge_miss/year_suspect)で裁定なし: {len(missing)} 群")
    for c, b, d in missing[:30]:
        print(f"   [{c}] {b} : {d}")
    if missing:
        mp = ROOT / ".cache" / "c2-unverdicted-new.tsv"
        with mp.open("w", encoding="utf-8") as f:
            f.write("category\tbase\tpages\n")
            for c, b, d in missing:
                f.write(f"{c}\t{b}\t{d}\n")
        print(f"   → {mp}")


if __name__ == "__main__":
    main()

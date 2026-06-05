"""gap c-1: 真の別作品(著者非共有・別年=偶然同名)に option1 接尾辞を当てる候補生成。

option1 = 主版を無印、 従版に `-作画家姓-初出年`。 主版選定は決定的 tie-break:
  巻数多 → 初出年古 → 姓ローマ字昇順。 これで URL が deterministic に安定。

★対象は triage の "diff_works"(= 著者非共有・別年)のみ。 著者共有(merge漏れ/option2)や
  同年衝突は別工程。 ★適用なし(候補 TSV 出力のみ)。 姓は pykakasi 由来=要レビュー。
"""
import csv
import importlib.util
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
FINAL = ROOT / ".cache" / "slug-final.tsv"
TRIAGE = ROOT / ".cache" / "slug-collision-triage.tsv"
MATCH = ROOT / ".cache" / "match-v14-all.tsv"
DB = ROOT / ".cache" / "db-v2.sqlite"
OUT = ROOT / "data" / "seeds" / "slug-collision-option1-candidates.tsv"


def load_isbn_foreign():
    """series_key → True(全ISBN非9784=外国版) / False(日本ISBN有) / None(ISBN無)。
    ★クリーンlatin題の外国版(Akira等)が真の別作品に紛れるのを ISBN国コードで弾く。"""
    con = sqlite3.connect(DB)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    out = {}
    q = """SELECT s.series_key, v.isbn13 FROM series s
           JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id
           WHERE v.isbn13 IS NOT NULL"""
    agg = defaultdict(list)
    for sk, isbn in con.execute(q):
        agg[sk].append(str(isbn).replace("-", ""))
    con.close()
    for sk, ibs in agg.items():
        jp = any(i.startswith("9784") for i in ibs)
        out[sk] = (not jp) if ibs else None
    return out


def load_assemble():
    spec = importlib.util.spec_from_file_location("asm", ROOT / "scripts" / "_slug-assemble.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    asm = load_assemble()

    # ★姓ローマ字の正規ソース = AniList staff.full (native→姓、 Art役割優先)。
    #   長音は drop_long で落とす(Ootomo→otomo)= slug規則準拠。 pykakasi は fallback。
    nat2sur = json.loads((ROOT / ".cache" / "anilist-author-surname.json").read_text(encoding="utf-8"))

    def anilist_sur(name):
        s = nat2sur.get((name or "").strip())
        return re.sub(r"[^a-z]", "", asm.drop_long(s)) if s else ""

    def resolve_surname(rep):
        a0 = (a_auth.get(rep, "") or "").strip()
        ao = asm.author_of(rep)
        for nm in (a0, ao):
            s = anilist_sur(nm)
            if s:
                return s, "anilist"
        # fallback = pykakasi (誤読あり=要確認)
        s = asm.surname_romaji(a0) or asm.surname_romaji(ao)
        return (s, "pykakasi") if s else ("", "none")

    # match-v14: series_key → a_authors[0] (作画家姓の優先ソース)
    a_auth = {}
    with MATCH.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"].startswith("S") and r.get("a_authors"):
                a_auth[r["s3_key"]] = r["a_authors"].split("|")[0]

    # diff_works の base 集合
    diff = set()
    with TRIAGE.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["category"] == "diff_works":
                diff.add(r["base"])

    foreign = load_isbn_foreign()

    # slug-final を rep 重複排除しつつ base ごとに集約
    groups = defaultdict(list)
    seen = set()
    with FINAL.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["rep"] in seen:
                continue
            seen.add(r["rep"])
            if r["base_slug"] not in diff:
                continue
            sur, sur_src = resolve_surname(r["rep"])
            groups[r["base_slug"]].append(
                {"rep": r["rep"], "title": r["title"], "vols": int(r["vols"] or 0),
                 "year": r["year"], "sur": sur, "sur_src": sur_src,
                 "foreign": foreign.get(r["rep"]) is True}
            )

    out = []
    used = set()            # 生成 slug の一意性担保
    no_sur = 0
    drop_fore = 0
    resolved_by_drop = 0
    for base, pages in groups.items():
        # ★外国版(全ISBN非9784)は suffix でなく drop 行き(クリーンlatin外国版を分離)
        fore = [p for p in pages if p["foreign"]]
        real = [p for p in pages if not p["foreign"]]
        for p in fore:
            drop_fore += 1
            out.append((base, "drop-foreign", "", p["title"], p["vols"], p["year"], p["sur"], p["sur_src"], "FOREIGN_DROP"))
        if len(real) < 2:
            # 外国版を抜くと衝突解消 = 残り1件は無印のまま(suffix不要)
            if len(real) == 1 and fore:
                resolved_by_drop += 1
                p = real[0]
                out.append((base, "main", base, p["title"], p["vols"], p["year"], p["sur"], p["sur_src"], "RESOLVED_BY_FOREIGN_DROP"))
            continue
        # 決定的 tie-break: 巻数多 desc, 年古 asc, 姓(anilistのみ) asc, rep asc
        def sortkey(p):
            s = p["sur"] if p["sur_src"] == "anilist" else ""
            return (-p["vols"], int(p["year"] or 9999), s or "zzzz", p["rep"])
        ps = sorted(real, key=sortkey)
        for i, p in enumerate(ps):
            if i == 0:
                used.add(base)
                out.append((base, "main", base, p["title"], p["vols"], p["year"],
                            p["sur"] if p["sur_src"] == "anilist" else "", p["sur_src"], ""))
                continue
            yr = p["year"] if (p["year"] and p["year"] != "9999") else ""
            use_sur = p["sur"] if p["sur_src"] == "anilist" else ""   # ★AniList姓のみ採用
            parts = [base]
            if use_sur:
                parts.append(use_sur)
            if yr:
                parts.append(yr)
            slug = "-".join(parts)
            if slug in used or not yr:
                # -年(姓なし)で区別不能 = ★Web検証で作画家姓が要る (or 年欠落)
                no_sur += 1
                flag = "NEED_SURNAME_VERIFY"
                cand = slug if slug else base
                k = 2
                while cand in used:
                    cand = f"{(slug or base)}-{k}"
                    k += 1
            else:
                flag = ""
                cand = slug
            used.add(cand)
            out.append((base, "sub", cand, p["title"], p["vols"], p["year"], use_sur, p["sur_src"], flag))

    with OUT.open("w", encoding="utf-8") as f:
        f.write("base\trole\tnew_slug\ttitle\tvols\tyear\tsurname\tsur_src\tflag\n")
        for x in out:
            f.write("\t".join(str(v).replace("\t", " ") for v in x) + "\n")

    grp = len([b for b, p in groups.items() if len(p) >= 2])
    print(f"=== gap c-1 option1 候補: {grp:,} 群 / {len(out):,} 行 ({OUT.name}) ===")
    print(f"  主版(無印): {sum(1 for x in out if x[1]=='main'):,}")
    print(f"  従版(接尾辞): {sum(1 for x in out if x[1]=='sub'):,}")
    print(f"  ★外国版→drop(非9784・別工程): {drop_fore:,}")
    print(f"  ★外国版dropで衝突解消(残1=無印): {resolved_by_drop:,}")
    subs = [x for x in out if x[1] == "sub"]
    with_sur = sum(1 for x in subs if x[6])
    need_verify = sum(1 for x in subs if x[8] == "NEED_SURNAME_VERIFY")
    print(f"  従版 {len(subs):,}: AniList姓で -姓-年 = {with_sur:,} / -年のみ = {len(subs)-with_sur-need_verify:,} / ★Web検証要(同年衝突/年欠落) = {need_verify:,}")
    print("\n=== サンプル12群 ===")
    shown = 0
    cur = None
    for x in out:
        if x[0] != cur:
            cur = x[0]
            shown += 1
            if shown > 12:
                break
            print(f"  [{x[0]}]")
        print(f"      {x[1]:<4} {x[2]:<30} ← {x[3][:18]} (v{x[4]},{x[5]},{x[6] or '—'})")


if __name__ == "__main__":
    main()

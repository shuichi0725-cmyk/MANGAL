"""gap c-2 slug 生成: c2_suffix / option2 / subtitle の最終slugを確定ルールで生成(★適用なし)。

c-1 の option1 ロジックを c-2 の非merge群へ適用:
  - different_works / no_merge → option1(主版無印 + 従版 `-姓-年`/`-年`)。
  - option2               → ★全版 `-姓-年`、 無印を作らない(原作+別作画)。
  - subseries             → ★副題で区別(共通prefixを超える差分をヘボン append)。

姓 = AniList staff.full(長音drop)、 無ければ年のみ。 外国版(非9784)は除外。
一意性検証 = 生成slug全ユニーク + 群外の確定slugとの交差衝突0。
出力 data/seeds/slug-c2-suffix-candidates.tsv。
"""
import csv
import importlib.util
import json
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
FINAL = ROOT / ".cache" / "slug-final.tsv"
C2 = ROOT / "data" / "seeds" / "slug-c2-merge-candidates.tsv"
INTEG = ROOT / "data" / "seeds" / "slug-final-integrated.tsv"
MATCH = ROOT / ".cache" / "match-v14-all.tsv"
DB = ROOT / ".cache" / "db-v2.sqlite"
OUT = ROOT / "data" / "seeds" / "slug-c2-suffix-candidates.tsv"

SUFFIX_V = {"different_works", "no_merge"}


def load_asm():
    spec = importlib.util.spec_from_file_location("asm", ROOT / "scripts" / "_slug-assemble.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def lcp(strs):
    if not strs:
        return ""
    a, b = min(strs), max(strs)
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    return a[:i]


def main():
    asm = load_asm()
    nat2sur = json.loads((ROOT / ".cache" / "anilist-author-surname.json").read_text(encoding="utf-8"))
    a_auth = {}
    with MATCH.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"].startswith("S") and r.get("a_authors"):
                a_auth[r["s3_key"]] = r["a_authors"].split("|")[0]

    def anilist_sur(name):
        s = nat2sur.get((name or "").strip())
        return re.sub(r"[^a-z]", "", asm.drop_long(s)) if s else ""

    def surname(rep):
        a0 = (a_auth.get(rep, "") or "").strip()
        ao = asm.author_of(rep)
        for nm in (a0, ao):
            s = anilist_sur(nm)
            if s:
                return s
        return ""  # pykakasi誤読は不採用

    # ISBN国コード(外国版除外)
    con = sqlite3.connect(DB)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    agg = defaultdict(list)
    for sk, isbn in con.execute(
        "SELECT s.series_key,v.isbn13 FROM series s JOIN editions e ON e.series_id=s.id "
        "JOIN volumes v ON v.edition_id=e.id WHERE v.isbn13 IS NOT NULL"
    ):
        agg[sk].append(str(isbn).replace("-", ""))
    con.close()
    foreign = {sk: (not any(i.startswith("9784") for i in ibs)) for sk, ibs in agg.items()}

    verdict = {r["base"]: r["verdict"] for r in csv.DictReader(C2.open(encoding="utf-8"), delimiter="\t")}
    targets = {b for b, v in verdict.items() if v in SUFFIX_V or v in ("option2", "subseries")}

    # 群外の確定slug(交差衝突チェック用)= ★slug-final の final + c-1 候補(対象群以外)。
    # 旧実装の統合TSV(INTEG)参照は規則改訂で stale になるため廃止(2026-06-11)。
    taken = set()
    _seen_rep = set()
    with FINAL.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["rep"] in _seen_rep:
                continue
            _seen_rep.add(r["rep"])
            if r["base_slug"] not in targets and r["final_slug"]:
                taken.add(r["final_slug"])
    _c1 = ROOT / "data" / "seeds" / "slug-collision-option1-candidates.tsv"
    for r in csv.DictReader(_c1.open(encoding="utf-8"), delimiter="\t"):
        if r["new_slug"] and r["base"] not in targets:
            taken.add(r["new_slug"])

    # 群集約(rep dedup, 外国版除外)
    groups = defaultdict(list)
    seen = set()
    with FINAL.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["rep"] in seen:
                continue
            seen.add(r["rep"])
            if r["base_slug"] in targets and not (foreign.get(r["rep"]) is True):
                groups[r["base_slug"]].append(
                    {"rep": r["rep"], "title": r["title"], "vols": int(r["vols"] or 0), "year": r["year"]}
                )

    used = set(taken)
    out = []

    def uniq(slug, base):
        cand = slug or base
        k = 2
        while cand in used:
            cand = f"{slug or base}-{k}"
            k += 1
        used.add(cand)
        return cand

    def sfx(base, sur, yr):
        parts = [base]
        if sur:
            parts.append(sur)
        if yr and yr != "9999":
            parts.append(yr)
        return "-".join(parts)

    for base, pages in groups.items():
        v = verdict[base]
        if len(pages) < 2:
            continue
        if v in SUFFIX_V or v == "option2":
            ps = sorted(pages, key=lambda p: (-p["vols"], int(p["year"] or 9999), surname(p["rep"]) or "zzzz", p["rep"]))
            for i, p in enumerate(ps):
                sur = surname(p["rep"])
                yr = p["year"] if (p["year"] and p["year"] != "9999") else ""
                if v != "option2" and i == 0:
                    cand = uniq(base, base)  # option1: 主版無印
                    flag = ""
                else:
                    slug = sfx(base, sur, yr)  # option2は全版suffix
                    flag = "" if sur else ("YEAR_ONLY" if yr else "NEED_TIEBREAK")
                    cand = uniq(slug, base)
                out.append((p["rep"], base, v, "main" if (v != "option2" and i == 0) else "sub",
                            cand, p["title"], sur, flag))
        elif v == "subseries":
            common = lcp([p["title"] for p in pages])
            if len(common) < 2:
                # 共通prefix無し = 真の副題関係でない(表記違い等)→ 年/姓 fallback + flag
                ps = sorted(pages, key=lambda p: (-p["vols"], int(p["year"] or 9999), p["rep"]))
                for i, p in enumerate(ps):
                    sur = surname(p["rep"])
                    yr = p["year"] if (p["year"] and p["year"] != "9999") else ""
                    cand = uniq(base, base) if i == 0 else uniq(sfx(base, sur, yr), base)
                    out.append((p["rep"], base, v, "main" if i == 0 else "sub", cand,
                                p["title"], sur, "SUBSERIES_NO_PREFIX"))
                continue
            for p in pages:
                sub = p["title"][len(common):]
                sub = re.sub(r"^[\s　・,，.。!！?？\-―ー~〜:：/／]+", "", sub)
                if not sub:
                    cand = uniq(base, base)  # 本編=無印
                    flag = ""
                else:
                    ssl = asm.subtitle_slug(sub)
                    cand = uniq(f"{base}-{ssl}" if ssl else base, base)
                    flag = "SUBTITLE_REVIEW" if (not ssl or re.search(r"[0-9]", ssl)) else ""
                out.append((p["rep"], base, v, "sub" if sub else "main", cand, p["title"], "", flag))

    with OUT.open("w", encoding="utf-8") as f:
        f.write("key\tbase\tverdict\trole\tnew_slug\ttitle\tsurname\tflag\n")
        for x in out:
            f.write("\t".join(str(v).replace("\t", " ") for v in x) + "\n")

    from collections import Counter
    vc = Counter(x[2] for x in out)
    fc = Counter(x[7] for x in out if x[7])
    gen = [x[4] for x in out]
    print(f"=== gap c-2 slug生成 {len(out)} 行 / {len(groups)} 群 ({OUT.name}) ===")
    print(f"  verdict別: {dict(vc)}")
    print(f"  flag: {dict(fc)}")
    print(f"  ★一意性: 生成{len(gen)} / ユニーク{len(set(gen))} / 重複{len(gen)-len(set(gen))} / 群外交差衝突0(usedで担保)")
    print("\n=== サンプル ===")
    cur = None
    n = 0
    for x in sorted(out, key=lambda r: (r[2], r[1])):
        if x[1] != cur:
            cur = x[1]
            n += 1
            if n > 14:
                break
            print(f"  [{x[2]}] {x[1]}")
        print(f"      {x[3]:<4} {x[4]:<34} ← {x[5][:20]} {('姓='+x[6]) if x[6] else ''} {x[7]}")


if __name__ == "__main__":
    main()

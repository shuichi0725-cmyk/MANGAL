"""MADB 504 (Agent master) 由来の作者を mangaka 補完 CSV に書き出す。

Wikidata 由来の `data/seed/mangaka.csv`(6,751名)に居ない作者(原作者・新人・成年作家等)を
MADB から補完し、種2 build の series_authors 紐付けカバレッジを上げる。

方針(plan: mangaka.csv 拡充):
  - 識別子: ma:ndla があれば `ndl:<8桁>`、無ければ `madb:<C-ID>`(Wikidata QID は使わない)。
  - ndla で重複 C-ID を名寄せ(高橋留美子3個→1 等)。
  - 団体(additionalGenre=団体)は除外、個人のみ。
  - 既存 mangaka.csv に正規化名が在る作者は skip(= Wikidata Q を優先、二重登録回避)。
  - 出力列は mangaka.csv と同一: qid,name,birth_year,death_year,alt_names,has_adult_credit。
    has_adult_credit は false(成年判定は _apply-adult-filter の adult_mangaka_known × 比率で実施)。

出力: data/seed/mangaka-madb.csv
"""

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META101 = ROOT / ".cache" / "madb" / "metadata101-clean.json"
META104 = ROOT / ".cache" / "madb" / "metadata104.json"
META504 = ROOT / ".cache" / "madb" / "metadata504.json"
MANGAKA_CSV = ROOT / "data" / "seed" / "mangaka.csv"
OUT = ROOT / "data" / "seed" / "mangaka-madb.csv"


def norm(s: str) -> str:
    return re.sub(r"[・\s　,，、.·]+", "", s or "")


def load_504():
    """cid -> {name, ndla, genre, birth}。"""
    out = {}
    data = json.load(open(META504, encoding="utf-8"))["@graph"]
    for b in data:
        cid = b.get("schema:identifier", "")
        if not cid:
            continue
        nm = b.get("schema:name", "") or b.get("rdfs:label", "")
        if isinstance(nm, list):
            nm = nm[0] if nm else ""
        if isinstance(nm, dict):
            nm = nm.get("@value", "")
        if not isinstance(nm, str):
            nm = ""
        ndla = re.search(r"(\d{8})", str(b.get("ma:ndla", "")))
        bd = re.search(r"(\d{4})", str(b.get("schema:birthDate", "")))
        out[cid] = {
            "name": nm,
            "ndla": ndla.group(1) if ndla else "",
            "genre": b.get("ma:additionalGenre", ""),
            "birth": bd.group(1) if bd else "",
        }
    return out


def collect_author_cids():
    """metadata101 + 104 の dcterms:creator C-ID 集合 (= 漫画に出る作者)。"""
    cids = set()

    def scan(path, label):
        data = json.load(open(path, encoding="utf-8"))["@graph"]
        print(f"  {label}: {len(data)} records", file=sys.stderr)
        for b in data:
            c = b.get("dcterms:creator")
            if isinstance(c, dict):
                c = [c]
            if isinstance(c, list):
                for x in c:
                    if isinstance(x, dict):
                        cid = x.get("@id", "").rsplit("/", 1)[-1]
                        if cid:
                            cids.add(cid)

    print("[scan] dcterms:creator ...", file=sys.stderr)
    scan(META104, "104")
    scan(META101, "101")
    return cids


def load_mangaka_norm_set():
    s = set()
    with MANGAKA_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            s.add(norm(row["name"]))
            for a in (row.get("alt_names") or "").split("|"):
                if a.strip():
                    s.add(norm(a))
    return s


def main():
    print("loading metadata504 ...", file=sys.stderr)
    ag = load_504()
    print(f"  agents: {len(ag)}", file=sys.stderr)

    author_cids = collect_author_cids()
    print(f"  漫画に出る作者 C-ID: {len(author_cids)}", file=sys.stderr)

    mk_norm = load_mangaka_norm_set()
    print(f"  mangaka.csv 正規化名: {len(mk_norm)}", file=sys.stderr)

    # ndla(無ければ cid)で名寄せグループ化
    groups: dict[str, list[str]] = defaultdict(list)  # key -> [cid,...]
    for cid in author_cids:
        info = ag.get(cid)
        if not info or not info["name"]:
            continue
        if info["genre"] == "団体":
            continue  # 個人のみ
        key = ("ndl:" + info["ndla"]) if info["ndla"] else ("madb:" + cid)
        groups[key].append(cid)

    rows = []
    skipped_existing = 0
    for key, cids in groups.items():
        names = []
        births = []
        for cid in cids:
            info = ag[cid]
            if info["name"] and info["name"] not in names:
                names.append(info["name"])
            if info["birth"]:
                births.append(info["birth"])
        # 既存 mangaka.csv と重複(正規化名一致)なら skip
        if any(norm(n) in mk_norm for n in names):
            skipped_existing += 1
            continue
        primary = names[0]
        alt = "|".join(names[1:])
        birth = births[0] if births else ""
        rows.append({
            "qid": key,
            "name": primary,
            "birth_year": birth,
            "death_year": "",
            "alt_names": alt,
            "has_adult_credit": "false",
        })

    rows.sort(key=lambda r: r["qid"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["qid", "name", "birth_year", "death_year", "alt_names", "has_adult_credit"],
        )
        w.writeheader()
        w.writerows(rows)

    n_ndl = sum(1 for r in rows if r["qid"].startswith("ndl:"))
    n_madb = sum(1 for r in rows if r["qid"].startswith("madb:"))
    print(f"\n=== 出力 ===", file=sys.stderr)
    print(f"  既存重複 skip: {skipped_existing}", file=sys.stderr)
    print(f"  書き出し: {len(rows)} (ndl:{n_ndl} / madb:{n_madb})", file=sys.stderr)
    print(f"  wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()

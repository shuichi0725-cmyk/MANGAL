#!/usr/bin/env python3
"""著者QID監査の対象頁を NDL 書誌(役割つき)で裁定し、頁データの是正案を作る (2026-10-22)

入力: docs/production-diagnostics/author-qid-audit.tsv + .cache/author-qid-ndl.jsonl(_audit-author-qid-ndl.py)
出力: docs/production-diagnostics/author-qid-proposals.tsv(案のみ。 ★本番には書かない)

NDL の役割 → MANGAL の欄(既存頁の書き方 = DEATH NOTE / 転スラ / ありふれた に合わせる):
  原作・作・脚本・シナリオ(+「原作・監修」等の複合) → original_authors(role writer)
  漫画・作画・画・絵・まんが                        → authors(role artist)
  原案・キャラクター原案・キャラクターデザイン・監修・構成・企画 等 → credits(role=NDLの役割語)
  著 / 編 / 役割なし                                → 判定材料のみ(足さない)

判定:
  ADD        頁の著者は全員 NDL に居る。 NDL に居て頁に無い人を、上の対応で足す案(純粋追加)
  CONFLICT   頁の著者欄に NDL に居ない人が居る(出版社名・(unknown)・別人)= 頁の著者が誤りの疑い。 人が裁定
  QID_ONLY   頁と NDL は一致、 QID の人物は NDL に居ない = 頁は正しく QID だけが別人
  OK_CREDIT  頁と NDL は一致、 QID の人物は NDL で副次クレジット(キャラ原案等)= 足すのは credits だけ
  NO_NDL     NDL に無い/ISBN 無し = 判定材料なし
"""
import collections, csv, json, os, re, sqlite3, sys, unicodedata

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUD = os.path.join(ROOT, "docs", "production-diagnostics", "author-qid-audit.tsv")
NDL = os.path.join(ROOT, ".cache", "author-qid-ndl.jsonl")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "author-qid-proposals.tsv")

VAR = str.maketrans({"齋": "斎", "齊": "斉", "邊": "辺", "邉": "辺", "髙": "高", "﨑": "崎", "嶋": "島", "濱": "浜",
                     "澤": "沢", "國": "国", "廣": "広", "櫻": "桜", "眞": "真", "惠": "恵", "德": "徳", "藏": "蔵"})
WRITER = ("原作", "作", "脚本", "シナリオ", "ストーリー")
ARTIST = ("漫画", "作画", "画", "絵", "まんが", "マンガ", "コミック")
INFO = ("著", "[著]", "ほか著", "編", "")


def norm(s):
    s = unicodedata.normalize("NFKC", s or "").casefold().translate(VAR)
    s = "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)
    return re.sub(r"[\s・=.\-ー〜~!！?？☆★♪,、。()（）]", "", s)


def split_raw(x):
    """「山本英夫 作」→(山本英夫, 作)。 役割語が無ければ (x, "")"""
    p = x.strip().rsplit(" ", 1)
    if len(p) == 2 and len(p[1]) <= 16 and not re.search(r"\d{4}", p[1]):
        return p[0].strip(), p[1].strip()
    return x.strip(), ""


def bucket(role):
    r = role.replace("・監修", "").replace("監修・", "")
    if r in INFO:
        return "info"
    if r == "原作" or r.startswith("原作") or r in ("作", "脚本", "シナリオ"):
        return "original"
    if r in ARTIST:
        return "artist"
    return "credit"


def main():
    con = sqlite3.connect(os.path.join(ROOT, ".cache", "db-v2.sqlite"))
    qn = collections.defaultdict(set)
    for q, n, alt in con.execute("select qid, name, alt_names from mangaka"):
        for a in [n] + re.split(r"[|,;/、]", alt or ""):
            if a and a.strip():
                qn[q].add(norm(a))
    ndl = {}
    for ln in open(NDL, encoding="utf-8"):
        r = json.loads(ln)
        if r["slug"] not in ndl or r.get("ndl_hit") or r.get("isbn"):
            ndl[r["slug"]] = r  # 後の行(取り直し)を優先
    res = collections.Counter()
    rows = []
    for a in csv.DictReader(open(AUD, encoding="utf-8"), delimiter="\t"):
        s, q = a["slug"], a["qid"]
        d = yaml.safe_load(open(os.path.join(ROOT, "data", "manga.v2", a["stem"] + ".yml"), encoding="utf-8")) or {}
        au = [x["name"] for x in (d.get("authors") or [])]
        oa = [x["name"] for x in (d.get("original_authors") or [])]
        cr = [x["name"] for x in (d.get("credits") or [])]
        page_all = {norm(x) for x in au + oa + cr}
        n = ndl.get(s) or {}
        if not n.get("ndl_hit"):
            v, add = "NO_NDL", []
        else:
            # ★NDL は複数著者を「A, B, C 著」と1行にまとめる(アンソロジー等)= 名前をカンマで割り役割を共有
            people = [(nm.strip(), r) for x in (n.get("creators_raw") or [])
                      for p0, r in [split_raw(x)] for nm in re.split(r",\s*|、", p0) if nm.strip()]
            if not people:
                people = [(c.split(",")[0] + "".join(c.split(",")[1:2]).strip(), "") for c in n.get("creators", [])]
            ndl_names = {norm(p) for p, _ in people}
            bad = [x for x in au + oa if norm(x) not in ndl_names]
            add = [(p, r, bucket(r)) for p, r in people if norm(p) not in page_all and bucket(r) != "info"]
            q_in = [(p, r) for p, r in people if norm(p) in qn.get(q, set())]
            if bad:
                v = "CONFLICT"
            elif not q_in:
                v = "QID_ONLY" if not add else "ADD"
            elif all(bucket(r) == "credit" for _, r in q_in) and all(b == "credit" for _, _, b in add):
                v = "OK_CREDIT"
            else:
                v = "ADD" if add else "QID_ONLY"
        res[v] += 1
        rows.append((v, s, a["title"], q, a["qid_name"], "|".join(au), "|".join(oa),
                     " / ".join(n.get("creators_raw") or []),
                     " / ".join(f"{p}→{b}({r})" for p, r, b in add)))
    print(dict(res))
    with open(OUT, "w", encoding="utf-8", newline="") as fo:
        w = csv.writer(fo, delimiter="\t")
        w.writerow(["verdict", "slug", "title", "qid", "qid_name", "authors", "original_authors", "ndl_creators", "proposal"])
        w.writerows(sorted(rows))
    print(f"→ {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Wikipedia発売日 掃引 STEP2 = ゲートを通った頁だけ override 行を生成する。

★ユーザ裁定(2026-09-04): 「全巻そろって通った頁だけ」= 頁内で基準を混ぜない。
  → 頁が採用されるのは、その頁の **ISBNを持つ全巻** が
     ①jawiki記事に載っており ②楽天ゲートに引っかからない 場合のみ。
     1巻でも「楽天が本番を支持」「三者バラバラ」「記事に無い」があれば **頁ごと見送り**。

判定(巻単位。実測は docs/production-diagnostics/wikipedia-date-sweep-estimate.md):
  SAME        wiki == 本番              → 変更なし(頁の資格は保つ)
  ADOPT_MONTH 月が違う & 楽天が wiki 支持 → 採用
  ADOPT_DAY   同月・日違い & 楽天が wiki 支持 → 採用
  ADOPT_GAIN  本番YYYY-MM & wikiに日 & 楽天は月まで(反証にならない) → 採用
  BLOCK_PROD  楽天が本番を支持           → ★頁ごと見送り
  BLOCK_SPLIT 三者バラバラ / 楽天に日付なしで判定不能 → ★頁ごと見送り
  NOT_IN_WIKI 本番の巻が記事に無い        → ★頁ごと見送り(基準が混ざるため)
  ALREADY_OVERRIDDEN 既にoverride行がある(過去の意図ある是正) → ★頁ごと見送り

出力:
  docs/production-diagnostics/wikipedia-date-sweep.tsv        全頁の判定(人が見る)
  .cache/wiki-date-override-new.jsonl                          追記候補の override 行
  --apply で data/seeds/release-date-override.jsonl へ追記 + 対象slugを
  .cache/wiki-date-slugs.txt へ書き出し(reflect --only 用)

usage: python scripts/_wiki-date-apply.py [--apply]
"""
import argparse, collections, io, json, os, re, sys
import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAND = os.path.join(ROOT, ".cache", "jawiki-title-hits.json")
WIKI = os.path.join(ROOT, ".cache", "wiki-sweep")
TSV = os.path.join(ROOT, "docs", "production-diagnostics", "wikipedia-date-sweep.tsv")
NEWJL = os.path.join(ROOT, ".cache", "wiki-date-override-new.jsonl")
OVR = os.path.join(ROOT, "data", "seeds", "release-date-override.jsonl")
SLUGS = os.path.join(ROOT, ".cache", "wiki-date-slugs.txt")

ISBN_RE = re.compile(r"(?:ISBN[ 　]?|\{\{ISBN2?\|)([0-9][0-9\- ]{8,20}[0-9X])")
DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(?:(\d{1,2})日)?")


def key(name):
    return re.sub(r"[^0-9A-Za-z぀-ヿ一-鿿]", "_", name)[:80]


def to13(raw):
    d = re.sub(r"[^0-9X]", "", raw.upper())
    if len(d) == 13:
        return d
    if len(d) != 10:
        return None
    core = "978" + d[:9]
    s = sum(int(c) * (1 if k % 2 == 0 else 3) for k, c in enumerate(core))
    return core + str((10 - s % 10) % 10)


def as_date(m):
    y, mo, dd = m.group(1), int(m.group(2)), m.group(3)
    return "%s-%02d-%02d" % (y, mo, int(dd)) if dd else "%s-%02d" % (y, mo)


def wiki_pairs(body):
    out = {}
    for ln in body.splitlines():
        mi = ISBN_RE.search(ln)
        if not mi:
            continue
        md = DATE_RE.search(ln)
        if not md:
            continue
        i13 = to13(mi.group(1))
        if i13:
            out[i13] = as_date(md)
    return out


def load_existing_override():
    """★過去に人/per-case作業が意図して置いた override は絶対に上書きしない。
    (実測: date-disorder 是正39巻を掃引が9-11年ずらして潰しかけた = 2026-09-04)"""
    ex = {}
    if os.path.exists(OVR):
        for line in io.open(OVR, encoding="utf-8"):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("isbn13") and d.get("date"):
                ex[d["isbn13"]] = d["date"]
    return ex


def load_rakuten():
    rkt = {}
    for f in ("rakuten-isbn.jsonl", "rakuten-isbn-delta.jsonl"):
        p = os.path.join(ROOT, ".cache", f)
        if not os.path.exists(p):
            continue
        for line in io.open(p, encoding="utf-8", errors="replace"):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            it = d.get("item") or d
            i = str(it.get("isbn") or "")
            sd = it.get("salesDate")
            if i and sd and i not in rkt:
                m = DATE_RE.search(sd)
                if m:
                    rkt[i] = as_date(m)
    return rkt


def judge(wiki, prod, rkt):
    """巻単位の判定 → (code, 採用日 or None)"""
    if wiki == prod:
        return "SAME", None
    if wiki[:7] != prod[:7]:
        if rkt and rkt[:7] == wiki[:7]:
            return "ADOPT_MONTH", wiki
        if rkt and rkt[:7] == prod[:7]:
            return "BLOCK_PROD", None
        return "BLOCK_SPLIT", None
    # 同月
    if len(prod) == 7 and len(wiki) == 10:
        if rkt and rkt == wiki:
            return "ADOPT_GAIN", wiki
        if rkt and len(rkt) == 10:
            return "BLOCK_SPLIT", None       # 楽天が別日を主張
        return "ADOPT_GAIN", wiki            # 楽天は月まで=反証にならない
    if len(prod) == 10 and len(wiki) == 7:
        # ★同月で本番の方が細かい = 日を落とすだけの情報損失。採らない
        # (実測 2026-09-04: これで144巻/50頁の粒度を落としかけた)
        return "SAME", None
    if rkt and rkt == wiki:
        return "ADOPT_DAY", wiki
    if rkt and rkt == prod:
        return "BLOCK_PROD", None
    return "BLOCK_SPLIT", None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    exist = load_existing_override()
    print("既存override ISBN:", len(exist), flush=True)
    rkt = load_rakuten()
    print("楽天日付索引:", len(rkt), flush=True)
    rows = json.load(io.open(CAND, encoding="utf-8"))
    print("候補頁:", len(rows), flush=True)

    stat = collections.Counter()
    vstat = collections.Counter()
    out_rows = []
    new_lines = []
    slugs = []

    for stem, ti, nvol, wname in rows:
        p = os.path.join(ROOT, "data", "manga.v2", stem + ".yml")
        fp = os.path.join(WIKI, key(wname) + ".txt")
        if not os.path.exists(p):
            stat["頁なし"] += 1
            continue
        if not os.path.exists(fp):
            stat["記事未取得"] += 1
            continue
        body = io.open(fp, encoding="utf-8", errors="replace").read()
        if body.startswith("__MISSING__") or len(body) < 200:
            stat["記事なし"] += 1
            continue
        try:
            d = yaml.safe_load(io.open(p, encoding="utf-8", errors="replace"))
        except Exception:
            stat["頁パース不可"] += 1
            continue
        authors = [x.get("name") for x in (d.get("authors") or []) if x.get("name")]
        if authors and not any(x in body for x in authors):
            stat["別作品の同名記事"] += 1
            continue
        wp = wiki_pairs(body)
        if not wp:
            stat["記事に巻別ISBN+日付なし"] += 1
            continue
        prod = {}
        for ed in (d.get("editions") or []):
            for v in (ed.get("volumes") or []):
                if v.get("isbn13") and v.get("release_date"):
                    prod[str(v["isbn13"])] = str(v["release_date"])
        if not prod:
            stat["本番にISBN付き巻なし"] += 1
            continue

        judged = {}
        for i, pr in prod.items():
            if i in exist:
                judged[i] = ("ALREADY_OVERRIDDEN", None)   # 既存是正を潰さない
            elif i not in wp:
                judged[i] = ("NOT_IN_WIKI", None)
            else:
                judged[i] = judge(wp[i], pr, rkt.get(i))
        codes = collections.Counter(c for c, _ in judged.values())
        adopt = {i: dt for i, (c, dt) in judged.items() if dt}
        blocked = sum(codes[k] for k in ("BLOCK_PROD", "BLOCK_SPLIT", "NOT_IN_WIKI", "ALREADY_OVERRIDDEN"))

        if blocked:
            verdict = "SKIP_PAGE"
            stat["見送り(全巻ゲート不成立)"] += 1
        elif not adopt:
            verdict = "NO_CHANGE"
            stat["変更不要(全巻一致)"] += 1
        else:
            verdict = "APPLY"
            stat["適用"] += 1
            slugs.append(stem)
            for i, dt in sorted(adopt.items()):
                new_lines.append(json.dumps({
                    "isbn13": i, "date": dt, "slug": stem,
                    "reason": "wikipedia-release-date(sweep, rakuten-gated)",
                    "wiki": wname, "at": "2026-09-04"}, ensure_ascii=False))
        for c in codes:
            vstat[c] += codes[c]
        out_rows.append((verdict, stem, ti, wname, len(prod), len(wp), len(adopt),
                         codes["SAME"], codes["ADOPT_MONTH"], codes["ADOPT_DAY"],
                         codes["ADOPT_GAIN"], codes["BLOCK_PROD"], codes["BLOCK_SPLIT"],
                         codes["NOT_IN_WIKI"], codes["ALREADY_OVERRIDDEN"]))

    order = {"APPLY": 0, "SKIP_PAGE": 1, "NO_CHANGE": 2}
    out_rows.sort(key=lambda r: (order.get(r[0], 9), -r[6]))
    with io.open(TSV, "w", encoding="utf-8", newline="") as f:
        f.write("verdict\tslug\ttitle\twiki_article\t本番巻\twiki対\t採用巻\t"
                "SAME\tADOPT_MONTH\tADOPT_DAY\tADOPT_GAIN\tBLOCK_PROD\tBLOCK_SPLIT\t"
                "NOT_IN_WIKI\tALREADY_OVERRIDDEN\n")
        for r in out_rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    io.open(NEWJL, "w", encoding="utf-8").write("\n".join(new_lines) + ("\n" if new_lines else ""))

    print("\n=== 頁判定 ===")
    for k, v in stat.most_common():
        print("  %-24s %6d" % (k, v))
    print("\n=== 巻判定(適用/見送り頁すべて込み) ===")
    for k, v in vstat.most_common():
        print("  %-14s %7d" % (k, v))
    print("\n適用頁 %d / 書き換え巻 %d" % (len(slugs), len(new_lines)))
    print("一覧 ->", os.path.relpath(TSV, ROOT))
    print("override候補 ->", os.path.relpath(NEWJL, ROOT))

    if a.apply and new_lines:
        with io.open(OVR, "a", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")
        io.open(SLUGS, "w", encoding="utf-8").write(",".join(sorted(set(slugs))))
        print("\n[APPLY] release-date-override.jsonl に %d 行追記 / 対象slug %d -> %s"
              % (len(new_lines), len(set(slugs)), os.path.relpath(SLUGS, ROOT)))


main()

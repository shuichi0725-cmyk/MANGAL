#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kindle版ASIN 収穫(Creators API・作者名で一括)。2026-11-21 試行版。

流れ: 作者名で KindleStore を searchItems(1回10件・1検索最大100件=itemPage<=10)
      → 自サイトのその作者の頁の巻(isbn13あり)と 題+巻番号+発売日 で照合 → 候補を書く。
      ★seed(data/seeds/kindle-asin.jsonl)へは書かない(apply は別・ユーザGO後)。

使い方:
  python scripts/_kindle-asin-harvest.py trial [--n 10] [--seed 1121]   # 作者を50音・年代で散らして選び試行
  python scripts/_kindle-asin-harvest.py author "<作者名>"              # 1人だけ
出力: .cache/kindle-asin/<run>/ items.jsonl(取れたKindle版) / match.tsv(照合) / report.txt
鍵: .env の AMAZON_CREATORS_CLIENT_ID / AMAZON_CREATORS_SECRET。 1TPS(1.1秒間隔)・初期8,640回/日。
"""
import os, re, sys, json, time, random, argparse, unicodedata, datetime, urllib.request, urllib.error
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache", "kindle-asin")
os.makedirs(CACHE, exist_ok=True)
CALLS = Counter()


# ---------------- API ----------------
def _env():
    kv = {}
    for ln in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
        if "=" in ln:
            k, v = ln.strip().split("=", 1)
            kv[k] = v.strip().strip('"').strip("'")
    return kv


def _post(url, body, h):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **h})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


_TOK = os.path.join(CACHE, "token.json")


def _token():
    try:
        d = json.load(open(_TOK))
        if d["exp"] > time.time() + 60:
            return d["t"]
    except Exception:
        pass
    kv = _env()
    st, t = _post("https://api.amazon.co.jp/auth/o2/token",
                  {"grant_type": "client_credentials", "client_id": kv["AMAZON_CREATORS_CLIENT_ID"],
                   "client_secret": kv["AMAZON_CREATORS_SECRET"], "scope": "creatorsapi::default"}, {})
    if st != 200:
        raise SystemExit(f"token HTTP {st}: {t[:200]}")
    d = json.loads(t)
    json.dump({"t": d["access_token"], "exp": time.time() + int(d.get("expires_in", 3600))}, open(_TOK, "w"))
    return d["access_token"]


_last = [0.0]


def call(op, body):
    w = 1.1 - (time.time() - _last[0])
    if w > 0:
        time.sleep(w)
    body = {"marketplace": "www.amazon.co.jp", "partnerTag": "mangal08-22", **body}
    for k in range(4):
        _last[0] = time.time()
        st, t = _post(f"https://creatorsapi.amazon/catalog/v1/{op}", body,
                      {"Authorization": "Bearer " + _token(), "x-marketplace": "www.amazon.co.jp"})
        CALLS[op] += 1
        if st == 429 and k < 3:
            time.sleep(5 * (k + 1)); continue
        if st == 403 and "AssociateNotEligible" in t:
            raise SystemExit("403 AssociateNotEligible = 直近30日の売上条件を外れた(API停止)")
        try:
            return st, json.loads(t)
        except Exception:
            return st, {"raw": t[:300]}
    return st, {}


RES = ["itemInfo.title", "itemInfo.byLineInfo", "itemInfo.contentInfo", "itemInfo.classifications"]


def kindle_by_author(name):
    """→ (items, total, capped)。 1検索最大100件。"""
    items, total = [], None
    for page in range(1, 11):
        st, d = call("searchItems", {"author": name, "searchIndex": "KindleStore", "itemCount": 10,
                                     "itemPage": page, "resources": RES})
        if st != 200:
            print(f"   searchItems HTTP {st} {str(d)[:160]}")
            break
        sr = d.get("searchResult") or {}
        total = sr.get("totalResultCount", total)
        its = sr.get("items") or []
        for it in its:
            ii = it.get("itemInfo") or {}
            items.append({
                "asin": it["asin"],
                "title": (ii.get("title") or {}).get("displayValue", ""),
                "date": ((ii.get("contentInfo") or {}).get("publicationDate") or {}).get("displayValue", "")[:10],
                "binding": ((ii.get("classifications") or {}).get("binding") or {}).get("displayValue", ""),
                "authors": [c.get("name") for c in ((ii.get("byLineInfo") or {}).get("contributors") or [])],
            })
        if len(its) < 10:
            break
    return items, total, (total or 0) > len(items)


# ---------------- 自サイト ----------------
_PAT_VOL = re.compile(r"- number: (\S+)\n(?:\s+\w+:.*\n)*?\s+isbn13: '?(\d{13})'?\n(?:\s+(?!- )\w+:.*\n)*?\s+release_date: '?([\d-]*)'?")


def load_pages():
    """作者名 → [{slug,title,vols:[(number,isbn13,date)]}]"""
    by = defaultdict(list)
    d = os.path.join(ROOT, "data", "manga.v2")
    for f in os.listdir(d):
        s = open(os.path.join(d, f), encoding="utf-8").read()
        m = re.search(r"^title: (.*)$", s, re.M)
        yr = re.search(r"^year_started: (\d+)", s, re.M)
        names = re.findall(r"^- name: (.*)$", s.split("\noriginal_authors:")[0], re.M)
        vols = []
        for num, isbn, dt in _PAT_VOL.findall(s):
            try:
                vols.append((float(num), isbn, dt))
            except ValueError:
                pass
        if not vols or not m:
            continue
        rec = {"slug": f[:-4], "title": m.group(1).strip().strip("'\""), "year": int(yr.group(1)) if yr else None,
               "kana": (re.search(r"^title_kana: (.*)$", s, re.M) or [None, ""])[1], "vols": vols}
        for n in names:
            by[n.strip().strip("'\"")].append(rec)
    return by


# ---------------- 照合 ----------------
def norm(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    return re.sub(r"[\s・:：!！?？、。,.\-‐―ー~〜'\"「」『』【】\[\]()（）]", "", s)


_LABEL = re.compile(r"\s*[\(（][^()（）]*(コミックス|comics|文庫|digital|ＤＩＧＩＴＡＬ|ブックス|books|レーベル|シリーズ)[^()（）]*[\)）]\s*$", re.I)
_BAD = re.compile(r"分冊|単話|話売り|連載版|第\d+話|特装|限定版|試し読み|無料|お試し|合本|セット|画集|ファンブック|公式ガイド|小説|ノベル|ベストセレクション|傑作選|傑作集|総集編|名作選|アンソロジー", re.I)


def vol_of(t):
    """Kindle題 → (本体題, 巻番号 or None)"""
    t = unicodedata.normalize("NFKC", t)
    t = _LABEL.sub("", t).strip()
    for p in (r"^(.*?)[\s　]*[\(（](\d+)[\)）]\s*$", r"^(.*?)[\s　]*第?(\d+)巻?\s*$", r"^(.*?)\s*(\d+)\s*[\(（]", r"^(.*?\D)(\d+)$"):
        m = re.match(p, t)
        if m:
            return m.group(1).strip(), int(m.group(2))
    return t, None


def days(a, b):
    try:
        da = datetime.date.fromisoformat(a[:10]) if len(a) >= 10 else datetime.date.fromisoformat(a[:7] + "-15")
        db = datetime.date.fromisoformat(b[:10]) if len(b) >= 10 else datetime.date.fromisoformat(b[:7] + "-15")
        return abs((da - db).days)
    except Exception:
        return None


def match_author(pages, items):
    """→ rows(巻ごと)。 grade = A(題+巻+日付±62日) / B(題+巻・日付ズレ/欠け) / -(なし)。"""
    kin = []
    for it in items:
        if it["binding"] and "Kindle" not in it["binding"]:
            continue
        if _BAD.search(it["title"]):
            continue
        base, n = vol_of(it["title"])
        kin.append({**it, "base": norm(base), "n": n, "color": "カラー" in it["title"]})
    rows = []
    for pg in pages:
        nt = norm(pg["title"])
        single = len(pg["vols"]) == 1
        for num, isbn, dt in pg["vols"]:
            cands = []
            for k in kin:
                # ★Kindle題 ⊇ 自サイト題 のみ(「まんが版 〜」の前置きは許す)。 逆向き(自サイト題がKindle題を含む)は
                #   「〜対マイコン電児ラン」に「マイコン電児ラン(1)」が当たる誤りになる(2026-11-21 試行で実踏)。
                if not nt or nt not in k["base"]:
                    continue
                if k["n"] is None and k["base"] != nt:  # 巻番号なしのKindle題は題が完全一致の時だけ
                    continue
                if len(k["base"]) > len(nt) * 2.2 + 6:  # 題が長すぎる=別作品(外伝・関連本)の疑い
                    continue
                if k["n"] is not None and k["n"] != int(num):
                    continue
                if k["n"] is None and not single and int(num) != 1:
                    continue
                dd = days(dt, k["date"]) if dt and k["date"] else None
                cands.append((0 if (dd is not None and dd <= 62) else 1, k["color"], dd if dd is not None else 99999, k))
            cands.sort(key=lambda x: (x[0], x[1], x[2]))
            if cands:
                g = "A" if cands[0][0] == 0 else "B"
                k = cands[0][3]
                amb = len([c for c in cands if c[0] == cands[0][0] and c[1] == cands[0][1]]) > 1
                rows.append((pg["slug"], pg["title"], int(num), isbn, dt, g + ("?" if amb else ""), k["asin"], k["date"],
                             k["title"], cands[0][2]))
            else:
                rows.append((pg["slug"], pg["title"], int(num), isbn, dt, "-", "", "", "", ""))
    return rows


# ---------------- 実行 ----------------
ROW = "アカサタナハマヤラワ"


def pick_authors(by, n, seed):
    """50音の行 × 年代が偏らないように(人気順にしない)。 巻3〜150冊の作者から。"""
    rnd = random.Random(seed)
    pool = defaultdict(list)
    for a, pgs in by.items():
        tot = sum(len(p["vols"]) for p in pgs)
        if not (3 <= tot <= 150) or len(a) < 2:
            continue
        yrs = [p["year"] for p in pgs if p["year"]]
        if not yrs:
            continue
        dec = (min(yrs) // 10) * 10
        pool[dec].append(a)
    decs = sorted(d for d in pool if d >= 1960)
    out = []
    i = 0
    while len(out) < n and i < 200:
        d = decs[i % len(decs)]
        c = rnd.choice(pool[d])
        if c not in out:
            out.append(c)
        i += 1
    return out


def run(authors, by, tag):
    od = os.path.join(CACHE, tag)
    os.makedirs(od, exist_ok=True)
    fi = open(os.path.join(od, "items.jsonl"), "w", encoding="utf-8")
    fm = open(os.path.join(od, "match.tsv"), "w", encoding="utf-8")
    fm.write("author\tslug\ttitle\tnumber\tisbn13\tour_date\tgrade\tkindle_asin\tkindle_date\tkindle_title\tdays\n")
    rep = []
    tot = Counter()
    for a in authors:
        c0 = sum(CALLS.values())
        items, total, capped = kindle_by_author(a)
        for it in items:
            fi.write(json.dumps({"author_q": a, **it}, ensure_ascii=False) + "\n")
        rows = match_author(by.get(a, []), items)
        for r in rows:
            fm.write(a + "\t" + "\t".join(str(x) for x in r) + "\n")
        g = Counter(r[5][0] for r in rows)
        calls = sum(CALLS.values()) - c0
        line = (f"{a}: 呼出{calls} / Kindle {len(items)}件(総{total}{'・100件の壁' if capped else ''}) / "
                f"自サイト {len(by.get(a, []))}頁 {len(rows)}巻 → A {g['A']} / B {g['B']} / なし {g['-']}")
        print(line, flush=True)
        rep.append(line)
        tot.update({"calls": calls, "items": len(items), "vols": len(rows), "A": g["A"], "B": g["B"], "none": g["-"]})
    s = (f"\n計: 呼出{tot['calls']} / Kindle {tot['items']}件 / 自サイト{tot['vols']}巻 → "
         f"A {tot['A']} ({tot['A'] / max(1, tot['vols']):.0%}) / B {tot['B']} / なし {tot['none']}")
    print(s)
    open(os.path.join(od, "report.txt"), "w", encoding="utf-8").write("\n".join(rep) + s + "\n")
    print("出力:", od)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("trial"); t.add_argument("--n", type=int, default=10); t.add_argument("--seed", type=int, default=1121)
    o = sub.add_parser("author"); o.add_argument("name")
    a = ap.parse_args()
    print("自サイトの頁を読み込み中…", flush=True)
    by = load_pages()
    if a.cmd == "trial":
        au = pick_authors(by, a.n, a.seed)
        print("選んだ作者:", " / ".join(au))
        run(au, by, f"trial-{time.strftime('%Y%m%d-%H%M')}")
    else:
        run([a.name], by, f"author-{time.strftime('%Y%m%d-%H%M')}")


if __name__ == "__main__":
    main()

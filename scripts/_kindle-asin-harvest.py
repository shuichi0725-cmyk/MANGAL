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
鍵: .env の AMAZON_CREATORS_CLIENT_ID / AMAZON_CREATORS_SECRET。 ★安全側: 2秒間隔・1日8,000回(KINDLE_ASIN_BUDGET)・429で即停止。 台帳 .cache/kindle-asin/calls.log
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
# ★2026-11-21 ユーザ「一番まずいのはやりすぎて使えなくなること」= 安全側に倒す3点:
#   ①間隔 2.0秒(公表上限 1TPS の半分) ②回数の台帳(直近24時間・プロセスをまたいで数える)で 1日の予算を超えたら止める
#     (2026-11-21 ユーザ裁定 8,000回=公表の初期上限 8,640/日の手前。 30日目以降は売上連動で下がり得る→429即停止で守る)
#   ③429 が1回でも出たら取り直さずに即停止(その日は終わり)・非200が5回続いたら停止。
PACE = 2.0
DAILY_BUDGET = int(os.environ.get("KINDLE_ASIN_BUDGET", "8000"))
_LEDGER = os.path.join(CACHE, "calls.log")  # 1行1呼び出し: epoch秒 op status
_bad = [0]


def _used_24h():
    now = time.time()
    try:
        return sum(1 for ln in open(_LEDGER, encoding="utf-8") if ln.strip() and now - float(ln.split()[0]) < 86400)
    except FileNotFoundError:
        return 0


def call(op, body):
    used = _used_24h()
    if used >= DAILY_BUDGET:
        raise SystemExit(f"1日の予算 {DAILY_BUDGET} 回に達した(直近24時間 {used} 回)= 今日はここまで。続きは明日")
    w = PACE - (time.time() - _last[0])
    if w > 0:
        time.sleep(w)
    body = {"marketplace": "www.amazon.co.jp", "partnerTag": "mangal08-22", **body}
    _last[0] = time.time()
    try:
        st, t = _post(f"https://creatorsapi.amazon/catalog/v1/{op}", body,
                      {"Authorization": "Bearer " + _token(), "x-marketplace": "www.amazon.co.jp"})
    except Exception as e:  # 通信エラーも1回と数える
        st, t = 0, f"{type(e).__name__}"
    CALLS[op] += 1
    with open(_LEDGER, "a", encoding="utf-8") as f:
        f.write(f"{time.time():.0f} {op} {st}\n")
    if st == 429:
        raise SystemExit(f"429(回数超過 or 停止)= 取り直さずに即停止。 本文: {t[:200]}")
    if st == 403 and "AssociateNotEligible" in t:
        raise SystemExit("403 AssociateNotEligible = 直近30日の売上条件を外れた(API停止)")
    _bad[0] = 0 if st == 200 else _bad[0] + 1
    if _bad[0] >= 5:
        raise SystemExit(f"200 以外が5回続いた(最後 HTTP {st})= 停止して調べる。 {t[:200]}")
    try:
        return st, json.loads(t)
    except Exception:
        return st, {"raw": t[:300]}


RES = ["itemInfo.title", "itemInfo.byLineInfo", "itemInfo.contentInfo", "itemInfo.classifications"]
# ★2026-11-21 ユーザ「一緒に取れる情報を捨てて取り直すことがあった」→ 取得前に全項目を調査して、価格・在庫(offersV2=
#   静的表示禁止・規約上1時間)以外は全部取る。 成人判定(productInfo.isAdultProduct)・ジャンル売り場(browseNodes)・
#   役割つき著者(byLineInfo)・頁数/紙の発売日/電子の配信日(contentInfo/productInfo)・書影URL(images=手元だけ・公開しない)。
FULL = ["browseNodeInfo.browseNodes", "browseNodeInfo.browseNodes.ancestor", "browseNodeInfo.browseNodes.salesRank",
        "browseNodeInfo.websiteSalesRank", "images.primary.large", "images.variants.large",
        "itemInfo.byLineInfo", "itemInfo.classifications", "itemInfo.contentInfo", "itemInfo.contentRating",
        "itemInfo.externalIds", "itemInfo.features", "itemInfo.manufactureInfo", "itemInfo.productInfo",
        "itemInfo.technicalInfo", "itemInfo.title", "itemInfo.tradeInInfo", "parentASIN"]
RAW_DIR = os.path.join(CACHE, "raw")
os.makedirs(RAW_DIR, exist_ok=True)
_CAMPAIGN = re.compile(r"キャンペーン|ポイント|クーポン|セール|まとめ買い|まとめ|Custom Stores|Experiment|Mystery|Offer|"
                       r"CompMatch|スタンプ|チャレンジ|円以下|_delete|\d{4}年|manga \d", re.I)


def _chain(bn):
    out = []
    while bn:
        out.append(bn.get("displayName", ""))
        bn = bn.get("ancestor")
    return out


def strip_item(it):
    """生の応答から販促用の売り場分類(1件80KB の大半)だけ落とす。 他は全部残す。"""
    bi = it.get("browseNodeInfo") or {}
    if not bi:
        return it
    keep = [b for b in bi.get("browseNodes") or [] if not any(_CAMPAIGN.search(x) for x in _chain(b))]
    return {**it, "browseNodeInfo": {**bi, "browseNodes": keep}}


def save_raw(kind, req, st, d, slug=None):
    """生の応答を .cache/kindle-asin/raw/YYYYMM.jsonl.gz へ追記(取り直し防止の一次保存)。"""
    import gzip
    d2 = d
    if isinstance(d, dict):
        for key in ("searchResult", "itemsResult"):
            if isinstance(d.get(key), dict) and d[key].get("items"):
                d2 = {**d, key: {**d[key], "items": [strip_item(x) for x in d[key]["items"]]}}
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind, "slug": slug, "req": req, "status": st, "resp": d2}
    with gzip.open(os.path.join(RAW_DIR, time.strftime("%Y%m") + ".jsonl.gz"), "at", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


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
        if not f.endswith(".yml"):
            continue
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


# ---------------- 頁モード(題名+第1作者で Kindle 検索 + 紙ISBNを getItems) ----------------
def i10(s):
    s = str(s)
    if len(s) != 13 or not s.startswith("978"):
        return None
    b = s[3:12]
    c = (11 - sum((10 - i) * int(b[i]) for i in range(9)) % 11) % 11
    return b + ("X" if c == 10 else str(c))


def _item_brief(it):
    ii = it.get("itemInfo") or {}
    return {"asin": it["asin"], "title": (ii.get("title") or {}).get("displayValue", ""),
            "date": ((ii.get("contentInfo") or {}).get("publicationDate") or {}).get("displayValue", "")[:10],
            "binding": ((ii.get("classifications") or {}).get("binding") or {}).get("displayValue", ""),
            "authors": [c.get("name") for c in ((ii.get("byLineInfo") or {}).get("contributors") or [])]}


def harvest_page(pg, author):
    """→ (kindle_items, paper_found{isbn13:asin}, paper_invalid[isbn13], calls)。 応答は全部 save_raw。"""
    c0 = sum(CALLS.values())
    items = []
    for page in range(1, 11):
        req = {"title": pg["title"], "author": author, "searchIndex": "KindleStore", "itemCount": 10,
               "itemPage": page, "resources": FULL}
        st, d = call("searchItems", req)
        save_raw("kindle-search", req, st, d, pg["slug"])
        if st != 200:
            break
        its = (d.get("searchResult") or {}).get("items") or []
        items += [_item_brief(x) for x in its]
        if len(its) < 10:
            break
    found, invalid = {}, []
    ids = {}
    for _, isbn, _ in pg["vols"]:
        k = i10(isbn)
        if k:
            ids[k] = isbn
    keys = list(ids)
    for j in range(0, len(keys), 10):
        req = {"itemIds": keys[j:j + 10], "itemIdType": "ASIN", "resources": FULL}
        st, d = call("getItems", req)
        save_raw("paper-get", req, st, d, pg["slug"])
        if st != 200:
            continue
        for it in (d.get("itemsResult") or {}).get("items") or []:
            if it["asin"] in ids:
                found[ids[it["asin"]]] = it["asin"]
        for e in d.get("errors") or []:
            m = re.search(r"ItemIds (\S+) provided", e.get("message", ""))
            if m and m.group(1) in ids:
                invalid.append(ids[m.group(1)])
    return items, found, invalid, sum(CALLS.values()) - c0


def first_author(slug):
    s = open(os.path.join(ROOT, "data", "manga.v2", slug + ".yml"), encoding="utf-8").read()
    head = s.split("\noriginal_authors:")[0]
    ms = re.findall(r"^- name: (.*)\n\s+role: (\S+)", head, re.M)
    for n, r in ms:  # 作画・作画兼作者を優先(原作者名だと Kindle 側の著者表記とずれることがある)
        if r in ("writer_artist", "artist"):
            return n.strip().strip("'\"")
    return ms[0][0].strip().strip("'\"") if ms else ""


def run_pages(authors, by, tag, max_pages):
    od = os.path.join(CACHE, tag)
    os.makedirs(od, exist_ok=True)
    fm = open(os.path.join(od, "match.tsv"), "w", encoding="utf-8")
    fm.write("author\tslug\ttitle\tnumber\tisbn13\tour_date\tgrade\tkindle_asin\tkindle_date\tkindle_title\tdays\tpaper\n")
    seen, rep, tot = set(), [], Counter()
    pages = []
    for a in authors:
        for pg in by.get(a, []):
            if pg["slug"] in seen or first_author(pg["slug"]) != a:
                continue
            seen.add(pg["slug"])
            pages.append((a, pg))
    pages = pages[:max_pages]
    print(f"対象 {len(pages)}頁 / {sum(len(p['vols']) for _, p in pages)}巻", flush=True)
    for a, pg in pages:
        items, found, invalid, calls = harvest_page(pg, a)
        rows = match_author([pg], items)
        g = Counter(r[5][0] for r in rows)
        for r in rows:
            pap = "有" if r[3] in found else ("無" if r[3] in invalid else "?")
            fm.write(a + "\t" + "\t".join(str(x) for x in r) + "\t" + pap + "\n")
        line = (f"{pg['title'][:24]}({a}) 呼出{calls} Kindle{len(items)} / {len(rows)}巻 → A{g['A']} B{g['B']} なし{g['-']}"
                f" / 紙 有{len(found)} 無{len(invalid)}")
        print(" ", line, flush=True)
        rep.append(line)
        tot.update({"calls": calls, "vols": len(rows), "A": g["A"], "B": g["B"], "none": g["-"],
                    "paper_ok": len(found), "paper_ng": len(invalid), "kitems": len(items)})
    s = (f"\n計: {len(pages)}頁 呼出{tot['calls']} / Kindle {tot['kitems']}件 / 自サイト{tot['vols']}巻 → "
         f"A {tot['A']} ({tot['A'] / max(1, tot['vols']):.0%}) / B {tot['B']} / なし {tot['none']}"
         f" / 紙の商品頁 有{tot['paper_ok']} 無{tot['paper_ng']}")
    print(s)
    open(os.path.join(od, "report.txt"), "w", encoding="utf-8").write("\n".join(rep) + s + "\n")
    print("出力:", od, "/ 生の応答:", RAW_DIR)


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
    pp = sub.add_parser("pages"); pp.add_argument("--n", type=int, default=10); pp.add_argument("--seed", type=int, default=2211)
    pp.add_argument("--max-pages", type=int, default=60)
    a = ap.parse_args()
    print("自サイトの頁を読み込み中…", flush=True)
    by = load_pages()
    if a.cmd == "trial":
        au = pick_authors(by, a.n, a.seed)
        print("選んだ作者:", " / ".join(au))
        run(au, by, f"trial-{time.strftime('%Y%m%d-%H%M')}")
    elif a.cmd == "pages":
        au = pick_authors(by, a.n, a.seed)
        print("選んだ作者:", " / ".join(au))
        run_pages(au, by, f"pages-{time.strftime('%Y%m%d-%H%M')}", a.max_pages)
    else:
        run([a.name], by, f"author-{time.strftime('%Y%m%d-%H%M')}")


if __name__ == "__main__":
    main()

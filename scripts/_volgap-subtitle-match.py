# -*- coding: utf-8 -*-
"""【巻抜け充填・副題を許す照合 2026-11-01】巻抜けターゲット × 楽天(ローカル種 + 9月の live 収穫)を、副題を許して照合する。
旧照合は「巻トークンを剥がした残りの題 == 頁題」を要求したため、楽天の題に副題が付く本
(世界最強の魔女、始めました 〜私だけ『攻略サイト』を…〜(6) / INOZ -55歳から…-(2) / 熱中!コボちゃん10 おいしいお使い編 /
 ピットスポルム 二葉 / 邦キチ!映子さん Season14)を全部捨てていた。
規則: 楽天の題(NFKC・記号抜き)が頁題で始まり、残りから巻番号が1つだけ読める。
ゲート: 著者が重なる / 版元のISBN記号が前後巻と同じ(違えば版元名一致を要求) / ISBN連番 / 発売日が前後巻の間 /
       本番のどの頁にも出ていない / セット・アンソロジー・小説・特装/限定版を除く / 1欠番1候補。"""
import csv, json, os, re, sys, unicodedata
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import yaml
import _rakuten_match_lib as R

P = "docs/production-diagnostics/"
KN = {c: i for i, c in enumerate("〇一二三四五六七八九")}


def kint(s):
    if s.isdigit():
        return int(s)
    if "十" in s:
        a, _, b = s.partition("十")
        if (a and a not in KN) or (b and b not in KN):
            return None
        return (KN[a] if a else 1) * 10 + (KN[b] if b else 0)
    return KN.get(s) if len(s) == 1 else None


def nk(s):
    return R.norm(R.clean_title(s))


EXCL = re.compile(r"セット|全巻|アンソロジー|小説|ノベル|画集|ファンブック|ガイドブック|特装|限定|同梱|BOX|ボックス|カレンダー|ドラマCD|ムック|総集編|公式|分冊")
VOLRE = [
    re.compile(r"^(?:season|vol|第)?(\d{1,3})(?:巻|集|話|葉)?(?!\d)", re.I),        # 先頭の数字(副題の前)
    re.compile(r"(?:season|vol|第)(\d{1,3})(?:巻|集|葉)?(?!\d)", re.I),
    re.compile(r"(\d{1,3})(?:巻|集)(?!\d)"),
    re.compile(r"([一二三四五六七八九十]{1,3})(?:葉|巻|集)"),
    re.compile(r"(\d{1,3})(?:完)?$"),                                                   # 末尾の数字
]


def vol_of(rest_raw):
    """頁題を取った残り(NFKC・記号は残す)から巻番号を読む。複数読めて食い違えば None。"""
    t = R.nfkc(rest_raw).lower()
    t = re.sub(r"[\s　]+", "", t)
    # 副題の括弧(〜…〜 / -…- / 【…】)の中の数字は巻でないことが多い → 括弧を外した版と両方見る
    nosub = re.sub(r"(〜[^〜]*〜|~[^~]*~|【[^】]*】|-[^-]*-|―[^―]*―)", "", t)
    found = set()
    for s in (nosub, t):
        s2 = re.sub(r"[()（）\[\]「」『』:：!！?？.,、。・]", "", s)
        for rx in VOLRE:
            m = rx.search(s2)
            if m:
                v = kint(m.group(1))
                if v:
                    found.add(v)
                break
        if found:
            break
    return found.pop() if len(found) == 1 else None


def anorm(s):
    return re.sub(r"[\s　・,、/／()（）]", "", R.nfkc(s)).lower()


# --- ターゲット ---
tg = list(csv.DictReader(open(P + "volgap-fill-targets.tsv", encoding="utf-8"), delimiter="\t"))
pages = {}
for r in tg:
    s = r["stem"]
    if s in pages:
        continue
    d = yaml.safe_load(open(f"data/manga.v2/{s}.yml", encoding="utf-8"))
    titles = {nk(d.get("title"))}
    for k in ("title_display", "title_romaji"):
        pass
    auth = set()
    for key in ("authors", "original_authors"):
        for a in d.get(key) or []:
            n = anorm(a.get("name"))
            if n and n != "unknown" and n != "(unknown)":
                auth.add(n)
    pages[s] = {"title": d.get("title"), "nt": nk(d.get("title")), "auth": auth}
by_prefix = defaultdict(list)
for s, pg in pages.items():
    if len(pg["nt"]) >= 2:
        by_prefix[pg["nt"][:2]].append(s)

prod = set(json.load(open(".cache/isbn-page-index.json", encoding="utf-8")).keys())


def consider(isbn, title, author, pub, sales, src, hits):
    raw = R.clean_title(title)
    n = R.norm(raw)
    if len(n) < 2 or EXCL.search(raw):
        return
    for s in by_prefix.get(n[:2], []):
        pt = pages[s]["nt"]
        if not n.startswith(pt) or n == pt and False:
            continue
        # 残り(記号付き)を取り出す: raw を先頭から頁題ぶん食べる
        i = j = 0
        while i < len(raw) and j < len(pt):
            c = R.norm(raw[i])
            if c and c == pt[j:j + len(c)]:
                j += len(c)
            i += 1
        rest = raw[i:]
        v = vol_of(rest) if rest.strip() else None
        if v is None and not rest.strip():
            v = 1  # 題だけ = 1巻扱いの候補(先頭欠け用)
        if v is None:
            continue
        hits[(s, v)].append({"isbn": isbn, "title": raw, "author": author, "pub": pub, "date": R.parse_salesdate(sales), "src": src})


hits = defaultdict(list)
n = 0
for isbn, it in R.iter_items((R.DELTA, R.OLD)):
    n += 1
    consider(isbn, it.get("title", ""), it.get("author", ""), it.get("publisherName", ""), it.get("salesDate", ""), "local", hits)
print(f"楽天ローカル {n:,} 件 走査", flush=True)
for f, key in ((".cache/volgap-live-rakuten.jsonl", "items"), (".cache/volgap-lead-live.jsonl", "rakuten")):
    for l in open(f, encoding="utf-8"):
        j = json.loads(l)
        for it in j.get(key) or []:
            ib = re.sub(r"\D", "", str(it.get("isbn") or it.get("isbn13") or ""))
            if len(ib) == 13:
                consider(ib, it.get("title", ""), it.get("author", ""), it.get("publisherName", ""), it.get("salesDate", ""), "live", hits)

out = []
for r in tg:
    s, num = r["stem"], int(r["number"])
    cands = {}
    for c in hits.get((s, num), []):
        cands.setdefault(c["isbn"], c)
    res = []
    for ib, c in cands.items():
        why = []
        if ib in prod:
            why.append("本番に在る")
        au = {anorm(x) for x in re.split(r"[/／,、]", c["author"] or "") if anorm(x)}
        pa = pages[s]["auth"]
        if pa and au and not any(a in b or b in a for a in au for b in pa):
            why.append("著者違い")
        regs = {x[3:9] for x in (r["prev_isbn"], r["next_isbn"]) if x}
        if regs and ib[3:9] not in regs:
            pn, ep = anorm(c["pub"]), anorm(r["publisher"])
            if not (pn and ep and (pn in ep or ep in pn)):
                why.append("版元違い")
        if r["prev_isbn"] and r["prev_isbn"][3:9] == ib[3:9] and not r["prev_isbn"] < ib:
            why.append("ISBN連番の外")
        if r["next_isbn"] and r["next_isbn"][3:9] == ib[3:9] and not ib < r["next_isbn"]:
            why.append("ISBN連番の外")
        cd = R.date_str(c["date"]) if c["date"] else ""
        if cd:
            if r["prev_date"] and cd[:7] < r["prev_date"][:7]:
                why.append("前巻より前")
            if r["next_date"] and cd[:7] > r["next_date"][:7]:
                why.append("次巻より後")
        res.append((why, ib, c, cd))
    good = [x for x in res if not x[0]]
    if len(good) == 1:
        dec = "APPLY"
    elif len(good) > 1:
        dec = "HOLD(候補複数)"
    elif res:
        dec = "REJECT:" + ",".join(sorted({w for x in res for w in x[0]}))
    else:
        dec = "NOHIT"
    best = good[0] if len(good) == 1 else (res[0] if res else None)
    out.append({"decision": dec, "stem": s, "title": pages[s]["title"], "ei": r["ei"], "etype": r["etype"], "number": num,
                "kind": r["kind"], "isbn": best[1] if best else "", "date": best[3] if best else "",
                "rak_title": best[2]["title"] if best else "", "rak_author": best[2]["author"] if best else "",
                "rak_pub": best[2]["pub"] if best else "", "src": best[2]["src"] if best else "",
                "prev": f'{r["prev_num"]}:{r["prev_isbn"]}:{r["prev_date"]}', "next": f'{r["next_num"]}:{r["next_isbn"]}:{r["next_date"]}',
                "route": r["route"]})
with open(P + "volgap-subtitle-match.tsv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0]), delimiter="\t")
    w.writeheader()
    w.writerows(out)
from collections import Counter
c = Counter(o["decision"].split(":")[0] for o in out)
print(dict(c))
ap = [o for o in out if o["decision"] == "APPLY"]
print(f"APPLY {len(ap)} 巻 / {len({o['stem'] for o in ap})} 頁")

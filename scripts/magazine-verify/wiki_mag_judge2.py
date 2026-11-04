"""候補頁 × Wikipedia Infobox(漫画) × MADB × 楽天説明 × 今の値 の裁定表(読むだけ)。
欄の選び方: 欄の題(タイトル=、 無ければ記事名)が頁の題と合う + 作画者(作者/作画/漫画)が合う欄を優先、 原作者だけ合う欄は次点。"""
import json, sys, os, re, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wiki_mag_lib import *
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
L = os.path.join(ROOT, ".cache/magazine-lists")
rows = json.load(open(f"{L}/madb-decision.json", encoding="utf-8"))
cand = [r for r in rows if r[0] in ("未解決表", "その他") and r[1] in ("食い違い", "空欄→埋められる", "マスタに無い誌")]
JUNK = re.compile(r"一覧|記載なし|解説|プロフィール|^昭和$|未収録|誤植|^[：:.\s／/]")
cand = [r for r in cand if not JUNK.search(r[5] or "")]
hits = json.load(open(os.path.join(ROOT, ".cache/jawiki-title-hits.json"), encoding="utf-8"))
by_stem, by_title = {}, {}
for stem, title, n, w in hits:
    by_stem.setdefault(stem, []).append(w); by_title.setdefault(norm(title), []).append(w)
idx = json.load(open(f"{L}/wiki-index.json", encoding="utf-8")) if os.path.exists(f"{L}/wiki-index.json") else {}
cap = json.load(open(f"{L}/rakuten-caption-mags.json", encoding="utf-8"))
ser = {x["slug"]: x for x in json.load(open(f"{L}/madb-serial-vs-page.json", encoding="utf-8"))}
sho = {x["slug"]: x for x in json.load(open(f"{L}/madb-vs-page.json", encoding="utf-8"))}
li = json.load(open(os.path.join(ROOT, "data/manga-list-index.json"), encoding="utf-8"))
F = {k: i for i, k in enumerate(li["f"])}


def nm(v):
    return [str(x).split("\t")[0] if not isinstance(x, dict) else x.get("name", "") for x in (v or [])]


page = {r[F["slug"]]: {"art": [a for a in nm(r[F["authors"]]) if a], "orig": [a for a in nm(r[F["original_authors"]]) if a],
                        "year": r[F["year_started"]] or 0} for r in li["d"]}


def variants(t):
    v = [t]
    for x in (t.replace("!", "！").replace("?", "？"), t.replace("！", "!").replace("？", "?")):
        if x != t:
            v.append(x)
    v.append(t + " (漫画)")
    base = re.split(r"[ 　]+[-‐－〜~]", t)[0].strip()
    if base and base != t:
        v += [base, base + " (漫画)"]
    return v


def articles(r):
    out = []
    for w in dict.fromkeys(by_stem.get(r[2], []) + by_title.get(norm(r[3]), [])):
        p = os.path.join(ROOT, ".cache/wiki-sweep", safe_key(w) + ".txt")
        if os.path.exists(p):
            out.append((w, p))
    for v in variants(r[3]):
        e = idx.get(v)
        if e and not e["missing"] and not e.get("disambig"):
            out.append((e["final"], os.path.join(L, "wiki", e["file"])))
    seen, res = set(), []
    for w, p in out:
        if w not in seen:
            seen.add(w); res.append((w, p))
    return res


def fetched(r):
    return all(v in idx for v in variants(r[3])) or bool(by_stem.get(r[2]) or by_title.get(norm(r[3])))


SEP = r"[\s　・:：\-‐－〜~～「」『』()（）!！?？]"


def tsim(pt, bt):
    """題が同じ(正規化一致)か、 片方がもう片方の中に「区切りで挟まれて」現れる時だけ同じ作品の欄とみなす。
    ホクサイと飯 ⊂ ホクサイと飯さえあれば(区切りなし)= 別作品なので弾く。 ゼロの使い魔外伝 タバサの冒険 ⊃ タバサの冒険 = 可。"""
    braw = re.sub(r"<nowiki>|</nowiki>|<br\s*/?>", " ", plain(bt)).strip()
    a, b = norm(pt), norm(braw)
    if not a or not b:
        return False
    if a == b:
        return True

    def bounded(small, big):
        for m in re.finditer(re.escape(small), big):
            l = big[m.start() - 1] if m.start() > 0 else " "
            r = big[m.end()] if m.end() < len(big) else " "
            if re.match(SEP, l) and re.match(SEP, r):
                return True
        return False
    p2 = unicodedata.normalize("NFKC", pt).strip(); b2 = unicodedata.normalize("NFKC", braw)
    return (len(p2) >= 2 and bounded(p2, b2)) or (len(b2) >= 2 and bounded(b2, p2))


def artists(b):
    s = " ".join(b.get(k, "") for k in ("作者", "作画", "漫画", "著者"))
    names = [x for pair in links(s) for x in pair] + [x for x in re.split(r"[、,/・\s]|<br\s*/?>", plain(s)) if x]
    return {norm(x) for x in names if len(norm(x)) >= 2}


def madb_of(slug):
    s = ser.get(slug); h = sho.get(slug); out = {}
    if s:
        tot = sum(s["mags"].values())
        out["目次"] = [s["key"] or s["madb"], s["n"], round(s["n"] / tot, 2), s["mags"]]
    if h:
        out["初出"] = [h["madb_key"] or h["madb_name"], h.get("strong"), h["first"][:90]]
    return out


res = []
for r in cand:
    grp, cls, slug, title, cur, madb, ev = r
    P = page[slug]
    pa = {norm(a) for a in P["art"] if len(norm(a)) >= 2}
    po = {norm(a) for a in P["orig"] if len(norm(a)) >= 2}
    best = None; art_seen = False
    for w, p in articles(r):
        art_seen = True
        wt = open(p, encoding="utf-8").read()
        for b in blocks(wt):
            mv = b.get("掲載誌") or b.get("掲載サイト") or b.get("掲載誌（又は連載）") or ""
            if not mv.strip():
                continue
            bt = b.get("タイトル") or re.sub(r"\s*\([^)]*\)$", "", w)
            if not tsim(title, bt):
                continue
            ar = artists(b); allp = people(b)
            lvl = 2 if any(a in x or x in a for a in pa for x in ar) else (1 if any(a in x or x in a for a in (pa | po) for x in allp) else 0)
            if lvl == 0 or (pa and lvl < 2):
                continue          # ★作画者が分かる頁は作画者で合う欄だけ(原作者だけ合う欄=別の漫画版のことがある 伝説の勇者の伝説)
            y = years(b); py = P["year"]
            dy = abs(y - py) if (y and py) else 9
            fm = first_mag(mv); k, disp, note = mag_key(fm)
            moved = bool(re.search(r"→|&#8594;|<br|、", strip_markup(mv)))
            c = (-lvl, dy, w, k or ident(disp), disp, note, y, strip_markup(mv)[:120].replace("\n", " "), moved)
            if best is None or c[:2] < best[:2]:
                best = c
    W = None
    if best:
        _, dy, w, wid, disp, note, y, raw, moved = best
        W = {"article": w, "id": wid, "name": disp, "year": y, "dy": dy, "note": note, "raw": raw, "moved": moved, "lvl": -best[0]}
    Cid = cur or ""
    Mid = ident(madb)
    Rs = [ident(n) for _, _, n, _ in cap.get(slug, [])]
    Rid = Counter(Rs).most_common(1)[0][0] if Rs else ""
    if W:
        Wid = W["id"]
        if W["dy"] > 6 and W["dy"] != 9:
            v = "要確認(Wikiの欄と年が離れる)"
        elif W["note"]:
            v = "要確認(Wikiは増刊等)"
        elif same(Wid, Mid):
            v = "今のまま(3つとも同じ誌)" if Cid and same(Cid, Wid) else ("埋める" if not Cid else "直す") + "(Wiki+MADB)"
        elif Cid and same(Wid, Cid):
            v = "今のまま(Wiki=今の値)"
        else:
            v = "要確認(Wikiは別の誌)"
    elif Cid and same(Cid, Mid):
        v = "今のまま(MADB=今の値)"
    else:
        if Rid and same(Rid, Mid):
            v = ("埋める" if not Cid else "直す") + "(MADB+楽天)"
        elif not fetched(r):
            v = "未取得(Wiki)"
        else:
            m = madb_of(slug)
            strong = ("目次" in m and m["目次"][1] >= 10 and m["目次"][2] >= 0.8) or ("初出" in m and bool(m["初出"][1]))
            v = "MADBのみ(" + ("強" if strong else "弱") + ")" + ("・記事はあるが欄が合わない" if art_seen else "")
    res.append({"grp": grp, "cls": cls, "slug": slug, "title": title, "cur": Cid, "madb": madb, "madb_id": Mid,
                "madb_ev": madb_of(slug), "wiki": W, "rakuten": cap.get(slug, [])[:3], "verdict": v})
json.dump(res, open(f"{L}/wiki-judge2.json", "w", encoding="utf-8"), ensure_ascii=False)
c = Counter((x["grp"] + "/" + x["cls"], x["verdict"]) for x in res)
for g in ("未解決表/食い違い", "その他/食い違い", "その他/空欄→埋められる", "未解決表/マスタに無い誌", "その他/マスタに無い誌"):
    print(g, sum(v for k, v in c.items() if k[0] == g))
    for k, v in sorted(((k[1], v) for k, v in c.items() if k[0] == g), key=lambda x: -x[1]):
        print("     ", k, v)

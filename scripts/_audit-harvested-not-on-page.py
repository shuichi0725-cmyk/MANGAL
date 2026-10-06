#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""月次サニティ #36: 「拾ったのに頁に無い」層(カクリキ2型 / 7/24種4全消し型)。報告のみ(seed は書かない)。

2026-10-06 発見(mangaseek の発売日一覧との突き合わせ): 発売済みの続巻が頁に出ていなかった。原因は2つ。
  ①7/24 月次(1e107d9a4)が種4-auto を全消し → 8/26 の復元(8/21直前から)の対象外 → 225冊が誰にも見えないまま消えていた
  ②日次の楽天予約は「前回から増えたISBN」しか分類しない → 初見で頁に入らなかった巻は二度と拾われない
    (予約頁の続巻は分類の前に「過去ドラフトの再登場」として捨てられていた=カクリキ2/猩猩姫3)
どちらも「一度は手元に来た巻が、今どの頁にも無い」で見える。既存の番人は穴がある:
  _audit-isbn-loss.py = 連続する2回の反映の差しか見ない(基準線より前の消失は見えない)
  巻抜け監査          = 途中の欠けしか見ない(最新巻=末尾の欠けは見えない)

A. 種4の履歴: volumes-supplement(-auto/手動/-offset).yml の git 全版に一度でも載ったISBNのうち、今どこにも無いもの
B. 予約の窓: 楽天予約harvest(latest-full ∪ prev)のうち、題が本番頁と一致+著者が重なるのに頁に無いもの

C. 予約頁 seed(preorder-pages)に在るのに頁に出ていない巻

「頁に無い」= 本番頁(ISBN索引)に無く、種2 / ドラフト / ISBN除外簿・退役簿 / 確認済み簿 のどれにも無い。
★今の種4は「載っている」に数えない: 予約頁で作られる頁は種4を読まない(promote の予約合流は本流が同じ stem を
  書いた時だけ seed を退く)ので、種4に在っても頁に出ていないことがある(2026-10-06 97冊を実踏)。

class(月次で見るのは ★ の新規増加):
  ★LOST          頁が在り、同じ版にその巻番号が無い(=本当に抜けている)
  ★NO_PAGE       行き先の頁を決められない(題無し・鍵が種2から消えた・候補が割れる)
  ★HARVEST       予約harvestに在り題・著者が頁と一致するのに頁に無い(②の再投入が効いていれば発売前に消える)
   FROZEN        行き先が手で巻を固定した頁(edition-overrides / edition-canonical / 予約頁)= 種4では出ない。本体へ1件ずつ
   NUM_PRESENT   その巻番号は別ISBNで頁に在る(版違い/特装版/ISBN差し替え。情報)
確認済み簿 data/seeds/harvested-not-on-page-ack.jsonl ({"isbn13","reason","at"}) に書いた行は ack 列に理由を出し件数から外す。

使い方: python scripts/_audit-harvested-not-on-page.py          → docs/production-diagnostics/harvested-not-on-page.tsv
        (git 全版の読み出しは .cache/audit-hnop-revcache.json に貯めるので2回目以降は速い)
"""
import sys as _sys_h
if any(_a in ("-h", "--help") for _a in _sys_h.argv[1:]):
    print(__doc__); _sys_h.exit(0)
import collections, functools, glob, json, os, re, sqlite3, subprocess, sys, unicodedata
sys.stdout.reconfigure(encoding="utf-8")
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
SEEDS = os.path.join(ROOT, "data", "seeds")
PRE = os.path.join(ROOT, ".cache", "preorders")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "harvested-not-on-page.tsv")
REVCACHE = os.path.join(ROOT, ".cache", "audit-hnop-revcache.json")
ACK = os.path.join(SEEDS, "harvested-not-on-page-ack.jsonl")
SEED4 = ["volumes-supplement-auto.yml", "volumes-supplement.yml", "volumes-supplement-offset.yml"]
EXCLUDE_FILES = ["volume-exclude.yml", "volume-exclude-isbn.yml", "art-book-exclude-isbn.yml", "preorder-deny.jsonl",
                 "anthology-drop.tsv", "american-comics-drop.tsv", "distill-drop-2026.tsv", "non-manga-drop.yml",
                 "company-nonmanga-drop.json", "magazines-drop.yml", "volumes-supplement-retire-changelog.jsonl"]
ISBN_RE = re.compile(r"97[89]\d{10}")
SPECIAL_ED = re.compile(r"特装版|限定版|初回限定|豪華版|特別版|特典付|小冊子付|ドラマCD|CD付|DVD付|Blu-?ray|OAD|アクリル|しおり付|カードセット付|ポストカード|クリアスタンド|キーホルダー|フィギュア付", re.I)


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    return re.sub(r"[\s・!?！？〜~ー\-—()（）【】《》〈〉「」『』:：,，.。、/／'\"’”♡♥☆★…‥&＆]", "", s)


def norm_person(s):
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = re.sub(r"[（(][^）)]*[）)]", "", s)
    return re.sub(r"[\s・=＝]", "", s)


def load_pub2stem():
    m = {}
    p = os.path.join(SEEDS, "slug-overrides.yml")
    if os.path.exists(p):
        d = yaml.safe_load(open(p, encoding="utf-8")) or {}
        ov = d.pop("overrides", {}) or {}
        for stem, pub in d.items():
            if isinstance(pub, str) and pub != stem:
                m[pub] = stem
        for stem, rec in ov.items():
            pub = (rec or {}).get("slug") if isinstance(rec, dict) else None
            if pub and pub != stem:
                m[pub] = stem
    return m


PUB2STEM = load_pub2stem()


@functools.lru_cache(maxsize=None)
def resolve_stem(slug):
    if not slug:
        return None
    if os.path.exists(os.path.join(ROOT, "data", "manga.v2", f"{slug}.yml")):
        return slug
    st = PUB2STEM.get(slug)
    if st and os.path.exists(os.path.join(ROOT, "data", "manga.v2", f"{st}.yml")):
        return st
    return None


@functools.lru_cache(maxsize=None)
def page(stem):
    p = os.path.join(ROOT, "data", "manga.v2", f"{stem}.yml")
    return yaml.safe_load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def history_entries():
    """種4 3ファイルの git 全版から {isbn: 最後に見えた entry(dict)} を作る(版ごとの抽出結果はキャッシュ)。"""
    cache = json.load(open(REVCACHE, encoding="utf-8")) if os.path.exists(REVCACHE) else {}
    out = {}
    for f in SEED4:
        path = f"data/seeds/{f}"
        revs = subprocess.run(["git", "log", "--reverse", "--format=%H", "--", path], cwd=ROOT,
                              capture_output=True, text=True).stdout.split()
        for rev in revs:
            key = f"{rev}:{path}"
            if key not in cache:
                r = subprocess.run(["git", "show", key], cwd=ROOT, capture_output=True)
                ents = {}
                if r.returncode == 0:
                    txt = r.stdout.decode("utf-8", errors="ignore")
                    for blk in re.split(r"\n(?=- )", txt):
                        m = re.search(r"isbn13:\s*'?(97[89]\d{10})", blk)
                        if not m:
                            continue
                        g = lambda k: (re.search(rf"^\s*{k}:\s*(.*)$", blk, re.M) or [None, None])[1]
                        ents[m.group(1)] = {"number": g("number"), "note": g("note"), "title": g("title_display"),
                                            "edition_type": g("edition_type"), "release_date": g("release_date"),
                                            "source": g("source"), "keys": re.findall(r"^\s*- ((?:qid|name):[^\n]*)$", blk, re.M),
                                            "file": f, "rev": rev[:9]}
                cache[key] = ents
            for ib, e in cache[key].items():
                out[ib] = e
    json.dump(cache, open(REVCACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return out


def main():
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "_exists.py"), "--build"], cwd=ROOT,
                   check=True, capture_output=True)
    idx = json.load(open(os.path.join(ROOT, ".cache", "isbn-page-index.json"), encoding="utf-8"))
    con = sqlite3.connect(f"file:{ROOT}/.cache/db-v2.sqlite?mode=ro", uri=True)
    resolved = set(idx) | {r[0] for r in con.execute("SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL")}
    files = [os.path.join(SEEDS, f) for f in EXCLUDE_FILES] + glob.glob(os.path.join(PRE, "drafts*", "*.yml"))
    for p in files:   # ★種4・予約頁seed は数えない(上の docstring)
        if os.path.exists(p):
            resolved |= set(ISBN_RE.findall(open(p, encoding="utf-8", errors="ignore").read()))
    ack = {}
    if os.path.exists(ACK):
        for ln in open(ACK, encoding="utf-8"):
            if ln.strip():
                d = json.loads(ln)
                ack[str(d.get("isbn13"))] = d.get("reason", "")
    eo = json.load(open(os.path.join(SEEDS, "edition-overrides.json"), encoding="utf-8"))

    def frozen(stem):
        d = page(stem) or {}
        pub = d.get("slug") or stem
        if isinstance(eo.get(pub), dict) and eo[pub].get("editions"):
            return "edition-overrides"
        if os.path.exists(os.path.join(SEEDS, "edition-canonical", f"{stem}.yml")):
            return "edition-canonical"
        if os.path.exists(os.path.join(SEEDS, "preorder-pages", f"{stem}.yml")):
            return "preorder-pages"
        return None

    def stems_for_key(sk):
        c = collections.Counter()
        for (ib,) in con.execute("SELECT v.isbn13 FROM volumes v JOIN editions e ON v.edition_id=e.id "
                                 "JOIN series s ON e.series_id=s.id WHERE s.series_key=? AND v.isbn13 IS NOT NULL", (sk,)):
            for pub in idx.get(ib, []):
                c[resolve_stem(pub) or pub] += 1
        return c

    def classify(stem, number, etype):
        d = page(stem)
        if not d:
            return "NO_PAGE", "頁ファイル不在"
        fz = frozen(stem)
        if fz:
            return "FROZEN", fz
        try:
            num = float(str(number).strip("'\""))
        except (TypeError, ValueError):
            return "NO_PAGE", "巻番号不明"
        nums = {float(v["number"]) for ed in d.get("editions") or [] if (ed.get("type") or "standard") == (etype or "standard")
                for v in ed.get("volumes") or [] if isinstance(v.get("number"), (int, float))}
        return ("NUM_PRESENT", "同巻番号が別ISBNで在る") if num in nums else ("LOST", "")

    rows = []
    # A. 種4の履歴
    hist = history_entries()
    for ib, e in hist.items():
        if ib in resolved:
            continue
        m = re.search(r"stem=([a-z0-9\-]+)", e.get("note") or "") or re.search(r"slug=([a-z0-9\-]+)", e.get("note") or "")
        stem = resolve_stem(m.group(1)) if m else None
        if not stem:
            tot = collections.Counter()
            for sk in e.get("keys") or []:
                tot.update(stems_for_key(sk))
            top = tot.most_common(2)
            if top and (len(top) == 1 or top[0][1] >= 2 * top[1][1]):
                stem = top[0][0]
        if stem:
            cls, why = classify(stem, e.get("number"), (e.get("edition_type") or "").strip("'\""))
        else:
            cls, why = "NO_PAGE", "題無し・鍵が種2に無い/候補が割れる"
        if cls == "LOST" and SPECIAL_ED.search(str(e.get("title") or "")):
            cls, why = "NUM_PRESENT", "特装版(通常版の扱い)"
        rows.append({"class": cls, "isbn13": ib, "number": e.get("number"), "stem": stem or "",
                     "page_title": (page(stem) or {}).get("title", "") if stem else "", "title": e.get("title") or "",
                     "date": e.get("release_date") or "", "part": f"A:{e['file']}@{e['rev']}",
                     "why": why, "ack": ack.get(ib, "")})
    # C. 予約頁 seed に在るのに頁に無い(seed を書いたのに頁が作り直されていない/合流で落ちた)
    seen_a = {r["isbn13"] for r in rows}
    for p in sorted(glob.glob(os.path.join(SEEDS, "preorder-pages", "*.yml"))):
        stem = os.path.splitext(os.path.basename(p))[0]
        d = yaml.safe_load(open(p, encoding="utf-8")) or {}
        for e in d.get("editions") or []:
            for v in e.get("volumes") or []:
                ib = str(v.get("isbn13") or "")
                if ib and ib not in resolved and ib not in seen_a:
                    seen_a.add(ib)
                    rows.append({"class": "LOST", "isbn13": ib, "number": v.get("number"), "stem": stem,
                                 "page_title": (page(stem) or {}).get("title", ""), "title": d.get("title") or "",
                                 "date": v.get("release_date") or "", "part": "C:preorder-pages",
                                 "why": "予約頁seedに在るのに頁に無い(要反映)", "ack": ack.get(ib, "")})
    # B. 予約の窓
    try:
        from _preorder_title_lib import split_title
    except Exception:
        split_title = None
    li = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    F = li["f"]
    it_, is_, ia_ = F.index("title"), F.index("slug"), F.index("authors")
    by_title = collections.defaultdict(list)
    for r in li["d"]:
        by_title[norm(r[it_])].append((r[is_], {norm_person(str(a).split("\t")[0]) for a in (r[ia_] or [])}))
    seen = {r["isbn13"] for r in rows}
    for fn in ("preorders-latest-full.jsonl", "preorders-prev.jsonl"):
        p = os.path.join(PRE, fn)
        if not os.path.exists(p):
            continue
        for ln in open(p, encoding="utf-8"):
            if not ln.strip():
                continue
            h = json.loads(ln)
            ib = str(h.get("isbn") or "")
            if not ib or ib in resolved or ib in seen or SPECIAL_ED.search(str(h.get("title") or "")):
                continue
            base = h.get("title") or ""
            vol = None
            if split_title:
                try:
                    st = split_title(base)
                    base, vol = st.get("base") or base, st.get("vol")
                except Exception:
                    pass
            cands = by_title.get(norm(base)) or []
            hk = {norm_person(x) for x in re.split(r"[/／、,]", str(h.get("author") or "")) if norm_person(x)}
            hit = [s for s, au in cands if hk & au]
            if len(hit) != 1:
                continue
            stem = resolve_stem(hit[0]) or hit[0]
            seen.add(ib)
            rows.append({"class": "HARVEST", "isbn13": ib, "number": vol or "", "stem": stem,
                         "page_title": (page(stem) or {}).get("title", ""), "title": h.get("title") or "",
                         "date": h.get("salesDate") or "", "part": f"B:{fn}",
                         "why": ("予約頁=seed直接追記" if frozen(stem) == "preorder-pages" else ""), "ack": ack.get(ib, "")})

    order = {"LOST": 0, "NO_PAGE": 1, "HARVEST": 2, "FROZEN": 3, "NUM_PRESENT": 4}
    rows.sort(key=lambda r: (order[r["class"]], bool(r["ack"]), r["stem"], str(r["number"])))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cols = ["class", "isbn13", "number", "stem", "page_title", "title", "date", "part", "why", "ack"]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r[c] if r[c] is not None else "").replace("\t", " ") for c in cols) + "\n")
    c = collections.Counter(r["class"] for r in rows if not r["ack"])
    ca = collections.Counter(r["class"] for r in rows if r["ack"])
    print(f"拾ったのに頁に無い: 種4履歴 {len(hist)} ISBN を走査")
    for k in order:
        star = "★" if k in ("LOST", "NO_PAGE", "HARVEST") else " "
        print(f"  {star}{k:12s} {c.get(k, 0):5d}" + (f"  (確認済み {ca[k]})" if ca.get(k) else ""))
    print(f"→ {os.path.relpath(OUT, ROOT)}  ★の新規増加=要対応(LOST/HARVEST は頁に足す・NO_PAGE は行き先を決める)")


if __name__ == "__main__":
    main()

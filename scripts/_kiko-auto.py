#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""奇子型(多版混在)自動是正パイプライン (= 2026-07-05 black-angels手動是正の機械化)

段階:
  --detect          現DBから奇子型候補を検出(帯混在×日付逆行×書影ムラ)→ .cache/kiko-candidates.tsv
  --harvest N       候補上位N作をNDL SRU harvest(著者束縛・全ページ・断片縫合)→ .cache/kiko-ndl.jsonl (resumable)
  --gen [--write]   版クラスタ(帯×年代×NDLシリーズタイトル)→全ゲート緑のみ canonical生成
  --verify slugs    promote後の数値検証(欠番/逆行/帯)→不合格は canonical削除(auto-revert)

戒めとの整合 [[feedback_dont_repeat_regrouping_error]]:
  - 二源合意(NDL典拠 × 楽天題) + fail-closed(1ゲートでも黄=worklist行き・書かない)
  - 可逆(canonical seed 1ファイル=削除で戻る) + 小バッチ + 事後検証で自動revert
ゲート:
  G1 著者束縛query + NDL題base==頁題base(題衝突/スピンオフ排除)
  G2 ISBN checksum再計算
  G3 楽天題base==頁題base(cacheに居る分・1件でも別作ならabort)
  G4 standardクラスタ=最古era×巻1..N連続(≥90%)×N≥3
  G5 非掲載ラベル(スペシャル/傑作選/ワイドSP/アンソロ/コンビニ)はクラスタごと除外(頁に足さない)
  G6 canonical既存slugはskip(直し済みと衝突しない)
"""
import argparse, glob, html, json, os, re, sys, time, unicodedata, urllib.request, urllib.parse
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try:
    from yaml import CSafeLoader as _L
except ImportError:
    from yaml import SafeLoader as _L
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEEP = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban"}
CAND = os.path.join(ROOT, ".cache", "kiko-candidates.tsv")
NDLJ = os.path.join(ROOT, ".cache", "kiko-ndl.jsonl")
WORK = os.path.join(ROOT, "docs", "production-diagnostics", "kiko-auto-worklist.tsv")

def months(s):
    m = re.match(r"^(\d{4})[.\-/]?(\d{1,2})?", str(s or ""))
    return int(m.group(1)) * 12 + (int(m.group(2)) if m.group(2) else 6) if m else None

_ITAIJI = str.maketrans("讚檜龍澤惡藝眞櫻壽萬邊",
                        "讃桧竜沢悪芸真桜寿万辺")
def norm(t):
    t = unicodedata.normalize("NFKC", str(t or "")).translate(_ITAIJI)
    return re.sub(r"[\s　・!！?？:：〜~\-＆&。、．.『』「」]", "", t).lower()

def to13(raw):
    d = re.sub(r"[^0-9X]", "", str(raw).upper())
    if len(d) == 13 and d.startswith("978"):
        core = d[:12]
    elif len(d) >= 9:
        core = "978" + d[:9]
    else:
        return None
    s = sum(int(c) * (1 if k % 2 == 0 else 3) for k, c in enumerate(core))
    return core + str((10 - s % 10) % 10)

# ---------- detect ----------
def detect():
    rows = []
    existing = {os.path.basename(x)[:-4] for x in glob.glob(f"{ROOT}/data/seeds/edition-canonical/*.yml")}
    for p in glob.glob(f"{ROOT}/data/manga.v2/*.yml"):
        slug = os.path.basename(p)[:-4]
        if slug in existing:
            continue
        try:
            d = yaml.load(open(p, encoding="utf-8"), Loader=_L)
        except Exception:
            continue
        if not d or d.get("adult") or d.get("adult_us"):
            continue
        for e in d.get("editions") or []:
            if e.get("type") not in KEEP:
                continue
            vols = [v for v in (e.get("volumes") or []) if v.get("isbn13")]
            if len(vols) < 4:
                continue
            bands = Counter(str(v["isbn13"])[:7] for v in vols)
            if len(bands) < 2:
                continue
            seq = [(v.get("number"), months(v.get("release_date"))) for v in sorted(vols, key=lambda x: x.get("number") or 0) if v.get("number")]
            inv = sum(1 for i in range(1, len(seq)) if seq[i][1] and seq[i-1][1] and seq[i][1] < seq[i-1][1])
            if inv == 0:
                continue  # 帯複数でも時系列単調=社名変更等の正常
            ncover = sum(1 for v in vols if v.get("cover_url"))
            labmix = len({bool(re.search(r"[上中下前後]", str(v.get("volume_label") or ""))) for v in vols}) > 1
            score = inv * 2 + len(bands) + (2 if labmix else 0) + (1 if 0 < ncover < len(vols) else 0)
            rows.append((score, slug, d.get("title"), e.get("type"), len(vols), len(bands), inv))
            break
    rows.sort(reverse=True)
    with open(CAND, "w", encoding="utf-8") as f:
        f.write("score\tslug\ttitle\tedition\tvols\tbands\tinversions\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    print(f"奇子型候補: {len(rows)}作 → {CAND}")
    for r in rows[:15]:
        print(f"  score{r[0]:>3} {r[1]} ({r[4]}冊/帯{r[5]}/逆行{r[6]})")

# ---------- harvest ----------
def sru(q, start):
    p = {"operation": "searchRetrieve", "query": q, "recordSchema": "dcndl",
         "maximumRecords": "200", "startRecord": str(start)}
    req = urllib.request.Request("https://ndlsearch.ndl.go.jp/api/sru?" + urllib.parse.urlencode(p))
    req.add_header("User-Agent", "Mozilla/5.0")
    return html.unescape(urllib.request.urlopen(req, timeout=40).read().decode("utf-8"))

def parse_records(xml):
    recs = []
    for r in re.split(r"<dcndl:BibResource", xml)[1:]:
        g = lambda pat: (re.search(pat, r, re.S).group(1) if re.search(pat, r, re.S) else "")
        recs.append({"title": g(r"<dcterms:title>([^<]+)"),
                     "vol": g(r"<dcndl:volume>.*?<rdf:value>([^<]+)"),
                     "date": g(r"<dcterms:date>([^<]+)"),
                     "isbn": re.sub(r"[^0-9X]", "", g(r"(97[89][\d\-]{10,16})")) or re.sub(r"[^0-9X]", "", g(r"ISBN[^\d]{0,3}(\d[\d\-]{8,12}[\dX])")),
                     "series": g(r"<dcndl:seriesTitle>([^<]+)") or g(r"<dcndl:seriesTitle>.*?<rdf:value>([^<]+)"),
                     "pub": g(r"<foaf:name>([^<]+)")})
    # 断片縫合(isbnのみ断片を直前のtitle断片へ)
    out = []
    for r in recs:
        if r.get("isbn") and not r.get("title") and out and not out[-1].get("isbn"):
            out[-1]["isbn"] = r["isbn"]
        else:
            out.append(r)
    return out

def harvest(n_works):
    done = set()
    if os.path.exists(NDLJ):
        for ln in open(NDLJ, encoding="utf-8"):
            done.add(json.loads(ln)["slug"])
    targets = []
    for i, ln in enumerate(open(CAND, encoding="utf-8")):
        if i == 0:
            continue
        c = ln.rstrip("\n").split("\t")
        if c[1] not in done:
            targets.append(c[1])
        if len(targets) >= n_works:
            break
    fo = open(NDLJ, "a", encoding="utf-8")
    for slug in targets:
        d = yaml.load(open(f"{ROOT}/data/manga.v2/{slug}.yml", encoding="utf-8"), Loader=_L)
        title = d.get("title") or ""
        creator = (d.get("authors") or [{}])[-1].get("name") or ""  # 作画側(最後)優先
        q = f'title="{title}" AND creator="{creator}"'
        recs = []
        start = 1
        total = None
        while start <= 1800:
            try:
                xml = sru(q, start)
            except Exception as ex:
                print(f"  {slug}: p{start}失敗 {ex} → 取得分で確定")
                break
            if "Too Many Requests" in xml:
                print("★429→中断(逐次保存済)")
                fo.close()
                sys.exit(2)
            m = re.search(r"<numberOfRecords>(\d+)", xml)
            total = int(m.group(1)) if m else 0
            recs += parse_records(xml)
            time.sleep(1.3)
            start += 200
            if start > (total or 0):
                break
        fo.write(json.dumps({"slug": slug, "total": total, "records": recs}, ensure_ascii=False) + "\n")
        fo.flush()
        print(f"  {slug}: NDL {len(recs)}件(total={total})")
    fo.close()
    print(f"harvest完了 {len(targets)}作")

# ---------- gen ----------
EXCL_PAT = re.compile(r"スペシャル|傑作|ワイドSP|アンソロ|コンビニ|My First|MyFirst|廉価|総集|セレクト版")
def etype_of(series):
    s = series or ""
    if "文庫" in s: return "bunkobon", "文庫版"
    if re.search(r"ワイド(?!SP)", s): return "wideban", "ワイド版"
    if re.search(r"愛蔵|豪華|大全", s): return "aizoban", None
    if re.search(r"完全版|COMPLETE", s, re.I): return "kanzenban", "完全版"
    if re.search(r"新装|セレクション|デラックス|DX", s): return "shinsoban", None
    return "standard", None

def vnum(v):
    m = re.fullmatch(r"\s*(\d{1,3})\s*", str(v or ""))
    return int(m.group(1)) if m else None

def gen(write=False):
    tm = json.load(open(f"{ROOT}/.cache/isbn-title-map.json", encoding="utf-8"))
    results = []
    wl = []
    for ln in open(NDLJ, encoding="utf-8"):
        j = json.loads(ln)
        slug = j["slug"]
        if os.path.exists(f"{ROOT}/data/seeds/edition-canonical/{slug}.yml"):
            results.append((slug, "G6 canonical既存=skip")); continue
        page = yaml.load(open(f"{ROOT}/data/manga.v2/{slug}.yml", encoding="utf-8"), Loader=_L)
        pt = norm(page.get("title"))
        # G1: NDL題base==頁題base のレコードだけ
        clusters = defaultdict(dict)  # (band, series) -> {vol: (isbn,date)}
        for r in j["records"]:
            n = vnum(r.get("vol"))
            ib = to13(r.get("isbn")) if r.get("isbn") else None
            _t = unicodedata.normalize("NFKC", r.get("title") or "")
            _t = re.sub(r"[.。]\s*(第?\s*\d+\s*巻?|[上中下前後]巻?|vol(ume)?\.?\s*\d+)\s*$", "", _t, flags=re.I)
            _t = re.sub(r"\s*(第?\s*\d+\s*巻|[（(]\d+[)）])\s*$", "", _t)
            tb = norm(_t)
            if n is None or not ib or len(ib) != 13:
                continue
            if tb != pt:
                continue
            key = (ib[:7], (r.get("series") or "").split(".")[0].strip())
            clusters[key].setdefault(n, (ib, r.get("date", "")))
        if not clusters:
            results.append((slug, "NDLクラスタ0(題不一致/ISBN無)")); wl.append((slug, "NDLクラスタ0")); continue
        # クラスタ→版候補
        cands = []
        for (band, series), vols in clusters.items():
            if len(vols) < 2:
                continue
            if EXCL_PAT.search(series or ""):
                continue  # G5 非掲載系
            eras = [months(v[1]) for v in vols.values() if months(v[1])]
            if not eras:
                continue
            cands.append({"band": band, "series": series, "vols": vols, "era": min(eras)})
        if not cands:
            results.append((slug, "版クラスタ不成立")); wl.append((slug, "版クラスタ不成立")); continue
        cands.sort(key=lambda x: x["era"])
        # ★standardに据えるのはstandard型レーベルのみ(文庫/ワイドが最古ISBNでも原版扱いしない=きりひと型。
        #   プレISBN原版はNDLにISBN無→文庫が最古クラスタになる罠)
        std_cands = [c for c in cands if etype_of(c["series"])[0] == "standard"]
        if not std_cands:
            results.append((slug, f"原版(standard型)クラスタ無=プレISBN原版か 最古={cands[0]['series']}")); wl.append((slug, "原版クラスタ無")); continue
        orig = std_cands[0]
        onums = sorted(orig["vols"])
        # G4: 1..N 連続≥90% N>=3
        if onums[0] != 1 or len(onums) < 3 or len(onums) < 0.9 * onums[-1]:
            results.append((slug, f"G4原版不完全 vols={onums[:5]}..{onums[-1]}")); wl.append((slug, f"G4 {onums[:5]}..")); continue
        # G7 切り捨てガード(SERVAMP事故 2026-07-05): 現ページの最大巻がNDL原版クラスタより大きい=
        #   連載中のレーベル移行(帯変更)で後半巻が別クラスタに落ちた可能性→canonical化すると本編切り捨て
        _pgmax = max([v.get("number") or 0 for e in (page.get("editions") or []) if e.get("type") == "standard"
                      for v in (e.get("volumes") or [])], default=0)
        if _pgmax > onums[-1] + 1:
            results.append((slug, f"G7切り捨て疑い page最大{_pgmax}巻>NDL原版{onums[-1]}巻(移籍/連載中)")); wl.append((slug, f"G7 {_pgmax}>{onums[-1]}")); continue
        # G3: 楽天題
        def rak_bad(vols):
            bad = []
            for n, (ib, dt) in vols.items():
                t2 = tm.get(ib)
                if t2 is None:
                    continue
                base = norm(re.sub(r"[（(]\s*\d+\s*[)）]\s*$|第?\s*\d+\s*巻?\s*$", "", unicodedata.normalize("NFKC", t2)))
                if not (base == pt or base.startswith(pt) or pt.startswith(base)):
                    bad.append((n, t2[:18]))
            return bad
        b = rak_bad(orig["vols"])
        if b:
            results.append((slug, f"G3楽天不一致 {b[:2]}")); wl.append((slug, f"G3 {b[:2]}")); continue
        def mk(vols):
            out = []
            for n in sorted(vols):
                ib, dt = vols[n]
                m = re.match(r"^(\d{4})[.\-/]?(\d{1,2})?", dt)
                ds = f"{m.group(1)}-{int(m.group(2)):02d}" if m and m.group(2) else (m.group(1) if m else None)
                out.append({"number": n, "isbn13": ib, "release_date": ds})
            return out
        def yr(vs):
            ys = sorted({str(v["release_date"])[:4] for v in vs if v.get("release_date")})
            return f"{ys[0]}-{ys[-1][2:]}" if len(ys) > 1 else (ys[0] if ys else "")
        extras = []
        sup = set()
        page_types = {e.get("type") for e in page.get("editions") or []}
        for g in [c for c in cands if c is not orig]:
            if rak_bad(g["vols"]):
                continue
            gnums = sorted(g["vols"])
            if gnums[0] != 1 or len(gnums) < 0.8 * gnums[-1]:
                continue  # 追加版も概ね完全な時だけ
            et, lab = etype_of(g["series"])
            if et == "standard":
                et = "shinsoban"
            vs = mk(g["vols"])
            extras.append({"type": et, "label": f'{(lab or g["series"] or "別版")}({yr(vs)})', "volumes": vs})
            if et in page_types and et != "bunkobon":
                sup.add(et)  # 既存の同type(混線源)をsuppress。文庫は健全が多いので温存
        std = next((e for e in page.get("editions") or [] if e.get("type") == "standard"), {})
        seed = {"slug": slug, "canonical_label": (orig["series"] or std.get("label") or "通常版"),
                "source": f"奇子型自動是正(kiko-auto 2026-07-05): NDL典拠×楽天二源合意。原版={orig['series']}帯{orig['band']}全{onums[-1]}巻+追加版{len(extras)}",
                "publisher": std.get("publisher"), "volumes": mk(orig["vols"])}
        if extras:
            seed["extra_editions"] = extras
        if sup:
            seed["suppress_types"] = sorted(sup)
        if write:
            yaml.dump(seed, open(f"{ROOT}/data/seeds/edition-canonical/{slug}.yml", "w", encoding="utf-8"),
                      allow_unicode=True, sort_keys=False, width=200)
        results.append((slug, f"✅生成 原版{onums[-1]}巻({orig['series']}) extra{len(extras)} sup{sorted(sup)}"))
    for r in results:
        print(f"  {r[0]}: {r[1]}")
    ok = [r[0] for r in results if r[1].startswith("✅")]
    json.dump(ok, open(f"{ROOT}/.cache/kiko-ok.json", "w"))
    with open(WORK, "a", encoding="utf-8") as f:
        for s, why in wl:
            f.write(f"{s}\t{why}\t2026-07-05\n")
    print(f"生成{'(書出)' if write else '(dry)'}: {len(ok)} / worklist {len(wl)}")

# ---------- verify ----------
def verify(slugs):
    bad = []
    for slug in slugs:
        d = yaml.load(open(f"{ROOT}/data/manga.v2/{slug}.yml", encoding="utf-8"), Loader=_L)
        ok = True
        report = []
        for e in d.get("editions") or []:
            vols = [v for v in (e.get("volumes") or []) if v.get("isbn13")]
            if len(vols) < 2:
                continue
            nums = sorted(v.get("number") for v in vols if v.get("number"))
            gap = [n for n in range(nums[0], nums[-1] + 1) if n not in nums]
            seq = [(v.get("number"), months(v.get("release_date"))) for v in sorted(vols, key=lambda x: x.get("number") or 0)]
            inv = sum(1 for i in range(1, len(seq)) if seq[i][1] and seq[i-1][1] and seq[i][1] < seq[i-1][1])
            report.append(f"{e.get('type')}:{nums[0]}-{nums[-1]}({len(vols)})欠{len(gap)}逆{inv}")
            if gap or inv:
                ok = False
        print(f"  {slug}: {'OK' if ok else '★NG→revert'} {' / '.join(report)}")
        if not ok:
            cp = f"{ROOT}/data/seeds/edition-canonical/{slug}.yml"
            if os.path.exists(cp):
                os.remove(cp)
            bad.append(slug)
            with open(WORK, "a", encoding="utf-8") as f:
                f.write(f"{slug}\t事後検証NG(欠番or逆行)→auto-revert\t2026-07-05\n")
    json.dump(bad, open(f"{ROOT}/.cache/kiko-reverted.json", "w"))
    print(f"verify: NG={len(bad)} (canonical削除済=再promoteで元に戻る)")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--detect", action="store_true")
    ap.add_argument("--harvest", type=int)
    ap.add_argument("--gen", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--verify")
    a = ap.parse_args()
    if a.detect:
        detect()
    elif a.harvest:
        harvest(a.harvest)
    elif a.gen:
        gen(a.write)
    elif a.verify:
        verify(a.verify.split(","))

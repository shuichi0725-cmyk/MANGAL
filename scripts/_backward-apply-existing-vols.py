#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""後退蒸留A候補(existing-vols.json)の zokkan式+版判定 適用 (= 2026-07-15 ユーザ指示)

対象: _distill_backward --plan が出す「既存作の巻」候補(NDL発見・本番未収載ISBN)。
一括追加は版汚染を起こす(キリン新装版/アルスラーン同番号ISBN違い型)ため、型別ゲートで
**素直な続巻だけ**を種4(volumes-supplement-auto.yml)へ純粋追加し、残りはholdでTSV報告する。

ゲート(全部通過=S型のみ適用):
  1. 頁実在(data/manga.v2/<slug>.yml。slug-override頁=ファイル名不一致はhold M)
  2. ISBN未収載(頁上・種4上とも)
  3. 版判定: 同番号が頁(versions含む)に既存 → hold V(新装版/特装版/ISBN違い疑い=per-case)
  4. 連続性: 頁のmax番号+1から**連番**で埋まる分のみ(gapを作る飛び巻=hold G)
  5. ISBN帯: 新ISBNの出版者帯(先頭7桁)が頁既存ISBN帯と一致(帯混入防止=hold B)
  6. 日付単調: 既存最終巻日より2ヶ月以上過去=hold D(逆行=別版疑い)
書影/確定日: 楽天API実URL(real_cover_and_date)→covers seedへ純粋追加。構築禁止。

usage: python scripts/_backward-apply-existing-vols.py <year> [--dry]
次: reflect-targeted --only <touched> --push
"""
import json, os, re, sys, sqlite3, datetime, gzip
sys.stdout.reconfigure(encoding="utf-8")
import yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _preorder_draft_lib import real_cover_and_date as _rcd
try:
    from _lookup import rakuten_live as _rk_live, _env as _rk_env
    _RKENV = _rk_env()
except Exception:
    _rk_live = _RKENV = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YEAR = next((a for a in sys.argv[1:] if re.fullmatch(r"(19|20)\d{2}", a)), "2026")
DRY = "--dry" in sys.argv
AUTO = os.path.join(ROOT, "data", "seeds", "volumes-supplement-auto.yml")
TODAY = datetime.date.today().isoformat()

A = json.load(open(os.path.join(ROOT, ".cache", "backward", YEAR, "existing-vols.json"), encoding="utf-8"))
doc = yaml.safe_load(open(AUTO, encoding="utf-8")) or {"volumes": []}
have4 = {str(v.get("isbn13")) for v in doc["volumes"]}
con = sqlite3.connect(f"file:{ROOT}/.cache/db-v2.sqlite?mode=ro", uri=True)

def page_state(slug):
    p = f"{ROOT}/data/manga.v2/{slug}.yml"
    if not os.path.exists(p):
        return None
    d = yaml.safe_load(open(p, encoding="utf-8"))
    nums, isbns, last_date = set(), set(), ""
    for e in d.get("editions") or []:
        pools = [e.get("volumes") or []]
        for ver in e.get("versions") or []:
            pools.append(ver.get("volumes") or [])
        for vol_list in pools:
            for v in vol_list:
                if v.get("number") is not None:
                    nums.add(v["number"])
                if v.get("isbn13"):
                    isbns.add(str(v["isbn13"]))
                rd = str(v.get("release_date") or "")
                if rd > last_date:
                    last_date = rd
            for v in vol_list:
                for vr in v.get("variants") or []:
                    if vr.get("isbn13"):
                        isbns.add(str(vr["isbn13"]))
    return {"nums": nums, "isbns": isbns, "last_date": last_date}

def keys_for_slug(slug):
    p = f"{ROOT}/data/manga.v2/{slug}.yml"
    d = yaml.safe_load(open(p, encoding="utf-8"))
    ks = set()
    for e in d.get("editions") or []:
        for v in (e.get("volumes") or [])[:6]:
            if v.get("isbn13"):
                for r in con.execute("SELECT s.series_key FROM volumes v JOIN editions e2 ON v.edition_id=e2.id JOIN series s ON e2.series_id=s.id WHERE v.isbn13=?", (str(v["isbn13"]),)):
                    ks.add(r[0])
        if ks:
            break
    return sorted(ks) or None

def norm_date(s):
    m = re.match(r"^(\d{4})[.\-/]?(\d{1,2})?[.\-/]?(\d{1,2})?", str(s or ""))
    if not m:
        return None
    y, mo, d = m.groups()
    if mo and d:
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    if mo:
        return f"{y}-{int(mo):02d}"
    return y

# slugごとに候補を束ね、番号順に処理
by_slug = {}
for a in A:
    by_slug.setdefault(a["slug"], []).append(a)

applied, holds, touched = [], [], set()
covers_add = []
for slug, cands in sorted(by_slug.items()):
    st = page_state(slug)
    if st is None:
        for a in cands:
            holds.append(("M_頁ファイル無(override疑い)", a))
        continue
    ks = None
    mx = max([n for n in st["nums"] if isinstance(n, int)] or [0])
    expect = mx + 1
    for a in sorted(cands, key=lambda x: x["vol"]):
        isbn = str(a["isbn"])
        if isbn in st["isbns"] or isbn in have4:
            continue  # 既収載=何もしない
        if a["vol"] in st["nums"]:
            holds.append(("V_同番号既存(新装/特装/ISBN違い疑い)", a)); continue
        if a["vol"] != expect:
            holds.append((f"G_連番外(頁max={mx} 期待={expect})", a)); continue
        # ISBN帯(先頭7桁=978-4-社帯)一致
        band = isbn[:7]
        if not any(x.startswith(band) for x in st["isbns"]):
            holds.append(("B_ISBN帯不一致(帯混入/別版疑い)", a)); continue
        rd = norm_date(a.get("date"))
        # 楽天で実書影+確定日(構築禁止)
        cov, d2 = (None, None)
        if _rk_live and _RKENV:
            try:
                cov, d2 = _rcd(isbn, {}, _rk_live, _RKENV, need_date=True)
            except SystemExit:
                print("★楽天429→中断"); sys.exit(2)
            except Exception:
                pass
        rd_final = d2 or rd
        if st["last_date"] and rd_final and str(rd_final) < st["last_date"][:len(str(rd_final))] and \
           (int(str(rd_final)[:4]) * 12 + int(str(rd_final)[5:7] or 1)) < (int(st["last_date"][:4]) * 12 + int(st["last_date"][5:7] or 1)) - 2:
            holds.append((f"D_日付逆行({rd_final}<既存末{st['last_date'][:7]})", a)); continue
        if ks is None:
            ks = keys_for_slug(slug)
        if not ks:
            holds.append(("K_series_key逆引き不可", a)); continue
        doc["volumes"].append({"series_keys": ks, "qid": None, "number": int(a["vol"]), "isbn13": isbn,
                               "release_date": rd_final, "pages": None, "publisher": a.get("publisher"),
                               "edition_type": "standard", "title_display": a.get("title"),
                               "source": "ndl-backward", "added_at": TODAY,
                               "note": f"後退蒸留A(NDL発見続巻・zokkan式ゲート通過) slug={slug}"})
        have4.add(isbn)
        st["nums"].add(a["vol"])
        st["isbns"].add(isbn)
        if cov:
            covers_add.append({"isbn13": isbn, "cover_url": cov})
        touched.add(slug)
        applied.append((slug, a["vol"], isbn, rd_final))
        expect = a["vol"] + 1

print(f"適用(S型) {len(applied)}巻 / 対象頁 {len(touched)} / hold {len(holds)}")
from collections import Counter
for k, n in Counter(h[0].split('_')[0] for h in holds).most_common():
    print(f"  hold {k}: {n}")
if DRY:
    print("(--dry: 書込なし)")
    for s, v, i, d in applied[:20]:
        print(f"  + {s} 巻{v} {i} {d}")
    sys.exit(0)

yaml.dump(doc, open(AUTO, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=200)
if covers_add:
    cp = os.path.join(ROOT, "data", "seeds", "covers.jsonl.gz")
    have_c = set()
    try:
        for l in gzip.open(cp, "rt", encoding="utf-8"):
            try:
                have_c.add(json.loads(l).get("isbn13"))
            except Exception:
                pass
    except Exception:
        pass
    with gzip.open(cp, "at", encoding="utf-8") as f:
        for c in covers_add:
            if c["isbn13"] not in have_c:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"covers seed追記 {len(covers_add)}")
tsv = os.path.join(ROOT, "docs", "production-diagnostics", f"backward-{YEAR}-a-holds.tsv")
with open(tsv, "w", encoding="utf-8") as f:
    f.write("type\tslug\tvol\tisbn\ttitle\tdate\n")
    for why, a in holds:
        f.write(f"{why}\t{a['slug']}\t{a['vol']}\t{a['isbn']}\t{str(a.get('title'))[:40]}\t{a.get('date')}\n")
json.dump(sorted(touched), open(os.path.join(ROOT, ".cache", "backward", YEAR, "a-touched.json"), "w"))
print(f"hold明細 → {tsv}")
print(f"次: python scripts/_reflect-targeted.py --only {','.join(sorted(touched)[:5])}{'...' if len(touched)>5 else ''} --push")

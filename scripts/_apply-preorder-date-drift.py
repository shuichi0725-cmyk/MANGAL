#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""発売日ドリフトの適用 (= `_audit-preorder-date-drift.py` の後段。 2026-09-04)

★機械ゲートで自動確定し、割れた分だけ人に回す(= CLAUDE.md の運転則)。
  楽天(店の現在値)と **NDL(ISBN直引きの出版予定日)** が **独立に一致** した行だけを適用する。
  初回実測: 芯31行のうち NDL が記録を持つ30行は **全て楽天と一致** = ドリフトは実在。

ゲート (全部通った行だけ適用):
  1. class が POSTPONED / ADVANCED / MINOR (= 日付が動いた)
  2. 楽天の値が YYYY-MM-DD (年・年月しか無い行は保留)
  3. ★NDL(isbn直引き)の出版予定日が楽天と一致 (NDL に記録が無い/食い違う = 保留)
  4. その ISBN が本番で 1頁1巻にしか無い (重複ISBNは isbn-dup 案件なので触らない)
  5. 未発売 (楽天の値 or 現在値が今日以降)。 ★既発売の巻は触らない
     (初版日/再版日の論争に踏み込まない = 別案件)
  6. fix_layer が PREORDER / SEED4 / SEED2。 ★CANONICAL / OVERRIDES は
     seed 本体の再構築が要るので保留 ([[release_date_change_side_effects]] ②)

書くもの (= 純粋追加 + 可逆):
  - data/seeds/release-date-override.jsonl に1行追記 (reason: preorder-date-drift)
    ★promote は本流でも予約頁合流でもこれを最優先で読む(2026-09-04 に予約側も結線済)
  - PREORDER 層は data/seeds/preorder-pages/<stem>.yml の release_date も同値に更新
    (= 恒久保管庫が古い値を持ち続けないように。 行単位の外科的置換=書式を壊さない)
  - SEED4 層は data/seeds/volumes-supplement*.yml の release_date も同値に更新
  - .cache/preorder-date-drift-stems.txt に対象 stem (= `_reflect-targeted.py --only` に渡す)
  - 保留は docs/production-diagnostics/preorder-date-drift-review.tsv に理由つきで

使い方:
  python scripts/_apply-preorder-date-drift.py             # dry-run (既定)
  python scripts/_apply-preorder-date-drift.py --apply
  python scripts/_apply-preorder-date-drift.py --no-ndl    # NDL照会を省く(既存キャッシュのみ)
"""
import argparse
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import _rate_gate  # ★プロセス間レートゲート(NDL 1.3s/req)

TSV = os.path.join(ROOT, "docs", "production-diagnostics", "preorder-date-drift.tsv")
REVIEW = os.path.join(ROOT, "docs", "production-diagnostics", "preorder-date-drift-review.tsv")
OVR = os.path.join(ROOT, "data", "seeds", "release-date-override.jsonl")
PRE_DIR = os.path.join(ROOT, "data", "seeds", "preorder-pages")
SEED4 = [os.path.join(ROOT, "data", "seeds", "volumes-supplement.yml"),
         os.path.join(ROOT, "data", "seeds", "volumes-supplement-auto.yml")]
NDL_CACHE = os.path.join(ROOT, ".cache", "preorder-date-drift-ndl.json")
STEMS = os.path.join(ROOT, ".cache", "preorder-date-drift-stems.txt")

NSS = {"dcterms": "http://purl.org/dc/terms/", "dcndl": "http://ndl.go.jp/dcndl/terms/",
       "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#"}


def ndl_issued(isbn: str):
    """NDL SRU を ISBN で引き、出版(予定)日を返す。 取れなければ None。
    ★200で0件だけが「無い」。 例外は None を返さず raise させて否定記録にしない
    ([[feedback_no_negative_record_on_failure]])。"""
    q = urllib.parse.urlencode({"operation": "searchRetrieve", "recordSchema": "dcndl",
                                "maximumRecords": "5", "query": 'isbn="%s"' % isbn})
    _rate_gate.wait("ndlsearch.ndl.go.jp", 1.3)
    req = urllib.request.Request("https://ndlsearch.ndl.go.jp/api/sru?" + q,
                                 headers={"User-Agent": "mangal/1.0"})
    x = urllib.request.urlopen(req, timeout=40).read().decode("utf-8")
    out = []
    for rd in ET.fromstring(x).iter("{http://www.loc.gov/zing/srw/}recordData"):
        try:
            rdf = ET.fromstring("".join(rd.itertext()))
        except Exception:
            continue
        for res in rdf.iter("{http://ndl.go.jp/dcndl/terms/}BibResource"):
            e = res.find("dcterms:issued", NSS)
            if e is None:
                continue
            v = e.find("rdf:Description/rdf:value", NSS)
            s = (v.text if v is not None and v.text else (e.text or "")).strip()
            t = res.find("dcterms:title", NSS)
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
                out.append({"issued": s, "title": (t.text or "") if t is not None else ""})
    return out


# ------------- 行単位の外科的置換 (書式を壊さない) -------------

def patch_release_date(path: str, isbn: str, new_date: str, window: int = 14):
    """`isbn13: 'X'` 行から **前方向にだけ** 走査し、同じ entry 内の release_date 行を new_date に。
    ★前後対称の窓だと隣の巻の release_date を拾って「候補2件」で降りてしまう(実測20件)。
      種2/種4/予約seed のどれも key 順は ... isbn13 → (cover_url/pages) → release_date なので
      前方向のみで一意に決まる。 次の entry の始まり(`- ` 始まり) か 次の isbn13 で打ち切る。
    戻り値 = (置換したか, 旧値, 情報)。"""
    lines = io.open(path, encoding="utf-8").read().split("\n")
    hits = [i for i, ln in enumerate(lines)
            if re.search(r"isbn13:\s*'?%s'?\s*$" % re.escape(isbn), ln)]
    if len(hits) != 1:
        return False, None, "isbn13 hits=%d" % len(hits)
    i = hits[0]
    j = None
    for k in range(i + 1, min(len(lines), i + 1 + window)):
        ln = lines[k]
        if re.match(r"\s*-\s", ln) or "isbn13:" in ln:
            break                      # 次の巻/entry に入った
        if re.match(r"\s*release_date:\s*", ln):
            j = k
            break
    if j is None:
        return False, None, "release_date が entry 内に無い"
    m = re.match(r"(\s*release_date:\s*)(.*)$", lines[j])
    old = m.group(2).strip().strip("'\"")
    lines[j] = "%s'%s'" % (m.group(1), new_date)
    io.open(path, "w", encoding="utf-8", newline="").write("\n".join(lines))
    return True, old, j + 1


def patch_years(path: str):
    """preorder-pages seed の year_started/year_ended を巻の年に追随させる。
    ★現在値が巻から導けている時だけ(手入力を壊さない)。 戻り値 = 変更内容 or None"""
    txt = io.open(path, encoding="utf-8").read()
    years = sorted({int(m) for m in re.findall(r"release_date:\s*'?(\d{4})-\d{2}-\d{2}'?", txt)})
    if not years:
        return None
    chg = {}
    for key, want in (("year_started", years[0]), ("year_ended", years[-1])):
        m = re.search(r"^(%s:\s*)(\d{4})\s*$" % key, txt, flags=re.M)
        if m and int(m.group(2)) != want:
            chg[key] = (int(m.group(2)), want)
            txt = txt[:m.start()] + "%s%d" % (m.group(1), want) + txt[m.end():]
    if chg:
        io.open(path, "w", encoding="utf-8", newline="").write(txt)
    return chg or None


def _origin_is_rakuten(stem: str, isbn: str) -> bool:
    """現在値が楽天由来か(= 同一源リフレッシュとして扱ってよいか)を seed の実物で確認する。
    PREORDER: preorder-pages/<stem>.yml の _note_origin が rakuten-preorder
    SEED4   : volumes-supplement*.yml の当該 entry の source が rakuten 系"""
    p = os.path.join(PRE_DIR, stem + ".yml")
    if os.path.exists(p):
        return "rakuten" in io.open(p, encoding="utf-8").read()
    for sp in SEED4:
        if not os.path.exists(sp):
            continue
        txt = io.open(sp, encoding="utf-8").read()
        i = txt.find("isbn13: '%s'" % isbn)
        if i >= 0:
            return "source: rakuten" in txt[i:i + 700]
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--no-ndl", action="store_true", help="NDL照会を省く(既存キャッシュのみ)")
    ap.add_argument("--allow-minor", action="store_true", default=True,
                    help="±3日のズレも適用する(既定=する。 源が同じ楽天のリフレッシュのため)")
    a = ap.parse_args()
    today = date.today().isoformat()

    rows = [l.rstrip("\n").split("\t") for l in io.open(TSV, encoding="utf-8")]
    hdr, rows = rows[0], rows[1:]
    I = {k: i for i, k in enumerate(hdr)}

    cand = [r for r in rows if r[I["class"]] in ("POSTPONED", "ADVANCED", "MINOR")]
    if not a.allow_minor:
        cand = [r for r in cand if r[I["class"]] != "MINOR"]
    print("候補 %d 行 (%s)" % (len(cand), Counter(r[I["class"]] for r in cand)))

    # ---- NDL 独立照会 ----
    ndl = {}
    if os.path.exists(NDL_CACHE):
        try:
            ndl = json.load(io.open(NDL_CACHE, encoding="utf-8"))
        except Exception:
            ndl = {}
    if not a.no_ndl:
        todo = sorted({r[I["isbn13"]] for r in cand} - set(ndl))
        print("NDL照会 %d 件 (キャッシュ %d)" % (len(todo), len(ndl)))
        for n, isbn in enumerate(todo, 1):
            ndl[isbn] = ndl_issued(isbn)          # ★例外は握り潰さない = 否定記録を作らない
            if n % 20 == 0:
                json.dump(ndl, io.open(NDL_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
                print("  ndl %d/%d" % (n, len(todo)))
        json.dump(ndl, io.open(NDL_CACHE, "w", encoding="utf-8"), ensure_ascii=False)

    # ---- ゲート ----
    ok, held = [], []
    for r in cand:
        isbn, ours, theirs = r[I["isbn13"]], r[I["ours"]], r[I["theirs"]]
        why = None
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", theirs or ""):
            why = "楽天の日付が日単位でない"
        elif r[I["fix_layer"]] in ("CANONICAL", "OVERRIDES"):
            why = "層=%s(seed本体の再構築が要る)" % r[I["fix_layer"]]
        elif r[I["n_pages_with_isbn"]] != "1":
            why = "同ISBNが%s頁に在る(isbn-dup案件)" % r[I["n_pages_with_isbn"]]
        elif not (theirs >= today or (ours and ours >= today)):
            why = "既発売(初版/再版の論争に踏み込まない)"
        else:
            hits = ndl.get(isbn)
            if hits is None:
                why = "NDL未照会"
            elif not hits:
                # ★NDL に記録が無い = 「食い違い」ではなく「まだ登録されていない」。
                #   現在値が **同じ楽天由来**(PREORDER seed / 種4 source:rakuten) なら、
                #   同一源の新しい読み値に差し替えるのは基準の混在ではなく単なる鮮度更新。
                #   古い値を握り続ける方が実害(発売済に見える)が大きいので採る。 印は残す。
                if r[I["fix_layer"]] in ("PREORDER", "SEED4") and _origin_is_rakuten(r[I["stem"]], isbn):
                    r.append("rakuten-only")      # 末尾に印(適用ログ用)
                else:
                    why = "NDLに記録なし かつ 現在値が楽天由来と確認できない"
            elif any(h.get("issued") == ours for h in hits):
                # ★NDL が **現在値** を支持している = 楽天だけが違う。
                #   実測(2026-09-04): KADOKAWA/秋田の ±1日 19件が全部この型。
                #   NDL/MADB = 奥付の発行日、 楽天 = 店頭に並ぶ日 で 1日ずれるのが正常。
                #   = ドリフト(古い値)ではないので **変更しない**。 月次で毎回浮くのを防ぐため型名を付ける。
                why = "奥付日vs店頭日(NDL=現在値%s / 楽天=%s)= 既知の仕様差・変更しない" % (ours, theirs)
            elif not any(h.get("issued") == theirs for h in hits):
                why = "NDL(%s)と楽天(%s)が食い違う(どちらも現在値と別)" % (
                    "/".join(sorted({h.get("issued", "") for h in hits})), theirs)
        (held if why else ok).append((r, why))

    print("\n適用可 %d / 保留 %d" % (len(ok), len(held)))
    for r, why in held:
        print("  [保留] %-46s %s %s->%s : %s" % (r[I["stem"]][:46], r[I["isbn13"]],
                                                 r[I["ours"]], r[I["theirs"]], why))

    if not a.apply:
        print("\n(dry-run。 適用は --apply)")
        for r, _ in ok[:15]:
            print("  [適用予定] %-10s %-44s %s %s -> %s" % (
                r[I["fix_layer"]], r[I["stem"]][:44], r[I["isbn13"]], r[I["ours"]], r[I["theirs"]]))
        if len(ok) > 15:
            print("  ... 他 %d 行" % (len(ok) - 15))
        _write_review(held, hdr, I)
        return

    # ---- 適用 ----
    stamp = date.today().isoformat()
    stems, ovr_lines, seedlog = set(), [], []
    for r, _ in ok:
        isbn, theirs, stem, layer = r[I["isbn13"]], r[I["theirs"]], r[I["stem"]], r[I["fix_layer"]]
        ovr_lines.append(json.dumps({
            "isbn13": isbn, "date": theirs, "slug": stem,
            "vol": int(r[I["vol"]]) if r[I["vol"]].isdigit() else None,
            "reason": "preorder-date-drift", "was": r[I["ours"]],
            "src": ("rakuten-only" if len(r) > len(hdr) else "rakuten+ndl"),
            "at": stamp}, ensure_ascii=False))
        stems.add(stem)
        if layer == "PREORDER":
            p = os.path.join(PRE_DIR, stem + ".yml")
            if os.path.exists(p):
                done, old, info = patch_release_date(p, isbn, theirs)
                seedlog.append(("preorder", stem, isbn, old, theirs, done, info))
                if done:
                    ch = patch_years(p)
                    if ch:
                        seedlog.append(("preorder-years", stem, "", "", str(ch), True, 0))
        elif layer == "SEED4":
            for p in SEED4:
                if not os.path.exists(p):
                    continue
                done, old, info = patch_release_date(p, isbn, theirs)
                if done or info != 0:
                    seedlog.append((os.path.basename(p), stem, isbn, old, theirs, done, info))
                if done:
                    break

    with io.open(OVR, "a", encoding="utf-8", newline="") as fh:
        for ln in ovr_lines:
            fh.write(ln + "\n")
    io.open(STEMS, "w", encoding="utf-8").write("\n".join(sorted(stems)))

    print("\n=== 適用 ===")
    print("  release-date-override.jsonl に %d 行追記" % len(ovr_lines))
    nfail = 0
    for src, stem, isbn, old, new, done, info in seedlog:
        if not done:
            nfail += 1
            print("  ! seed未更新 %-24s %-40s %s (hits=%s)" % (src, stem[:40], isbn, info))
    print("  seed直接更新 %d 件 (失敗 %d = override層だけで効かせる)" %
          (sum(1 for s in seedlog if s[5]), nfail))
    print("  対象 stem %d -> %s" % (len(stems), STEMS))
    _write_review(held, hdr, I)
    print("\n★次: python scripts/_reflect-targeted.py --only $(cat .cache/preorder-date-drift-stems.txt | tr '\\n' ',')")


def _write_review(held, hdr, I):
    os.makedirs(os.path.dirname(REVIEW), exist_ok=True)
    with io.open(REVIEW, "w", encoding="utf-8", newline="") as fh:
        fh.write("\t".join(["hold_reason"] + hdr) + "\n")
        for r, why in held:
            fh.write("\t".join([why] + r) + "\n")
    print("保留表: %s (%d 行)" % (REVIEW, len(held)))


if __name__ == "__main__":
    main()

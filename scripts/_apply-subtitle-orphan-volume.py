#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sugar&Spice型検出(_audit-subtitle-orphan-volume.py)の芯を機械ゲートで仕分け、通った巻を種4-autoへ純粋追加する。

★成り立ち (2026-09-03): ユーザ「1から順番にやって」で3段(override固定/別sid/取込もれ)+4段目(レーベル経験別名表)を
  scratchpad の使い捨てscriptで回した(合計 override8頁 / 別sid195巻 / 取込もれ643+371巻)。その判定を月次で
  使えるよう1本に統合したのが本script。**候補の列挙と自動適用の境界は下のゲート**で、通らない巻は理由つきで
  REVIEW一覧(docs/production-diagnostics/subtitle-orphan-volume-review.tsv)へ。人はそこだけ見る。

入力: 検出器の docs/production-diagnostics/subtitle-orphan-volume.tsv(芯= MISSING × tierA × EXACT × 疑なし × 除外seed外)
      + .cache/label-alias-pairs.json / .cache/rakuten-series-by-isbn.json(検出器が同時に生成)
      + .cache/db-v2.sqlite / .cache/isbn-page-index.json(先に _exists.py --build) / data/manga.v2

ゲート(全部満たす時だけ適用):
  L  レーベル整合: 正規化一致 or 経験別名表(同一ISBNを種2とRakutenが別名で呼ぶペア, sid>=3) or 自頁証拠(対象版の既存巻の
     楽天seriesNameと一致)。頁レーベル空=不明として通す(出版者記号一致は芯の前提)
  E  対象版: 楽天seriesNameに合う版 → 無ければ standard の最大巻版。主版が文庫/完全版だけの頁は見送り(原版の断片を作らない)
  D  発売日順: 番号>頁最大巻 → 日付≥「日付を持つ巻」の最大 / 穴 → 前後巻の間。無日付だけの頁は通す
  N  同番号が対象版に無い / ISBNが種2(ABSENT時)・本番・既存種4に無い
  K  頁の series_key がISBN逆引きで確定
  F  override(editions固定)/canonical 頁は見送り(種4が効かない=手で追記)
  SPLIT固有: 種2の版種がkeep / 種2番号が一致 or extra / アニメ系レーベル除外 / 0巻除外 / 続編題(SEQTITLE)は検出器側で疑済
  SPLIT掃引: 採択した種2 sid(+同著者・同正規化題の兄弟sid)の、楽天キャッシュに無かった続巻も同ゲートで拾う
  SAME_SID: 適用しない(0巻規則/page-dedup残骸/MADB誤番号= per-case)

使い方:
  python scripts/_apply-subtitle-orphan-volume.py            # dry-run(件数と理由、REVIEW一覧は書かない)
  python scripts/_apply-subtitle-orphan-volume.py --go       # 種4-auto へ純粋追加 + changelog + REVIEW一覧更新
  → 出力 .cache/subtitle-orphan-apply-stems.txt を `_reflect-targeted.py --only $(cat ...)` に渡して反映
"""
import argparse
import collections
import csv
import io
import json
import os
import re
import sqlite3
import sys
import unicodedata

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV = os.path.join(ROOT, "docs", "production-diagnostics", "subtitle-orphan-volume.tsv")
REVIEW = os.path.join(ROOT, "docs", "production-diagnostics", "subtitle-orphan-volume-review.tsv")
ALIAS = os.path.join(ROOT, ".cache", "label-alias-pairs.json")
RKSER = os.path.join(ROOT, ".cache", "rakuten-series-by-isbn.json")
DB = os.path.join(ROOT, ".cache", "db-v2.sqlite")
IDX = os.path.join(ROOT, ".cache", "isbn-page-index.json")
V2 = os.path.join(ROOT, "data", "manga.v2")
S4 = os.path.join(ROOT, "data", "seeds", "volumes-supplement.yml")
S4A = os.path.join(ROOT, "data", "seeds", "volumes-supplement-auto.yml")
OVR = os.path.join(ROOT, "data", "seeds", "edition-overrides.json")
CANON_DIR = os.path.join(ROOT, "data", "seeds", "edition-canonical")
CHANGELOG = os.path.join(ROOT, "data", "seeds", "volume-gaps-changelog.jsonl")
STEMS_OUT = os.path.join(ROOT, ".cache", "subtitle-orphan-apply-stems.txt")
KEEP = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban", "deluxe"}
SOURCES = [os.path.join(ROOT, ".cache", "rakuten-isbn-delta.jsonl"), os.path.join(ROOT, ".cache", "rakuten-isbn.jsonl")]

_PUNCT = re.compile(r"[\s　〜~！!?？・:：（）()【】\[\]「」『』\-‐−―。、．.=＆&＋+'’\"“”,，/／|｜]")


def norm(t):
    return _PUNCT.sub("", unicodedata.normalize("NFKC", str(t or "")).lower())


def imp_norm(t):
    return re.sub(r"コミックス?$", "", norm(t))


def parse_date(s):
    s = unicodedata.normalize("NFKC", str(s or ""))
    m = re.match(r"(\d{4})年(\d{1,2})月(?:(\d{1,2})日)?", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}" + (f"-{int(m.group(3)):02d}" if m.group(3) else "")
    m = re.match(r"(\d{4})-(\d{2})(?:-(\d{2}))?", s)
    return m.group(0) if m else ""


def month_index(d):
    """'YYYY-MM[-DD]' → 通し月(比較用)。不正は 0"""
    try:
        return int(d[:4]) * 12 + int(d[5:7])
    except Exception:
        return 0


def jp_registrant(isbn13):
    s = str(isbn13 or "")
    if not s.startswith("9784") or len(s) != 13:
        return s[:8]
    b = s[4:]
    n = int(b[:2])
    ln = 2 if n <= 19 else 3 if int(b[:3]) <= 699 else 4 if int(b[:4]) <= 8499 else 5 if int(b[:5]) <= 89999 else 6 if int(b[:6]) <= 949999 else 7
    return "9784" + b[:ln]


def yq(s):
    s = str(s)
    return "'" + s.replace("'", "''") + "'"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--today", default=None)
    a = ap.parse_args()
    import datetime
    today = a.today or datetime.date.today().isoformat()
    for p in (TSV, ALIAS, RKSER, IDX):
        if not os.path.exists(p):
            print(f"★abort: {p} が無い(先に _exists.py --build → _audit-subtitle-orphan-volume.py)")
            return 2
    rows = list(csv.DictReader(io.open(TSV, encoding="utf-8"), delimiter="\t"))
    core = [r for r in rows if r["巻状態"] != "OTHER_ISBN" and r["tier"] == "A" and r["一致"] == "EXACT"
            and not r["疑"] and r["除外seed"] != "Y"]
    print(f"芯 {len(core)}巻:", dict(collections.Counter(r['種2'] for r in core)))
    pairs = {tuple(k.split("||")): v for k, v in json.load(io.open(ALIAS, encoding="utf-8")).items()}
    rk_series = json.load(io.open(RKSER, encoding="utf-8"))
    idx = json.load(io.open(IDX, encoding="utf-8"))
    inv = collections.defaultdict(set)
    for isbn, slugs in idx.items():
        for s in slugs:
            inv[s].add(isbn)
    ovr = json.load(io.open(OVR, encoding="utf-8"))
    canon = {f[:-4] for f in os.listdir(CANON_DIR)} if os.path.isdir(CANON_DIR) else set()
    s4txt = io.open(S4, encoding="utf-8").read()
    s4atxt = io.open(S4A, encoding="utf-8").read()
    con = sqlite3.connect(DB)
    s2 = {}
    for isbn, sid, num, extra, etype, imp, rd, lab in con.execute(
            "SELECT v.isbn13, e.series_id, v.number, v.is_extra, e.type, e.imprint, v.release_date, v.volume_label "
            "FROM volumes v JOIN editions e ON e.id=v.edition_id WHERE v.isbn13 IS NOT NULL AND v.isbn13!=''"):
        s2.setdefault(isbn.replace("-", ""), (sid, num, extra, etype, imp or "", rd or "", lab or ""))
    s2title = dict(con.execute("SELECT id, title FROM series"))
    s2key = dict(con.execute("SELECT id, series_key FROM series"))

    # slug → stem(改名頁)
    stems = {f[:-4] for f in os.listdir(V2)}
    need = {r["slug"] for r in core}
    stem_of = {s: s for s in need if s in stems}
    miss = need - set(stem_of)
    if miss:
        for f in os.listdir(V2):
            st = f[:-4]
            if st in need:
                continue
            head = io.open(os.path.join(V2, f), encoding="utf-8", errors="replace").read(300)
            m = re.search(r"^slug: (.+)$", head, re.M)
            if m and m.group(1).strip().strip("'\"") in miss:
                stem_of[m.group(1).strip().strip("'\"")] = st

    pages = {}

    def page(slug):
        if slug in pages:
            return pages[slug]
        st = stem_of.get(slug)
        if not st:
            pages[slug] = None
            return None
        d = yaml.safe_load(io.open(os.path.join(V2, st + ".yml"), encoding="utf-8"))
        eds = []
        for e in d.get("editions") or []:
            vols = e.get("volumes") or []
            eds.append({"type": e.get("type"), "imprint": e.get("imprint") or "", "publisher": e.get("publisher") or "",
                        "nums": {v["number"] for v in vols if v.get("number") is not None},
                        "vols": [(v.get("number"), str(v.get("release_date") or ""), str(v.get("isbn13") or "")) for v in vols]})
        skeys, sids = set(), set()
        for isbn in inv.get(slug, ()):
            h = s2.get(isbn)
            if h:
                sids.add(h[0])
                skeys.add(s2key.get(h[0], ""))
        skeys.discard("")
        pages[slug] = {"stem": st, "title": d.get("title"), "eds": eds, "skeys": sorted(skeys), "sids": sids,
                       "frozen": bool((ovr.get(slug) or {}).get("editions")), "canon": st in canon or slug in canon,
                       "regs": {jp_registrant(i) for i in inv.get(slug, ())}}
        return pages[slug]

    def label_ok(e, rk):
        """(一致か, 根拠, 強さ) 強さ: 3=完全一致 2=別名表/自頁証拠 1=包含 0=空。
        ★包含一致は standard 版だけ・短い側4文字以上(カムナガラ: 'yk'⊂'ykコミックデラックス' で文庫/DX版に
        吸われ、呪いの招待状: 'ホラーm'⊂'ホラーmコミック文庫' で文庫版に吸われて日付逆行に化けた 2026-09-03)"""
        ei = imp_norm(e["imprint"])
        if not rk or not ei:
            return True, "空", 0
        if rk == ei:
            return True, "正規化一致", 3
        pv = pairs.get((ei, rk)) or pairs.get((rk, ei))
        if pv and pv[0] >= 3:
            return True, f"経験別名表({ei}⇔{rk}:{pv[0]}sid)", 2
        if rk in {rk_series.get(i) for _n, _d, i in e["vols"] if i}:
            return True, "自頁の既存巻の楽天seriesNameと一致", 2
        if e["type"] == "standard" and min(len(rk), len(ei)) >= 4 and (rk in ei or ei in rk):
            return True, "正規化包含", 1
        return False, "", 0

    accepted, review, sweep = [], [], []
    seen_isbn = set()
    accepted_sids = set()   # (slug, sid) for sweep

    def gate(r):
        """共通ゲート → (entry or None, why[], target)"""
        slug, num, isbn = r["slug"], int(r["抽出巻"]), r["isbn"]
        p = page(slug)
        why = []
        if p is None:
            return None, ["NOPAGE"], None
        rk = imp_norm(r["レーベル"])
        matched = [e for e in p["eds"] if label_ok(e, rk)[0] and label_ok(e, rk)[2] > 0]
        std = [e for e in p["eds"] if e["type"] == "standard"]
        main_all = max(p["eds"], key=lambda e: (max(e["nums"]) if e["nums"] else 0, len(e["nums"]))) if p["eds"] else None
        # 対象版 = 一致の強い版(完全一致>別名>包含)、同強度なら standard 優先、次いで最大巻
        target = (max(matched, key=lambda e: (label_ok(e, rk)[2], e["type"] == "standard", max(e["nums"]) if e["nums"] else 0)) if matched
                  else (max(std, key=lambda e: (max(e["nums"]) if e["nums"] else 0)) if std else None))
        ev = ""
        if target is None:
            why.append("E:standard版なし")
        else:
            ok, ev, _st = label_ok(target, rk)
            if not ok:
                why.append(f"L:レーベル不一致({r['レーベル']}≠{target['imprint']})")
            if main_all is not target and main_all and not matched and \
                    (max(main_all["nums"]) if main_all["nums"] else 0) > (max(target["nums"]) if target["nums"] else 0):
                why.append(f"E:主版が別版({main_all['type']})")
            nums, pmax = target["nums"], (max(target["nums"]) if target["nums"] else 0)
            dated = sorted((n, dt) for n, dt, _i in target["vols"] if dt and n is not None)
            rk_date = parse_date(r["発売日"])
            if num in nums:
                why.append("N:同番号既在")
            elif num > pmax:
                last_dt = max((dt for n, dt in dated if n <= pmax), default="")
                # ★1か月の許容: MADB(奥付月)と楽天(発売日)の月ずれ(一太郎ウオッ! 1巻=奥付1997-02/発売1997-01-21 と2巻同日刊)
                if last_dt and not (rk_date and month_index(rk_date) >= month_index(last_dt) - 1):
                    why.append(f"D:日付逆行({rk_date}<{last_dt[:7]} 頁側は後刷り日付の疑いも)")
            else:
                prev_dt = max((dt for n, dt in dated if n < num), default="")
                next_dt = min((dt for n, dt in dated if n > num), default="")
                if not (rk_date and (not prev_dt or rk_date[:7] >= prev_dt[:7]) and (not next_dt or rk_date[:7] <= next_dt[:7])):
                    why.append(f"D:穴の日付不整合({rk_date} vs {prev_dt[:7]}..{next_dt[:7]})")
        if not p["skeys"]:
            why.append("K:series_key bind不可")
        if p["frozen"]:
            why.append("F:override固定")
        if p["canon"]:
            why.append("F:canonical")
        if isbn in idx or isbn in s4txt or isbn in s4atxt or isbn in seen_isbn:
            why.append("N:ISBN既在")
        if r["種2"] == "ABSENT" and isbn in s2:
            why.append("N:種2に在る(検出器の索引が古い)")
        h = s2.get(isbn)
        if r["種2"] == "SPLIT" and h:
            sid, s2num, extra, etype, imp, rd, lab = h
            if etype not in KEEP:
                why.append(f"S:種2版種({etype})")
            if not (s2num == num or extra):
                why.append(f"S:種2番号不一致({s2num})")
            if re.search(r"アニメ|anime|フィルム", f"{imp} {r['レーベル']}", re.I):
                why.append("S:アニメ系レーベル")
            if num == 0:
                why.append("S:0巻")
        entry = None
        if not why:
            entry = {"slug": slug, "stem": p["stem"], "keys": p["skeys"], "number": num, "isbn": isbn,
                     "date": parse_date(r["発売日"]) or (h[5] if h else ""), "publisher": r["出版社"] or (target["publisher"] if target else ""),
                     "etype": target["type"] if target else "standard",
                     "title": r["楽天題"] + ((" " + r["楽天副題"]) if r["楽天副題"] else ""), "pmax": pmax if target else 0,
                     "kind": r["種2"], "ev": ev, "s2": h}
        return entry, why, target

    for r in core:
        if r["種2"] == "SAME_SID":
            review.append((r, ["SAME_SID(0巻規則/page-dedup残骸/MADB誤番号= per-case)"]))
            continue
        entry, why, target = gate(r)
        if entry:
            seen_isbn.add(entry["isbn"])
            if entry["kind"] == "SPLIT":
                sid = entry["s2"][0]
                entry["note"] = (f"Sugar&Spice型(分裂cluster): 種2 sid={sid} 題『{s2title.get(sid, '')}』number={entry['s2'][1]} extra={entry['s2'][2]} "
                                 f"imprint={entry['s2'][4]} に眠り本編頁と未結線。楽天= 『{r['楽天題']}』{r['楽天著者']}/{r['出版社']}/{r['レーベル']}/{entry['date']}。"
                                 f"レーベル={entry['ev']}。頁最終巻{entry['pmax']}")
                accepted_sids.add((r["slug"], sid, entry["s2"][4], target["imprint"] if target else "", entry["s2"][2]))
            else:
                entry["note"] = (f"MADB取込もれ(種2に当該ISBN無し)。楽天題が頁題+巻番号(完全一致)・著者一致・出版者記号一致・レーベル={entry['ev']}・"
                                 f"発売日順(頁最終巻{entry['pmax']}巻の後/穴の間)。楽天= {r['楽天著者']}/{r['出版社']}/{r['レーベル']}/{entry['date']}")
            accepted.append(entry)
        else:
            review.append((r, why))

    # SPLIT 掃引: 採択sid(+兄弟sid)の残り巻
    for slug, sid, s2imp, tgt_imp, extra in sorted(accepted_sids):
        if extra:
            continue
        p = page(slug)
        key = s2key.get(sid, "")
        author_part = key.split("|name:")[0]
        sibs = [x for (x, sk, st) in con.execute("SELECT id, series_key, title FROM series WHERE series_key LIKE ?", (author_part + "|name:%",))
                if norm(st) == norm(s2title.get(sid, ""))]
        tgt = [e for e in p["eds"] if imp_norm(e["imprint"]) == imp_norm(tgt_imp)]
        tgt = tgt[0] if tgt else None
        if tgt is None:
            continue
        nums = set(tgt["nums"]) | {e["number"] for e in accepted + sweep if e["slug"] == slug}
        pmax = max(tgt["nums"]) if tgt["nums"] else 0
        dated = [dt for n, dt, _i in tgt["vols"] if dt]
        last_dt = max(dated) if dated else ""
        cands = collections.defaultdict(list)
        for sb in sibs:
            for isbn, num, ex, etype, imp, rd, lab in con.execute(
                    "SELECT v.isbn13, v.number, v.is_extra, e.type, e.imprint, v.release_date, v.volume_label FROM volumes v JOIN editions e ON e.id=v.edition_id WHERE e.series_id=?", (sb,)):
                isbn = (isbn or "").replace("-", "")
                if not isbn or isbn in idx or isbn in seen_isbn or etype not in KEEP or ex or not num or num in nums:
                    continue
                if p["regs"] and jp_registrant(isbn) not in p["regs"]:
                    continue
                m = re.search(r"([^\s　]+?[編篇])", str(lab or ""))
                if m and norm(m.group(1)) not in norm(p["title"]):
                    continue
                if num > pmax and rd and last_dt and str(rd)[:7] < last_dt[:7]:
                    continue
                cands[num].append((0 if imp_norm(imp) == imp_norm(s2imp) else 1, str(rd or "9999"), isbn, imp or "", str(rd or ""), lab or "", sb))
        for num, cs in cands.items():
            cs.sort()
            _, _, isbn, imp, rd, lab, sb = cs[0]
            seen_isbn.add(isbn)
            sweep.append({"slug": slug, "stem": p["stem"], "keys": p["skeys"], "number": num, "isbn": isbn, "date": rd,
                          "publisher": tgt["publisher"], "etype": tgt["type"], "title": f"{p['title']} {num}", "kind": "SPLIT-sweep",
                          "note": f"同クラスタ掃引: 種2 sid={sb} 題『{s2title.get(sb, '')}』number={num} imprint={imp} label={lab} date={rd}。"
                                  f"楽天キャッシュ不在のため検出器は見なかったが、採択巻と同クラスタ・出版者記号一致・keep型・extra=0"})
    if sweep:
        want = {e["isbn"] for e in sweep}
        found = {}
        for fn in SOURCES:
            if not os.path.exists(fn):
                continue
            for line in io.open(fn, encoding="utf-8", errors="replace"):
                for w in want:
                    if w in line and w not in found:
                        try:
                            o = json.loads(line)
                        except Exception:
                            continue
                        if (o.get("isbn") or "").replace("-", "") == w:
                            found[w] = o.get("item") or {}
            if len(found) == len(want):
                break
        for e in sweep:
            it = found.get(e["isbn"])
            if it:
                d = parse_date(it.get("salesDate"))
                if d:
                    e["date"] = d
                if it.get("title"):
                    e["title"] = it["title"]
                e["note"] += f" 楽天= 『{it.get('title')}』{it.get('author')}/{it.get('publisherName')}/{it.get('seriesName')}/{it.get('salesDate')}"
    final = accepted + sweep
    print(f"適用可 {len(final)}巻 / 頁{len({e['slug'] for e in final})}:",
          dict(collections.Counter(e['kind'] for e in final)))
    print(f"REVIEW {len(review)}巻:")
    c = collections.Counter(" + ".join(sorted({re.sub(r'\(.*', '', w) for w in why})) for _r, why in review)
    for k, n in c.most_common():
        print(f"   {n:4d} {k}")
    if not a.go:
        print("(dry-run) --go で書き込み")
        return 0
    if final:
        lines = []
        for e in final:
            lines += ["- series_keys:"] + [f"  - {yq(k)}" for k in e["keys"]] + [
                "  qid: null", f"  number: {e['number']}", f"  isbn13: {yq(e['isbn'])}", f"  release_date: {yq(e['date'])}",
                f"  publisher: {yq(e['publisher'])}", f"  edition_type: {e['etype']}", f"  title_display: {yq(e['title'])}",
                f"  source: {'seed2-split-auto' if e['kind'].startswith('SPLIT') else 'rakuten-title-tail'}",
                f"  added_at: '{today}'", f"  note: {yq(e['note'])}"]
        raw = io.open(S4A, encoding="utf-8").read()
        assert raw.endswith("\n")
        bak = os.path.join(ROOT, ".cache", f"volumes-supplement-auto.yml.bak-sov-{today}")
        io.open(bak, "w", encoding="utf-8", newline="\n").write(raw)
        io.open(S4A, "a", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
        yaml.safe_load(io.open(S4A, encoding="utf-8"))
        with io.open(CHANGELOG, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({"op": "add-seed4-auto-subtitle-orphan", "count": len(final), "pages": len({e['slug'] for e in final}),
                                 "kinds": dict(collections.Counter(e['kind'] for e in final)),
                                 "reason": "_apply-subtitle-orphan-volume.py: Sugar&Spice型検出の芯を機械ゲート(レーベル整合/対象版/発売日順/同番号無し/ISBN未在/bind/override・canonical外)で一括登録",
                                 "at": today, "reversible": True, "backup": os.path.basename(bak)}, ensure_ascii=False) + "\n")
        print(f"種4-auto へ {len(final)}巻 追加(backup {os.path.basename(bak)})")
    io.open(STEMS_OUT, "w", encoding="utf-8").write(",".join(sorted({e["stem"] for e in final})))
    with io.open(REVIEW, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("slug\t頁題\t頁最大巻\t巻\tisbn\t発売日\t楽天題\t楽天副題\t楽天著者\t出版社\tレーベル\t種2\t見送り理由\n")
        for r, why in sorted(review, key=lambda x: (x[0]["slug"], int(x[0]["抽出巻"]))):
            fh.write("\t".join([r["slug"], r["頁題"], r["頁最大巻"], r["抽出巻"], r["isbn"], r["発売日"], r["楽天題"], r["楽天副題"],
                                r["楽天著者"], r["出版社"], r["レーベル"], r["種2"], " / ".join(why)]) + "\n")
    print(f"stems → {STEMS_OUT} / REVIEW → {REVIEW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

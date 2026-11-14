"""連載誌の保留(ledger_apply.py の HOLD)を、根拠の中身まで読んで解けるものだけ解く(2026-11-14 ユーザ「掲載誌の誤りと空欄を埋める」)。

  python scripts/magazine-verify/ledger_apply.py plan     # 先に今日の計画を作る(.cache/magazine-lists/ledger-apply-<今日>.json)
  python scripts/magazine-verify/ledger_apply2.py plan    # 解ける分 docs/production-diagnostics/magazine-ledger-apply2-<今日>.tsv(読むだけ)
  python scripts/magazine-verify/ledger_apply2.py apply   # magazine-corrections.yml へ末尾追記 + changelog + 反映用 stem 一覧

解く型(どれも「1誌に決まる」時だけ。 既に上書きのある頁・今の誌が根拠に在る頁は触らない):
  P1 出版社が合わない × MADB(初出欄 = その頁の巻そのものの記載 / 目次の本連載)        … 他社からの復刊・文庫。 誌は初出のまま
  P2 出版社が合わない × Wikipedia 作品記事 × 今は空欄 × 記事の掲載誌が1誌だけ(移籍なし) … 同上。 今の値が在る頁は別の漫画版のことがある = 触らない
  L1 Wiki一覧だけ × 一覧の行の先頭がその題 × 移籍・出張・並行の注記なし × 出版社が合う × 頁の開始年が連載開始より前でない
  S1 強い根拠が割れる → 一覧の当たりのうち「行の先頭がその題でない・移籍/出張/並行の注記つき」を外すと1誌に決まる
  S2 強い根拠が割れる → 2つ以上のソースが言う誌が1つだけで、他はどれも1ソース(増刊・出張掲載・読切)
  F0 ledger_apply.py の FILL / FIX(11/7 と同じ条件。 その後に台帳が増えて新しく当たった分)
"""
import datetime, importlib.util, json, os, re, shutil, sys, unicodedata
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ML = _load("ml", "scripts/_magazine-ledger.py")
LA = _load("la", "scripts/magazine-verify/ledger_apply.py")
import yaml

TODAY = datetime.date.today().isoformat()
BASE = os.path.join(ROOT, ".cache", "magazine-lists", f"ledger-apply-{TODAY}.json")
PLAN = os.path.join(ROOT, "docs", "production-diagnostics", f"magazine-ledger-apply2-{TODAY}.tsv")
PLAN_JSON = os.path.join(ROOT, ".cache", "magazine-lists", f"ledger-apply2-{TODAY}.json")
STEMS = os.path.join(ROOT, ".cache", "magazine-lists", f"stems-ledger2-{TODAY}.txt")
OLD_YEAR = 1995        # P2: 頁の開始年がこれ以前 = 復刊・他社版が普通の時代(新しい作品の社違いは「別の漫画版」のことがある: まおゆう・To Heart)
FOUNDED = {"ultra-jump": 1999, "jump-sq": 2007, "saikyo-jump": 2010, "shonen-jump-plus": 2014, "tonari-no-young-jump": 2012, "v-jump": 1993, "fresh-jump": 1982}
MOVE = re.compile(r"移籍|出張|並行|継続|読み切り|読切|再録|再掲")


def nz(s):
    return re.sub(r"[\s\W_]+", "", unicodedata.normalize("NFKC", str(s or "")).lower())


def row_is_title(ref, title):
    """一覧の行の「先頭の欄」がその題か(説明文の中に題が出ただけ・題が続く別作品は不可)。"""
    s = unicodedata.normalize("NFKC", ref or "")
    s = re.sub(r"^[\s*|!:;#]*(?:\d+\s*\|)?\s*", "", s)                     # 行頭の記号・通し番号
    s = re.sub(r"^[ぁ-ゖー・!?\s\d]+/\s*", "", s)                            # 「よみ/ 題」
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s).replace("'''", "").replace("''", "")
    t = nz(title)
    m = re.match(r"\s*『?(.+?)』?\s*(?:\|\||[((]|$)", s)
    return bool(m) and nz(m.group(1)) == t and len(t) >= 2


def list_year(ref):
    m = re.search(r"(19[4-9]\d|20[0-2]\d)", ref or "")
    return int(m.group(1)) if m else 0


def plan():
    if not os.path.exists(BASE):
        sys.exit("先に ledger_apply.py plan")
    base = json.load(open(BASE, encoding="utf-8"))
    pages = ML.load_pages()
    src = {k: ML.read_source(k) for k, _, _ in ML.SOURCES}
    MAG = ML.MAG
    corr = yaml.safe_load(open(LA.CORR, encoding="utf-8"))["corrections"]

    def hits(slug, key):
        rec = src[key][0].get(slug)
        return ML.clean_hits(rec[1]) if rec else []

    # 「単行本がたいてい他社から出る誌」(サイコミ・comico 等)= 既に根拠つきで上書き済みの頁が5つ以上あり、その半分以上で社が違う
    tot, dif = Counter(), Counter()
    for s_, v in corr.items():
        k_ = v.get("magazine")
        if s_ in pages and k_ in MAG and MAG[k_].get("publisher") and pages[s_]["pub"]:
            tot[k_] += 1
            dif[k_] += 0 if LA.same_pub(MAG[k_]["publisher"], pages[s_]["pub"]) else 1
    platform = {k_ for k_ in tot if tot[k_] >= 5 and dif[k_] * 2 >= tot[k_]} | {k_ for k_ in MAG if not MAG[k_].get("publisher")}
    print("他社から単行本が出る誌:", sorted(ML.magname(k_) for k_ in platform if tot[k_] >= 5))

    out, c = [], Counter()
    for r in base:
        slug, p = r["slug"], pages[r["slug"]]
        if r["action"] in ("FILL", "FIX"):
            out.append({**r, "rule": "F0"})
            c["F0"] += 1
            continue
        if r["action"] != "HOLD" or slug in corr:
            continue
        why, cur, pub, new, rule, ev = r["why"], r["cur"], r["pub"], "", "", ""
        E = ML.evidence_of(slug, src)
        if why.startswith("出版社"):
            k, srcs = r["new"], r["sources"].split("+")
            if any(s.startswith("madb") for s in srcs):
                hs = hits(slug, "madb-shoshutsu")
                # 初出欄が2誌以上を言う時は、一番多い誌が2番目の3倍以上(移籍・学年誌の並行連載を外す)
                if len(hs) < 2 or hs[0]["n"] >= 3 * hs[1]["n"]:
                    new, rule = k, "P1"
            elif not cur and "wiki-article" in srcs:
                ha = hits(slug, "wiki-article")
                exact = all(nz((h.get("ref") or "").split(": [[")[0]) == nz(p["title"]) for h in ha)
                if {h["mag"] for h in ha} == {k} and not E["weak"] and exact and ((p["year"] and p["year"] <= OLD_YEAR) or k in platform):
                    new, rule = k, "P2"
        elif why.startswith("根拠が Wiki"):
            k = r["new"]
            hl = [h for h in hits(slug, "wiki-list") if h["mag"] == k]
            ok = hl and all(row_is_title(h.get("ref"), p["title"]) and not MOVE.search(h.get("ref") or "") for h in hl)
            y = min([list_year(h.get("ref")) for h in hl if list_year(h.get("ref"))] or [0])
            if FOUNDED.get(k) and p["year"] and p["year"] < FOUNDED[k] - 1:
                ok = False
            if ok and not cur and LA.same_pub(MAG[k].get("publisher") or "", pub) and MAG[k].get("publisher") and pub \
                    and not E["weak"] and (not y or not p["year"] or p["year"] >= y - 1):
                new, rule = k, "L1"
        elif why.startswith("強い根拠が割れる") and cur not in E["strong"]:
            # S1: 一覧の当たりを厳しく読み直す
            bad = {h["mag"] for h in hits(slug, "wiki-list")
                   if not row_is_title(h.get("ref"), p["title"]) or MOVE.search(h.get("ref") or "")}
            by = {k: [s for s in v if not (s == "wiki-list" and k in bad)] for k, v in E["by_src"].items()}
            by = {k: v for k, v in by.items() if v}
            if len(by) == 1 and len(E["by_src"]) > 1:
                k = next(iter(by))
                if not k.startswith("?") and by[k] != ["wiki-list"]:
                    new, rule = k, "S1"
            if not new:
                multi = [k for k, v in by.items() if len(set(v)) >= 2]
                if len(multi) == 1 and not multi[0].startswith("?"):
                    new, rule = multi[0], "S2"
            if new and E["weak"] and new not in E["weak"]:
                new = rule = ""
        # 頁の出版社が「別の候補の誌」や「今の誌」の社と同じで、新しい誌の社とは違う = 移籍後の版・別の漫画版のことがある → 触らない
        if new and rule in ("S1", "S2", "P1"):
            others = [m for m in list(E["strong"]) + list(E["secondary"]) + ([cur] if cur else []) if m != new and m in MAG]
            np_ = MAG[new].get("publisher") or ""
            if pub and not (np_ and LA.same_pub(np_, pub)) and any((MAG[m].get("publisher") or "") and LA.same_pub(MAG[m]["publisher"], pub) and MAG[m].get("publisher") for m in others):
                new = rule = ""
        if not new or new == cur or new not in MAG:
            continue
        cols = {ML.SOURCES[i][0]: ML.SOURCES[i][1] for i in range(len(ML.SOURCES))}
        ev = " / ".join(f"{cols[s]}: {E['cells'][cols[s]]}" for s in dict.fromkeys(x for v in E["by_src"].values() for x in v))
        out.append({"action": "FILL" if not cur else "FIX", "rule": rule, "slug": slug, "stem": r["stem"], "title": r["title"], "pub": pub,
                    "cur": cur, "new": new, "sources": "+".join(E["by_src"][new]), "why": why, "ev": ev})
        c[rule] += 1
    json.dump(out, open(PLAN_JSON, "w", encoding="utf-8"), ensure_ascii=False)
    with open(PLAN, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# 連載誌の保留を解く計画 {TODAY}(scripts/magazine-verify/ledger_apply2.py)。 型は道具の先頭の説明\n")
        f.write("\t".join(["型", "action", "slug", "漫画名", "頁の開始年", "出版社", "今の連載誌", "新しい連載誌", "元の保留の理由", "根拠"]) + "\n")
        for r in sorted(out, key=lambda x: (x["rule"], x["slug"])):
            f.write("\t".join(str(v).replace("\t", " ").replace("\n", " ") for v in [
                r["rule"], r["action"], r["slug"], r["title"], pages[r["slug"]]["year"], r["pub"], ML.magname(r["cur"]), ML.magname(r["new"]), r.get("why", ""), r.get("ev", "")]) + "\n")
    print("解ける:", dict(c), "計", len(out), "/ 埋め", sum(1 for r in out if r["action"] == "FILL"), "直し", sum(1 for r in out if r["action"] == "FIX"))
    print("→", os.path.relpath(PLAN, ROOT))


def apply():
    rows = json.load(open(PLAN_JSON, encoding="utf-8"))
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = os.path.join(ROOT, ".cache", f"magazine-fix-bak-{ts}")
    os.makedirs(bak, exist_ok=True)
    shutil.copy2(LA.CORR, bak)
    txt = open(LA.CORR, encoding="utf-8").read()
    corr = yaml.safe_load(txt)["corrections"]
    n0 = len(corr)
    entries = {}
    for r in rows:
        if r["slug"] in corr:
            sys.exit(f"★{r['slug']} は既に上書きがある = 計画が古い。 plan からやり直す")
        ev = re.sub(r"\s+", " ", r["ev"])[:300] + f"。型 {r['rule']}・旧値 {r['cur'] or '空'}"
        entries[r["slug"]] = {"magazine": r["new"], "source": "ledger2:" + r["sources"], "evidence": ev, "added_at": TODAY}
    dumped = yaml.safe_dump(entries, allow_unicode=True, sort_keys=False, width=10000)
    dumped = "\n".join(("  " + ln) if ln else ln for ln in dumped.splitlines())
    txt = txt + ("" if txt.endswith("\n") else "\n") \
        + f"  # ★{TODAY} 保留を根拠の中身まで読んで解いた分(ユーザ「掲載誌の誤りと空欄を埋める」)。 型は scripts/magazine-verify/ledger_apply2.py の先頭\n" \
        + f"  #   計画表 = docs/production-diagnostics/magazine-ledger-apply2-{TODAY}.tsv\n" + dumped + "\n"
    chk = yaml.safe_load(txt)["corrections"]
    bad = [s for s, v in chk.items() if v["magazine"] not in ML.MAG]
    if bad or len(chk) != n0 + len(entries) or any(chk[s] != corr[s] for s in corr):
        sys.exit(f"★検算NG(マスタに無い誌 {bad[:5]} / 件数 {n0}+{len(entries)}≠{len(chk)} / 既存の上書きが変わった)= 中止")
    open(LA.CORR, "w", encoding="utf-8", newline="\n").write(txt)
    at = datetime.datetime.now().isoformat(timespec="seconds")
    with open(LA.LOG, "a", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps({"op": "magazine-correct", "slug": r["slug"], "title": r["title"], "before": r["cur"] or None, "after": r["new"],
                                "evidence": entries[r["slug"]]["evidence"], "tier": "ledger2-" + r["rule"],
                                "at": at, "via": "magazine-corrections.yml → _reflect-targeted --only-file",
                                "reversible": f"magazine-corrections.yml を退避 {os.path.relpath(bak, ROOT)} から戻して再反映"}, ensure_ascii=False) + "\n")
    open(STEMS, "w", encoding="utf-8", newline="\n").write("\n".join(sorted({r["stem"] for r in rows})) + "\n")
    print(f"書いた: {len(entries):,}頁(既存 {n0:,} は不変)/ 退避 {os.path.relpath(bak, ROOT)} / stems {os.path.relpath(STEMS, ROOT)}")


if __name__ == "__main__":
    {"plan": plan, "apply": apply}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()

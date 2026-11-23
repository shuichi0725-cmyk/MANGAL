#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NDL の役割つき著者表記(dc:creator「榊一郎 原作」「水田ケンジ 漫画」)で、頁の著者の役割と抜けを直す案を作る。

2026-11-23 新設(月次1.2.22 ユーザ「このまま進めて」)。
背景: MADB の NDL 由来レコード(dataPublisher=NDLサーチ)は schema:creator に役割語が無い。
  rolecredits / author-role-corrections は生MADBの[原作]タグから作るので拾えず、種2の既定 writer_artist のまま
  = [[feedback_never_default_author_role]] に反する状態(2人以上・全員 writer_artist・原作欄空 = 3,522頁)。
  NDL の dc:creator には役割語が残っているので、頁の巻の ISBN で NDL を引き直して役割を決める。

使い方:
  python scripts/_ndl-author-roles.py scan [--slugs a,b] [--all] [--limit N]   # NDL照会(1.2秒/回・再開可)→ .cache/ndl-author-roles/
  python scripts/_ndl-author-roles.py plan                                      # 照会結果 → 自動適用案 / 見直し表(TSV)
  python scripts/_ndl-author-roles.py apply                                     # 自動適用案を data/seeds/author-overrides.json に純粋追加
判定(偽適用より偽保留):
  - うちの著者が全員 NDL の名前(1巻・無ければ最終巻も)に居る → 自動(役割は NDL・NDL にだけ居る漫画/原作の人は足す)
  - うちの著者に NDL に居ない名前がある(別人化・外国名の表記違い等) → 見直し(書かない)
  - 既に author-overrides.json に在る slug は触らない(手の裁定が先)
役割語: 原作/脚本/作/シナリオ/ストーリー=writer(→original_authors) / 漫画/作画/画/まんが/絵=artist /
  著・役割なし=writer_artist(原作の人が別に居れば artist) / 構成・監修・キャラクター原案・原案・原作イラスト・編・訳 等=credits
"""
import os, re, sys, json, time, argparse, importlib.util, unicodedata

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MV2 = os.path.join(ROOT, "data", "manga.v2")
OUT = os.path.join(ROOT, ".cache", "ndl-author-roles")
os.makedirs(OUT, exist_ok=True)
SCAN = os.path.join(OUT, "scan.jsonl")
OVR = os.path.join(ROOT, "data", "seeds", "author-overrides.json")
PLAN = os.path.join(OUT, "plan.json")
REVIEW = os.path.join(ROOT, "docs", "production-diagnostics", "ndl-author-roles-review.tsv")

WRITER = ("原作", "脚本", "シナリオ", "ストーリー", "原作・脚本")
ARTIST = ("漫画", "作画", "画", "まんが", "マンガ", "絵", "コミカライズ")
CREDIT_HINT = ("構成", "監修", "キャラクター原案", "キャラクターデザイン", "原案", "原作イラスト", "イラスト", "編", "編集",
               "訳", "翻訳", "解説", "協力", "企画", "考案", "デザイン", "取材", "資料", "写真", "協賛", "校閲", "文")


def _lk():
    sp = importlib.util.spec_from_file_location("lk", os.path.join(ROOT, "scripts", "_lookup.py"))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or ""))
    return re.sub(r"[\s・,、。.･'’\-‐]", "", s).lower()


def parse_creator(raw):
    """「春原ロビンソン, 筒井大志 著」→ [(name, roleword)]。 役割語は末尾の語。"""
    raw = unicodedata.normalize("NFKC", raw).strip()
    m = re.match(r"^(.*?)\s+(\S+)$", raw)
    names, role = (m.group(1), m.group(2)) if m else (raw, "")
    # 役割語に見えない末尾(人名の一部)なら役割なし
    if role and not any(w in role for w in WRITER + ARTIST + CREDIT_HINT + ("著", "作")):
        names, role = raw, ""
    return [(n.strip(), role) for n in re.split(r",\s*", names) if n.strip()]


def classify(role):
    if not role or role in ("著", "作・画", "作画・原作", "文・絵", "著・画"):
        return "main"
    if "キャラクター" in role or "イラスト" in role:
        return "credit"
    if any(w in role for w in WRITER) or role == "作":
        return "writer"
    if any(w in role for w in ARTIST):
        return "artist"
    return "credit"


def page_targets(slugs=None, all_=False):
    out = []
    files = [f"{s}.yml" for s in slugs] if slugs else sorted(f for f in os.listdir(MV2) if f.endswith(".yml"))
    for f in files:
        p = os.path.join(MV2, f)
        if not os.path.exists(p):
            continue
        s = open(p, encoding="utf-8").read()
        m = re.search(r"^authors:\n((?:[- ] .*\n)+)", s, re.M)
        if not m:
            continue
        names = re.findall(r"^- name: (.+)$", m.group(1), re.M)
        roles = re.findall(r"role: (\S+)", m.group(1))
        o = re.search(r"^original_authors: (\[\])?", s, re.M)
        if not slugs:
            if not (len(roles) >= 2 and all(r == "writer_artist" for r in roles) and o and o.group(1)):
                continue
        isbns = re.findall(r"^\s+isbn13: '?(\d{13})'?", s, re.M)
        nums = re.findall(r"^\s+- number: (\S+)", s, re.M)
        slug = re.search(r"^slug: (\S+)", s, re.M).group(1)
        out.append({"stem": f[:-4], "slug": slug, "names": [n.strip().strip("'\"") for n in names],
                    "first": isbns[0] if isbns else None, "last": isbns[-1] if isbns else None})
    return out


def scan(a):
    L = _lk()
    done = set()
    if os.path.exists(SCAN):
        done = {json.loads(l)["stem"] for l in open(SCAN, encoding="utf-8")}
    T = page_targets(a.slugs.split(",") if a.slugs else None, a.all)
    T = [t for t in T if t["stem"] not in done and t["first"]]
    if a.limit:
        T = T[:a.limit]
    print(f"照会対象 {len(T)} 頁(済 {len(done)})", flush=True)
    t0 = time.time()
    with open(SCAN, "a", encoding="utf-8") as fo:
        for n, t in enumerate(T, 1):
            rec = {**t, "ndl": {}}
            for which in ("first", "last"):
                i = t[which]
                if which == "last" and (i == t["first"]):
                    continue
                if which == "last":
                    # 1巻でうちの著者が揃えば最終巻は引かない(回数の節約)
                    if rec["ndl"].get(t["first"]) is None:
                        continue  # 1巻の照会が失敗 = この頁は記録しない(次回取り直し)
                    got = {norm(nm) for c in rec["ndl"].get(t["first"]) or [] for nm, _ in parse_creator(c)}
                    if all(norm(x) in got for x in t["names"]):
                        continue
                try:
                    r = L.ndl_live_retry(f'isbn="{i}"', maximum=3)
                except SystemExit:
                    print("NDL 429/停止 → 中断(再開可)", flush=True); return
                except Exception as e:  # noqa: BLE001
                    if "429" in str(e) or "403" in str(e):
                        print(f"NDL {str(e)[:40]} → 即停止(再開可・規則: 429は止める)", flush=True); return
                    r = None
                    print(f"  {t['stem']}: NDL失敗 {str(e)[:60]}", flush=True)
                if r is None:
                    rec["ndl"][i] = None
                else:
                    rec["ndl"][i] = (r[0].get("creators_raw") if r else [])
            if any(v is None for v in rec["ndl"].values()):
                continue  # ★失敗は記録しない(否定記録にしない)= 次回取り直し
            fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fo.flush()
            if n % 100 == 0:
                print(f"[{time.strftime('%H:%M')}] {n}/{len(T)} {(time.time() - t0) / n:.1f}秒/頁", flush=True)
    print("照会おわり", flush=True)


def decide(rec):
    people = {}   # norm -> {name, kinds}
    for i, raws in rec["ndl"].items():
        for raw in raws or []:
            for nm, role in parse_creator(raw):
                k = norm(nm)
                if not k:
                    continue
                p = people.setdefault(k, {"name": nm, "kinds": set(), "roles": set()})
                p["kinds"].add(classify(role)); p["roles"].add(role)
    if not people:
        return None, "NDLに著者なし"
    ours = [norm(x) for x in rec["names"]]
    missing = [rec["names"][j] for j, k in enumerate(ours) if k not in people]
    if missing:
        return None, "うちの著者がNDLに無い: " + "/".join(missing) + " | NDL: " + "/".join(f"{p['name']}({'・'.join(sorted(r or '著' for r in p['roles']))})" for p in people.values())
    has_writer = any("writer" in p["kinds"] for p in people.values())
    authors, credits = [], []
    for k, p in people.items():
        ks = p["kinds"]
        # 我々の名前表記を優先(既存の索引・ヨミと繋がる)
        nm = next((rec["names"][j] for j, o in enumerate(ours) if o == k), p["name"])
        if "writer" in ks and ("artist" in ks or "main" in ks and not has_writer):
            authors.append({"name": nm, "role": "writer_artist"})
        elif "writer" in ks:
            authors.append({"name": nm, "role": "writer"})
        elif "artist" in ks or "main" in ks:
            authors.append({"name": nm, "role": "artist" if has_writer else "writer_artist"})
        else:
            credits.append({"name": nm, "role": "・".join(sorted(r for r in p["roles"] if r)) or "協力"})
    if not any(a["role"] in ("artist", "writer_artist") for a in authors):
        return None, "作画側が決まらない | " + "/".join(f"{p['name']}({'・'.join(sorted(p['roles']))})" for p in people.values())
    if all(a["role"] == "writer_artist" for a in authors) and not credits and len(authors) == len(rec["names"]):
        return {"same": True}, "NDLも共著(writer_artist)=変更なし"
    return {"authors": authors, "credits": credits}, ""


def plan(a):
    ovr = json.load(open(OVR, encoding="utf-8"))
    recs = {}
    for l in open(SCAN, encoding="utf-8"):
        r = json.loads(l); recs[r["stem"]] = r
    auto, rev, same, skip = {}, [], 0, 0
    for st, r in recs.items():
        if r["slug"] in ovr:
            skip += 1; continue
        d, why = decide(r)
        if d is None:
            rev.append((r["slug"], r["stem"], "|".join(r["names"]), why)); continue
        if d.get("same"):
            same += 1; continue
        auto[r["slug"]] = {**d, "_src": "ndl-author-roles 2026-11-23", "_isbn": [i for i in r["ndl"]]}
    json.dump(auto, open(PLAN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(REVIEW, "w", encoding="utf-8") as f:
        f.write("slug\tstem\tうちの著者\t理由\n")
        for x in rev:
            f.write("\t".join(x) + "\n")
    print(f"照会済 {len(recs)} / 自動 {len(auto)} / 変更なし(共著) {same} / 見直し {len(rev)} / 既にoverrideあり {skip}")
    print(f"→ {PLAN}\n→ {REVIEW}")


def apply(a):
    ovr = json.load(open(OVR, encoding="utf-8"))
    auto = json.load(open(PLAN, encoding="utf-8"))
    bak = os.path.join(ROOT, ".cache", f"author-overrides.json.bak-{time.strftime('%Y%m%d-%H%M%S')}")  # ★seedsに置かない
    open(bak, "w", encoding="utf-8").write(json.dumps(ovr, ensure_ascii=False, indent=1))
    n = 0
    for slug, d in auto.items():
        if slug in ovr:
            continue
        ovr[slug] = d; n += 1
    json.dump(ovr, open(OVR, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log = os.path.join(ROOT, "data", "seeds", "author-overrides-changelog.jsonl")
    with open(log, "a", encoding="utf-8") as f:
        for slug, d in auto.items():
            f.write(json.dumps({"op": "ndl-author-roles", "slug": slug, "after": d, "at": time.strftime("%Y-%m-%d"),
                                "revert": "author-overrides.json から slug を外す", "backup": os.path.relpath(bak, ROOT)},
                               ensure_ascii=False) + "\n")
    print(f"author-overrides.json に {n} slug 追加(退避 {bak})")
    open(os.path.join(OUT, "applied-stems.txt"), "w", encoding="utf-8").write(
        "\n".join(r["stem"] for r in map(json.loads, open(SCAN, encoding="utf-8")) if r["slug"] in auto))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("--slugs"); s.add_argument("--all", action="store_true"); s.add_argument("--limit", type=int, default=0)
    sub.add_parser("plan"); sub.add_parser("apply")
    a = ap.parse_args()
    {"scan": scan, "plan": plan, "apply": apply}[a.cmd](a)


if __name__ == "__main__":
    main()

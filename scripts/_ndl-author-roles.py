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
import os, re, sys, json, time, argparse, importlib.util, unicodedata, html

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MV2 = os.path.join(ROOT, "data", "manga.v2")
OUT = os.path.join(ROOT, ".cache", "ndl-author-roles")
os.makedirs(OUT, exist_ok=True)
SCAN = os.path.join(OUT, "scan.jsonl")
OVR = os.path.join(ROOT, "data", "seeds", "author-overrides.json")
PLAN = os.path.join(OUT, "plan.json")
REVIEW = os.path.join(ROOT, "docs", "production-diagnostics", "ndl-author-roles-review.tsv")

WRITER = ("原作", "脚本", "脚色", "シナリオ", "ストーリー", "原作・脚本")
ARTIST = ("漫画", "作画", "画", "まんが", "マンガ", "絵", "コミカライズ")
CREDIT_HINT = ("構成", "監修", "キャラクター原案", "キャラクターデザイン", "原案", "原作イラスト", "イラスト", "編", "編集",
               "訳", "翻訳", "解説", "協力", "企画", "考案", "デザイン", "取材", "資料", "写真", "協賛", "校閲", "文",
               "指導", "その他", "著作", "原著", "装幀", "装丁", "装画", "制作")
EN_ROLE = {"Art": "漫画", "Story": "原作", "art": "漫画", "story": "原作"}  # 「たむろ未知 Art」型(2026-11-27 実踏)
MANY_AUTHORS = 6  # これより多い頁(合同誌・アンソロジー型)は自動にしない=見直しへ


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
    raw = unicodedata.normalize("NFKC", html.unescape(html.unescape(raw))).strip()
    m = re.match(r"^(.*?)\s*/\s*([^/\s]+)$", raw)   # 「うえやま とち/著」型(名前に/を含む「yui/サウスのサウス」は役割語でないので残る)
    if m and _is_role(m.group(2)):
        names, role = m.group(1), m.group(2)
    else:
        m = re.match(r"^(.*?)\s+(\S+)$", raw)
        names, role = (m.group(1), m.group(2)) if m else (raw, "")
    role = re.sub(r"[\[\]()]", "", role)
    role = EN_ROLE.get(role, role)
    # 役割語に見えない末尾(人名の一部)なら役割なし
    if role and not _is_role(role):
        names, role = raw, ""
    return [(n.strip(), role) for n in re.split(r",\s*", names) if n.strip()]


ROLE_TAILS = WRITER + ARTIST + CREDIT_HINT + ("著", "作", "共著", "著者", "イラストレーター", "デザイナー", "原作者")


def _is_role(w):
    """役割語か(各「・」区切りの部分が役割語で終わる)。 「絵美」「とち」のような名前の一部は役割語にしない。"""
    w = re.sub(r"[\[\]()]", "", w)
    if w in EN_ROLE:
        return True
    parts = [x for x in w.split("・") if x]
    return bool(parts) and all(any(x.endswith(t) for t in ROLE_TAILS) for x in parts)


def classify(role):
    """役割語を「・」で割り、部分ごとに 著/原作側/作画側/協力 を決めて合成する(「企画」の「画」を作画と読まない)。"""
    if not role or role in ("文・絵", "作・絵", "著・画"):
        return "main"
    kinds = set()
    for x in [y for y in role.split("・") if y]:
        if x in ("著", "共著", "著者") or x.endswith("著") and not x.endswith("原著"):
            kinds.add("main")
        elif "キャラクター" in x or "イラスト" in x:
            kinds.add("credit")
        elif x in ("作", "原著", "原著作") or any(x.endswith(w) for w in WRITER):
            kinds.add("writer")
        elif x == "画" or any(x.endswith(w) for w in ARTIST if w != "画"):
            kinds.add("artist")
        else:
            kinds.add("credit")
    if "main" in kinds or {"writer", "artist"} <= kinds:
        return "main"
    for k in ("writer", "artist"):
        if k in kinds:
            return k
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


def scan_dump(a):
    """NDL 全件ダウンロード(_ndl-dump-extract.py の .cache/ndl-dump/extract)から dc:creator を引く = NDL に1回も照会しない。
    2026-11-24 新設(opensearch が 429 続きで 2,471頁が残った)。 live の creators_raw と同じ dc:creator 文字列。
    ダンプに無い ISBN の頁は記録しない(否定記録にしない)= 後で live scan が拾える。"""
    import gzip, glob
    idx = {}
    for f in sorted(glob.glob(os.path.join(ROOT, ".cache", "ndl-dump", "extract", "*.jsonl.gz"))):
        for l in gzip.open(f, "rt", encoding="utf-8"):
            r = json.loads(l)
            dc = r.get("dc_creator") or []
            for i in r.get("isbn") or []:
                cur = idx.setdefault(i, [])
                for c in dc:
                    if c not in cur:
                        cur.append(c)
    print(f"ダンプ索引 ISBN {len(idx)}", flush=True)
    done = set()
    if os.path.exists(SCAN):
        done = {json.loads(l)["stem"] for l in open(SCAN, encoding="utf-8")}
    T = page_targets(a.slugs.split(",") if a.slugs else None, a.all)
    T = [t for t in T if t["stem"] not in done and t["first"]]
    print(f"対象 {len(T)} 頁(済 {len(done)})", flush=True)
    hit = miss = 0
    with open(SCAN, "a", encoding="utf-8") as fo:
        for t in T:
            if t["first"] not in idx:
                miss += 1
                continue
            rec = {**t, "ndl": {t["first"]: idx[t["first"]]}, "src": "ndl-dump-20261107"}
            got = {norm(nm) for c in idx[t["first"]] for nm, _ in parse_creator(c)}
            if t["last"] and t["last"] != t["first"] and not all(norm(x) in got for x in t["names"]) and t["last"] in idx:
                rec["ndl"][t["last"]] = idx[t["last"]]
            fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
            hit += 1
    print(f"記録 {hit} 頁 / ダンプに1巻なし {miss} 頁(未記録=live で後日)", flush=True)


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
    # 「Dr.モロー&スタジオ寿」型 = 区切りで割った全部がうちの著者なら割る
    for k in list(people):
        parts = [x for x in re.split(r"[&＆]", people[k]["name"]) if x.strip()]
        if len(parts) > 1 and all(norm(x) in ours for x in parts):
            p0 = people.pop(k)
            for x in parts:
                q = people.setdefault(norm(x), {"name": x.strip(), "kinds": set(), "roles": set()})
                q["kinds"] |= p0["kinds"]; q["roles"] |= p0["roles"]
    odd = [p["name"] for p in people.values() if re.search(r"[&＆;；]|[Ѐ-ӿ]|ほか$|他$|著$", p["name"].strip())]
    if odd:
        return None, "NDLの名前表記が変則(割れない&・キリル文字等): " + "/".join(odd)
    if len(people) > MANY_AUTHORS:
        return None, f"著者が{len(people)}人(合同誌・アンソロジー型)=自動にしない"
    missing = [rec["names"][j] for j, k in enumerate(ours) if k not in people]
    if missing:
        return None, "うちの著者がNDLに無い: " + "/".join(missing) + " | NDL: " + "/".join(f"{p['name']}({'・'.join(sorted(r or '著' for r in p['roles']))})" for p in people.values())
    # NDLにだけ居る名前に空白が残る(役割語を割れなかった「伊藤博 装幀」型)・団体名(「コミックス 編」型)=見直しへ(2026-11-27 実踏)
    bad = [p["name"] for k, p in people.items() if k not in ours and (re.search(r"\s", p["name"].strip()) or re.search(r"(コミックス|編集部|プロダクション)$", p["name"].strip()))]
    if bad:
        return None, "NDLにだけ居る名前が変則(役割語の割り残し・団体名): " + "/".join(bad)
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
            ck = norm(re.sub(r"[(（].*?[)）]", "", nm))
            if any(norm(re.sub(r"[(（].*?[)）]", "", c["name"])) == ck for c in credits):
                continue  # 「川島健三(水野プロ)」と「川島健三」の二重(1巻と最終巻で表記違い)
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
    s = sub.add_parser("scan-dump"); s.add_argument("--slugs"); s.add_argument("--all", action="store_true")
    sub.add_parser("plan"); sub.add_parser("apply")
    a = ap.parse_args()
    {"scan": scan, "scan-dump": scan_dump, "plan": plan, "apply": apply}[a.cmd](a)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""7/24 月次(MADB 1.2.18・commit 1e107d9a4)の種4-auto全消しで消えたまま戻っていない巻を復元する。

2026-10-06 発見(mangaseek の発売日一覧との突き合わせ): 1e107d9a4 で volumes-supplement-auto.yml が
30,058行→`volumes: []` に全消し(2,691 ISBN)。8/26 の復元は 8d02dbf88~1(=8/21直前)からだったので
7/24 分は対象外だった。多くは別経路(MADB取込・巻抜け充填・保留見直し)で戻ったが、
頁にも種2にも種4にも無いものが残っている(=日次は「前回から増えたISBN」しか見ないので二度と拾われない)。
消えた中身 = 7/11 の stale-backfill(本番に出ていたのに seed の裏付けが無かった巻の固定)/ 楽天予約の続巻 / NDL巻抜け補完。

  python scripts/_restore-seed4-wipe-0724.py --plan    # 候補+ゲート+楽天live照合 → TSV と plan(seedは書かない)
  python scripts/_restore-seed4-wipe-0724.py --apply   # plan の RESTORE 行だけ種4-autoへ純粋追加(+covers seed・changelog・touched)

ゲート(_preorder-apply-zokkan.py と同じ検問+楽天照合):
 ①ISBNが本番頁/種2/種4(auto・手動・offset)/除外簿・退役簿のどこにも無い
 ②行き先の頁が一意に決まる(元noteのslug→SRC stem、無ければ元series_keys→種2→ISBN索引)
 ③手で巻を固定した頁(edition-overridesのeditions / edition-canonical)と予約頁(preorder-pages)は
   種4が効かない → 保留(per-case で本体へ)
 ④series_keys = 元の鍵が今も種2に在りその頁に当たればそれ、無ければ頁のISBNから逆引き(apply-zokkan と同じ)
 ⑤同じ版typeに同巻番号が既在 / 種4に同巻番号(鍵が重なる)既在 / 特装版・限定版 → 保留
 ⑥楽天live(ISBN・outOfStockFlag=1)で実在・題(頁題を含む)・著者overlap・巻番号・漫画ジャンルを照合。
   発売日と書影は楽天の今の値を使う(7月の予約日は延期で動いている可能性がある=すてごろ型)
出力: docs/production-diagnostics/seed4-restore-0724.tsv / .cache/seed4-restore-0724-plan.json
"""
import sys as _sys_h
if any(_a in ("-h", "--help") for _a in _sys_h.argv[1:]):   # --help で本体を走らせない
    print(__doc__); _sys_h.exit(0)
import collections, datetime, functools, gzip, json, os, re, shutil, sqlite3, subprocess, sys, unicodedata
sys.stdout.reconfigure(encoding="utf-8")
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import _lookup as LK  # 楽天live は _lookup.py の実装を使う(再実装しない)

WIPE_COMMIT = "1e107d9a4"
SEEDS = os.path.join(ROOT, "data", "seeds")
AUTO = os.path.join(SEEDS, "volumes-supplement-auto.yml")
SUPP = os.path.join(SEEDS, "volumes-supplement.yml")
OFFS = os.path.join(SEEDS, "volumes-supplement-offset.yml")
PLAN = os.path.join(ROOT, ".cache", "seed4-restore-0724-plan.json")
TSV = os.path.join(ROOT, "docs", "production-diagnostics", "seed4-restore-0724.tsv")
LOG = os.path.join(SEEDS, "seed4-restore-changelog.jsonl")
TOUCHED = os.path.join(ROOT, ".cache", "seed4-restore-0724-touched.txt")
COVERS = os.path.join(SEEDS, "covers.jsonl.gz")
TODAY = datetime.date.today().isoformat()
# apply-zokkan と同じ特装版判定(通常版ISBNだけを足す)
SPECIAL_ED = re.compile(r"特装版|限定版|初回限定|豪華版|特別版|特典付|小冊子付|ドラマCD|CD付|DVD付|Blu-?ray|OAD|アクリル|しおり付|カードセット付|ポストカード|クリアスタンド|キーホルダー|フィギュア付", re.I)
# 楽天照合を通っても戻さない(目で見て別物と確かめた行)。理由は TSV にそのまま出す
HOLD_MANUAL = {
    "9784041175750": "博多編=別シリーズ。頁 angorumoa が元寇合戦記1-10+博多編11-12の版混在(頁の分離が先)",
}
EXCLUDE_FILES = ["volume-exclude.yml", "volume-exclude-isbn.yml", "art-book-exclude-isbn.yml", "preorder-deny.jsonl",
                 "anthology-drop.tsv", "american-comics-drop.tsv", "distill-drop-2026.tsv", "non-manga-drop.yml",
                 "company-nonmanga-drop.json", "magazines-drop.yml", "volumes-supplement-retire-changelog.jsonl"]


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    return re.sub(r"[\s・!?！？〜~ー\-—()（）【】《》〈〉「」『』:：,，.。、/／'\"’”♡♥☆★…‥&＆]", "", s)


def norm_person(s):
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = re.sub(r"[（(][^）)]*[）)]", "", s)          # (原作) (漫画) 等の役割注記
    return re.sub(r"[\s・=＝]", "", s)


def seed_isbns(path):
    if not os.path.exists(path):
        return set()
    d = yaml.safe_load(open(path, encoding="utf-8")) or {}
    return {str(v.get("isbn13")) for v in (d.get("volumes") or []) if v.get("isbn13")}


def load_pub2stem():
    """公開slug→SRC stem(slug-overrides.yml)。apply-zokkan / _gen-shinkan-data.py と同実装。"""
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


_PAGE = {}


def page(stem):
    if stem not in _PAGE:
        p = os.path.join(ROOT, "data", "manga.v2", f"{stem}.yml")
        _PAGE[stem] = yaml.safe_load(open(p, encoding="utf-8")) if os.path.exists(p) else None
    return _PAGE[stem]


def parse_sales_date(s):
    s = str(s or "").replace("頃", "").strip()
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.match(r"(\d{4})年(\d{1,2})月", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.match(r"(\d{4})", s)
    return m.group(1) if m else None


def cover_300(url):
    if not url or "noimage" in url:
        return None
    return re.sub(r"\?_ex=\d+x\d+", "", url) + "?_ex=300x300"


def plan():
    # ①の土台: ISBN索引は鮮度が命 → 先に作り直す(manga.v2 1回走査・10秒)
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "_exists.py"), "--build"], cwd=ROOT, check=True,
                   capture_output=True)
    idx = json.load(open(os.path.join(ROOT, ".cache", "isbn-page-index.json"), encoding="utf-8"))
    raw = subprocess.run(["git", "show", f"{WIPE_COMMIT}~1:data/seeds/volumes-supplement-auto.yml"], cwd=ROOT,
                         capture_output=True, check=True).stdout.decode("utf-8")
    pre = (yaml.safe_load(raw) or {}).get("volumes") or []
    con = sqlite3.connect(f"file:{ROOT}/.cache/db-v2.sqlite?mode=ro", uri=True)
    s2 = {r[0] for r in con.execute("SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL")}
    cur_auto = yaml.safe_load(open(AUTO, encoding="utf-8")) or {}
    cur_supp = [v for p in (SUPP, OFFS) if os.path.exists(p)
                for v in ((yaml.safe_load(open(p, encoding="utf-8")) or {}).get("volumes") or [])]
    cur4_entries = (cur_auto.get("volumes") or []) + cur_supp
    cur4 = {str(v.get("isbn13")) for v in cur4_entries if v.get("isbn13")}
    excl = set()
    for f in EXCLUDE_FILES:
        p = os.path.join(SEEDS, f)
        if os.path.exists(p):
            excl |= set(re.findall(r"97[89]\d{10}", open(p, encoding="utf-8", errors="ignore").read()))
    eo = json.load(open(os.path.join(SEEDS, "edition-overrides.json"), encoding="utf-8"))

    def stems_for_key(sk):
        c = collections.Counter()
        for (ib,) in con.execute("SELECT v.isbn13 FROM volumes v JOIN editions e ON v.edition_id=e.id "
                                 "JOIN series s ON e.series_id=s.id WHERE s.series_key=? AND v.isbn13 IS NOT NULL", (sk,)):
            for pub in idx.get(ib, []):
                c[resolve_stem(pub) or pub] += 1
        return c

    def keys_for_stem(stem):
        d = page(stem) or {}
        ks = set()
        for e in d.get("editions") or []:
            for v in (e.get("volumes") or [])[:6]:
                if v.get("isbn13"):
                    for r in con.execute("SELECT s.series_key FROM volumes v JOIN editions e2 ON v.edition_id=e2.id "
                                         "JOIN series s ON e2.series_id=s.id WHERE v.isbn13=?", (str(v["isbn13"]),)):
                        ks.add(r[0])
            if ks:
                break
        return sorted(ks)

    rows, seen = [], set()
    n_present = collections.Counter()
    for e in pre:
        ib = str(e.get("isbn13") or "")
        if not ib or ib in seen:
            continue
        seen.add(ib)
        if ib in idx:
            n_present["頁に在る"] += 1; continue
        if ib in s2:
            n_present["種2に在る"] += 1; continue
        if ib in cur4:
            n_present["種4に在る"] += 1; continue
        r = {"isbn": ib, "number": e.get("number"), "old": e, "verdict": None, "why": ""}
        rows.append(r)
        if ib in excl:
            r["verdict"], r["why"] = "HOLD", "除外簿/退役簿に在る"; continue
        note = str(e.get("note") or "")
        m = re.search(r"stem=([a-z0-9\-]+)", note) or re.search(r"slug=([a-z0-9\-]+)", note)
        stem = resolve_stem(m.group(1)) if m else None
        old_keys = list(e.get("series_keys") or [])
        key_hits = {sk: stems_for_key(sk) for sk in old_keys}
        if not stem:
            tot = collections.Counter()
            for c in key_hits.values():
                tot.update(c)
            if not tot:
                r["verdict"], r["why"] = "HOLD", "元series_keyが種2に無い/頁に当たらない"; continue
            top = tot.most_common(2)
            if len(top) > 1 and top[0][1] < 2 * top[1][1]:
                r["verdict"], r["why"] = "HOLD", "頁が一意に決まらない: " + ",".join(f"{s}({n})" for s, n in top); continue
            stem = top[0][0]
        r["stem"] = stem
        d = page(stem)
        if not d:
            r["verdict"], r["why"] = "HOLD", "頁ファイル不在"; continue
        pub = d.get("slug") or stem
        r["pub"], r["page_title"] = pub, d.get("title")
        if isinstance(eo.get(pub), dict) and eo[pub].get("editions"):
            r["verdict"], r["why"] = "HOLD_FROZEN", "edition-overrides で巻を固定した頁(種4が効かない)"; continue
        if os.path.exists(os.path.join(SEEDS, "edition-canonical", f"{stem}.yml")):
            r["verdict"], r["why"] = "HOLD_FROZEN", "edition-canonical 頁(種4が効かない)"; continue
        if os.path.exists(os.path.join(SEEDS, "preorder-pages", f"{stem}.yml")):
            r["verdict"], r["why"] = "HOLD_FROZEN", "予約頁(preorder-pages=seed直接追記が正)"; continue
        ks = [sk for sk, c in key_hits.items() if stem in c] or keys_for_stem(stem)
        if not ks:
            r["verdict"], r["why"] = "HOLD", "series_key逆引き不可"; continue
        r["keys"] = ks
        etype = e.get("edition_type") or "standard"
        try:
            num = float(e.get("number"))
        except (TypeError, ValueError):
            r["verdict"], r["why"] = "HOLD", "巻番号不明"; continue
        nums = {float(v["number"]) for ed in d.get("editions") or [] if (ed.get("type") or "standard") == etype
                for v in ed.get("volumes") or [] if isinstance(v.get("number"), (int, float))}
        if num in nums:
            r["verdict"], r["why"] = "HOLD", f"同じ版({etype})に{e.get('number')}巻が既在(別ISBN=版違い/特装版?)"; continue
        dup4 = [v for v in cur4_entries if v.get("number") is not None and float(v.get("number")) == num
                and (v.get("edition_type") or "standard") == etype and set(v.get("series_keys") or []) & set(ks)]
        if dup4:
            r["verdict"], r["why"] = "HOLD", "種4に同巻番号が既在: " + ",".join(str(v.get("isbn13")) for v in dup4); continue
        if SPECIAL_ED.search(str(e.get("title_display") or "")):
            r["verdict"], r["why"] = "HOLD", "特装版/限定版(通常版だけ足す)"; continue
        r["verdict"] = "CHECK"

    # ⑥ 楽天照合(キャッシュ1パス → 無い分だけ live)
    chk = [r for r in rows if r["verdict"] == "CHECK"]
    print(f"全消し前 {len(seen)} ISBN / 今も在る {dict(n_present)} / 未復元 {len(rows)} / 楽天照合へ {len(chk)}")
    # 楽天の照会結果は保存して再実行で叩き直さない(None=楽天に無い、も記録)
    rk_cache_p = os.path.join(ROOT, ".cache", "seed4-restore-0724-rakuten.json")
    rk_cache = json.load(open(rk_cache_p, encoding="utf-8")) if os.path.exists(rk_cache_p) else {}
    need = [r["isbn"] for r in chk if r["isbn"] not in rk_cache]
    if need:
        rk_cache.update(LK.cache_delta_scan(need))
    env = LK._env()
    for k, r in enumerate(chk, 1):
        if r["isbn"] not in rk_cache:
            try:
                items = LK.rakuten_live_retry(env, isbn=r["isbn"])
            except Exception as ex:   # 全試行失敗 = 1件だけ保留にして続行(保存しない=次回また引く)
                r["verdict"], r["why"] = "HOLD", f"楽天照会失敗: {ex}"; continue
            rk_cache[r["isbn"]] = items[0] if items else None
            json.dump(rk_cache, open(rk_cache_p, "w", encoding="utf-8"), ensure_ascii=False)
        it = rk_cache.get(r["isbn"])
        if k % 20 == 0:
            print(f"  楽天照合 {k}/{len(chk)}", flush=True)
        if not it:
            r["verdict"], r["why"] = "HOLD", "楽天に無い(要確認)"; continue
        d = page(r["stem"])
        rt, ra = str(it.get("title") or ""), str(it.get("author") or "")
        r["rk_title"], r["rk_author"] = rt, ra
        gid = str(it.get("booksGenreId") or "")
        if gid and not any(g.startswith("001001") for g in gid.split("/")):
            r["verdict"], r["why"] = "HOLD", f"楽天ジャンルが漫画外({gid})"; continue
        # ★7/11 stale-backfill は title_display が空 = 特装版の検問は楽天の題で掛け直す(傷モノの花嫁12 小冊子付き特装版で実踏)
        if SPECIAL_ED.search(rt):
            r["verdict"], r["why"] = "HOLD", "特装版/限定版(楽天題で判定・通常版だけ足す)"; continue
        # ★「含む」でなく「頁題で始まる」: お江戸ねこぱんち/おとなのねこぱんち が ねこぱんち 頁に化けた(別シリーズ)
        nt = norm(d.get("title"))
        if not nt or not (norm(rt).startswith(nt) or norm(it.get("seriesName")).startswith(nt)):
            r["verdict"], r["why"] = "HOLD", "題不一致(楽天題が頁題で始まらない)"; continue
        nums = {float(x) for x in re.findall(r"\d+(?:\.\d+)?", unicodedata.normalize("NFKC", rt))}
        if nums and float(r["number"]) not in nums:
            r["verdict"], r["why"] = "HOLD", f"巻番号不一致(楽天題の数字={sorted(nums)})"; continue
        def names(lst):
            out = set()
            for a in lst or []:
                out.add(norm_person(a.get("name") if isinstance(a, dict) else a))
            return {x for x in out if x}
        pa, po = names(d.get("authors")), names(d.get("original_authors"))
        rk = {norm_person(x) for x in re.split(r"[/／、,]", ra) if norm_person(x)}
        if rk and pa and not (rk & pa):
            if not (rk & po and gid.startswith("001001")):
                r["verdict"], r["why"] = "HOLD", f"著者不一致(頁={sorted(pa)[:3]} 楽天={sorted(rk)[:3]})"; continue
        r["release_date"] = parse_sales_date(it.get("salesDate")) or r["old"].get("release_date")
        r["publisher"] = it.get("publisherName") or r["old"].get("publisher")
        r["cover"] = cover_300(it.get("largeImageUrl"))
        if r["isbn"] in HOLD_MANUAL:
            r["verdict"], r["why"] = "HOLD", "目視: " + HOLD_MANUAL[r["isbn"]]; continue
        r["verdict"] = "RESTORE"

    os.makedirs(os.path.dirname(TSV), exist_ok=True)
    with open(TSV, "w", encoding="utf-8") as f:
        f.write("verdict\twhy\tisbn13\tnumber\tstem\tpage_title\trakuten_title\trakuten_author\tdate_old\tdate_new\tsource_old\tadded_at_old\n")
        for r in sorted(rows, key=lambda x: (x["verdict"], x.get("stem") or "", float(x["number"] or 0))):
            o = r["old"]
            f.write("\t".join(str(x if x is not None else "") for x in (
                r["verdict"], r["why"], r["isbn"], r["number"], r.get("stem"), r.get("page_title"), r.get("rk_title"),
                r.get("rk_author"), o.get("release_date"), r.get("release_date"), o.get("source"), o.get("added_at"))) + "\n")
    json.dump([{k: v for k, v in r.items()} for r in rows], open(PLAN, "w", encoding="utf-8"), ensure_ascii=False, default=str)
    c = collections.Counter(r["verdict"] for r in rows)
    print("判定:", dict(c))
    for why, n in collections.Counter(r["why"].split(":")[0] for r in rows if r["verdict"] != "RESTORE").most_common():
        print(f"  保留 {n:3d}  {why}")
    print(f"→ {os.path.relpath(TSV, ROOT)}")


def apply():
    rows = [r for r in json.load(open(PLAN, encoding="utf-8")) if r["verdict"] == "RESTORE"]
    have = seed_isbns(AUTO) | seed_isbns(SUPP) | seed_isbns(OFFS)
    rows = [r for r in rows if r["isbn"] not in have]   # 冪等: 2回目は何もしない
    if not rows:
        print("追加対象なし(適用済み)"); return
    before = len(seed_isbns(AUTO))
    bak = os.path.join(ROOT, ".cache", f"seed4-restore-0724-bak-{datetime.datetime.now():%Y%m%d-%H%M%S}.yml")
    shutil.copy2(AUTO, bak)
    new = []
    for r in rows:
        o = r["old"]
        new.append({"series_keys": r["keys"], "qid": None, "number": o.get("number"), "isbn13": r["isbn"],
                    "release_date": r.get("release_date"), "pages": None, "publisher": r.get("publisher"),
                    "edition_type": o.get("edition_type") or "standard", "title_display": r.get("rk_title"),
                    "source": "restore-0724-wipe", "added_at": TODAY,
                    "note": f"7/24月次1.2.18({WIPE_COMMIT})の種4-auto全消しで消失→復元(楽天照合済) "
                            f"元source={o.get('source')} 元added_at={o.get('added_at')} stem={r['stem']}"})
    txt = open(AUTO, encoding="utf-8").read()
    if not txt.endswith("\n"):
        txt += "\n"
    # ★全体を書き直さず末尾に追記(書式差分を出さない)。値のquoteは yaml.dump に任せる(「: 」事故の防止)
    txt += yaml.dump(new, allow_unicode=True, sort_keys=False, width=200)
    open(AUTO, "w", encoding="utf-8").write(txt)
    after = len(seed_isbns(AUTO))
    assert after == before + len(new), f"件数検算NG before={before} after={after} new={len(new)}"
    have_cov = set()
    with gzip.open(COVERS, "rt", encoding="utf-8") as f:
        for ln in f:
            try:
                have_cov.add(json.loads(ln).get("isbn13"))
            except Exception:
                pass
    n_cov = 0
    with gzip.open(COVERS, "at", encoding="utf-8") as f:
        for r in rows:
            if r.get("cover") and r["isbn"] not in have_cov:
                f.write(json.dumps({"isbn13": r["isbn"], "cover_url": r["cover"]}, ensure_ascii=False) + "\n")
                n_cov += 1
    with open(LOG, "a", encoding="utf-8") as f:
        for r, v in zip(rows, new):
            f.write(json.dumps({"op": "restore_seed4_wipe_0724", "slug": r["stem"], "isbn13": r["isbn"],
                                "number": v["number"], "before": None, "after": v, "at": TODAY,
                                "backup": os.path.relpath(bak, ROOT), "reversible": True,
                                "evidence": f"git show {WIPE_COMMIT}~1 + 楽天live(ISBN)"}, ensure_ascii=False) + "\n")
    stems = sorted({r["stem"] for r in rows})
    open(TOUCHED, "w", encoding="utf-8").write("\n".join(stems) + "\n")
    print(f"種4-auto {before}→{after}(+{len(new)}) / 書影seed +{n_cov} / 頁 {len(stems)} / backup={os.path.relpath(bak, ROOT)}")
    print(f"touched → {os.path.relpath(TOUCHED, ROOT)}")


if __name__ == "__main__":
    if "--apply" in sys.argv:
        apply()
    elif "--plan" in sys.argv:
        plan()
    else:
        print(__doc__)

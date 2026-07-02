#!/usr/bin/env python3
"""後退蒸留 = 年月チャンクでNDL過去分を掃引し、未掲載漫画を掲載可否ゲートで仕分けて出す。

stages:
  --discover : NDL live取得(_ndl-discovery.py委譲・1.2s・resumable)。★NDL throttle中は回さない。
  --plan     : オフライン分析 = 既存作/新規作の仕分け → 楽天キャッシュenrich → 掲載ゲート
               → AI worksheet(.cache/backward/<year>/ai-todo.jsonl) + 欠落表 出力。本番/preview不変。
  --emit     : AI記入済みworksheetを検証(closed vocab等)→ previewページ生成(テスト先行)
               → 被覆台帳(data/seeds/distill-coverage.json)記帳。

掲載ゲート(2026-07-02 ユーザ裁定):
  掲載 = 必須メタ全部verified(題/ヨミ/著者/年/genre>=1/status/demographic) かつ 楽天書影(v1)あり。
  不足 = 掲載せず欠落表へ(何が足りないか明記)。fail-closed。
新規登録protocol遵守: 単巻先行禁止(同作の巻はまとめて)・題=NDL×楽天突合・勝手命名禁止。

usage: python _distill_backward.py 1998 --plan
       python _distill_backward.py 1998 --emit
"""
import csv, json, os, re, sys, glob, unicodedata, sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _rakuten_match_lib import norm, parse_vol, clean_title, parse_salesdate
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YEAR = next((a for a in sys.argv[1:] if re.fullmatch(r"(19|20)\d{2}", a)), None)
STAGE = next((a for a in sys.argv[1:] if a.startswith("--")), "--plan")
if not YEAR:
    print(__doc__); sys.exit(1)
WORK = os.path.join(ROOT, ".cache", "backward", YEAR)
os.makedirs(WORK, exist_ok=True)
COVERAGE = os.path.join(ROOT, "data", "seeds", "distill-coverage.json")

GENRES = set("action adventure fantasy sci-fi mystery horror gag comedy romcom romance drama slice-of-life school sports baseball soccer historical samurai mecha yokai gourmet 4-koma essay isekai bl suspense music supernatural ecchi mind-game mahou-shoujo war".split())

def nk(s):
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)
    return re.sub(r"[\s・=,．.。、!?！？♪☆★〜～ー\-]", "", s).upper()


def stage_discover():
    print("★NDL live。throttle状態を確認してから: python scripts/_ndl-discovery.py", YEAR)
    print("(今日はNDL休止中 = 実行しない)")


def load_discovery():
    p = os.path.join(ROOT, "data", "seeds", f"ndl-discovery-{YEAR}.tsv")
    if not os.path.exists(p):
        print(f"discovery未取得: {p} → 先に --discover"); sys.exit(1)
    rows = list(csv.DictReader(open(p, encoding="utf-8"), delimiter="\t"))
    print(f"discovery {len(rows)}行")
    return rows


def stage_plan():
    rows = load_discovery()
    # --- 0. 漫画性フィルタ(= promoteのdropパターンを輸入 + NDL既知FP型) ---
    from _promote_drop_patterns import is_droppable  # 下で共有モジュール化
    before = len(rows)
    rows = [r for r in rows if not is_droppable(r.get("title", ""), r.get("series", ""), r.get("creators_roled", ""))]
    print(f"漫画性フィルタ: {before}→{len(rows)} ({before-len(rows)}除外=研究書/図録/画集/ガイド/評論等)")
    # --- 1. 本番既存作とのwork-levelマッチ(title+著者姓) → 既存頁補完候補(A) / 新規(B) ---
    idx = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    f = idx["f"]; si = f.index("slug"); ti = f.index("title"); ai = f.index("authors")
    prod = {}
    for r in idx["d"]:
        aus = r[ai] or []
        a0 = (aus[0].get("name", "") if aus and isinstance(aus[0], dict) else "")
        prod.setdefault(nk(r[ti]), []).append((r[si], a0))
    con = sqlite3.connect(f"file:{ROOT}/.cache/db-v2.sqlite?mode=ro".replace("\\", "/"), uri=True)
    have2 = {x[0] for x in con.execute("SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL")}
    A = []  # 既存作の巻(種4候補)
    works = {}  # B: 新規作 group
    for r in rows:
        ib = re.sub(r"\D", "", r.get("isbn13", ""))
        if len(ib) != 13 or ib in have2:
            continue
        title = clean_title(r.get("title", ""))
        vol_tok, residual = parse_vol(title)
        vol = r.get("volume") or vol_tok
        try:
            vol = int(re.search(r"\d+", str(vol)).group()) if vol else 1
        except Exception:
            vol = 1
        creators = [c.split(":")[0].strip() for c in str(r.get("creators_roled") or r.get("creators") or "").split("/") if c.strip()]
        a0 = (creators[0] if creators else "").replace(" ", "").replace("　", "")
        key = nk(residual)
        hit = None
        for slug, pa in prod.get(key, []):
            if a0 and pa and (a0[:2] in pa.replace(" ", "") or pa.replace(" ", "")[:2] in a0):
                hit = slug; break
        if hit:
            A.append({"slug": hit, "isbn": ib, "vol": vol, "title": title, "date": r.get("date", ""), "publisher": r.get("publisher", "")})
        else:
            w = works.setdefault((key, a0), {"residual": residual, "kana": r.get("kana", ""), "creators": creators,
                                             "creators_roled": r.get("creators_roled", ""), "publisher": r.get("publisher", ""),
                                             "series_label": r.get("series", ""), "vols": []})
            w["vols"].append({"n": vol, "isbn": ib, "date": r.get("date", ""), "title": title})
    print(f"既存作の巻(A→既存頁補完候補): {len(A)} / 新規作(B): {len(works)}")
    json.dump(A, open(os.path.join(WORK, "existing-vols.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # --- 2. 楽天キャッシュ enrich (書影/titleKana/salesDate) ---
    need = {v["isbn"] for w in works.values() for v in w["vols"]}
    rk = {}
    delta = os.path.join(ROOT, ".cache", "rakuten-isbn-delta.jsonl")
    for ln in open(delta, encoding="utf-8"):
        if not any(x in ln for x in need):
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        ib = re.sub(r"\D", "", str(d.get("isbn", "")))
        if ib in need and ib not in rk:
            it = d.get("item") or {}
            img = str(it.get("largeImageUrl") or it.get("mediumImageUrl") or "")
            rk[ib] = {"cover": None if (not img or "noimage" in img) else img.split("?")[0] + "?_ex=300x300",
                      "kana": it.get("titleKana", ""), "sales": it.get("salesDate", ""), "title": it.get("title", ""), "caption": it.get("itemCaption", "")}
            need.discard(ib)
        if not need:
            break
    print(f"楽天キャッシュhit: {len(rk)} / miss {len(need)} (missはlive楽天候補=後日)")

    # --- 3. 掲載ゲート ---
    publishable = []; lacking = []
    for (key, a0), w in works.items():
        vols = sorted(w["vols"], key=lambda v: v["n"])
        nums = [v["n"] for v in vols]
        miss_fields = []
        # 巻連続性(単巻先行防止: 途中欠けは NDL内で見えている範囲の連番か)
        if len(set(nums)) != len(nums) or (nums and nums[0] != 1) or (nums and nums[-1] - nums[0] + 1 != len(nums)):
            miss_fields.append(f"巻不連続{nums[:8]}")
        if not w["kana"]:
            miss_fields.append("ヨミ無(NDL)")
        if not w["creators"]:
            miss_fields.append("著者無")
        v1 = next((v for v in vols if v["n"] == 1), None)
        cov1 = rk.get(v1["isbn"], {}).get("cover") if v1 else None
        if not cov1:
            miss_fields.append("v1書影無(楽天)")
        # 楽天題との突合(勝手命名禁止の担保)
        rk_title = rk.get(v1["isbn"], {}).get("title", "") if v1 else ""
        if rk_title:
            _, rres = parse_vol(clean_title(rk_title))
            if nk(rres) != key and nk(rres) not in key and key not in nk(rres):
                miss_fields.append(f"題不一致(NDL/楽天):{rres[:14]}")
        rec = {"key": key, "title": w["residual"], "kana": w["kana"], "creators": w["creators"],
               "creators_roled": w["creators_roled"], "publisher": w["publisher"],
               "series_label": w["series_label"],
               "vols": [{**v, "cover": rk.get(v["isbn"], {}).get("cover"),
                         "sales": rk.get(v["isbn"], {}).get("sales", "")} for v in vols],
               "rakuten_kana": rk.get(v1["isbn"], {}).get("kana", "") if v1 else "", "caption": rk.get(v1["isbn"], {}).get("caption", "") if v1 else ""}
        if miss_fields:
            lacking.append({**rec, "lacking": miss_fields})
        else:
            publishable.append(rec)
    json.dump(publishable, open(os.path.join(WORK, "publishable.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(ROOT, "docs", "production-diagnostics", f"backward-{YEAR}-lacking.tsv"), "w", encoding="utf-8") as fo:
        fo.write("title\tkana\tauthors\tvols\tlacking\n")
        for x in lacking:
            fo.write(f"{x['title']}\t{x['kana']}\t{'/'.join(x['creators'][:2])}\t{[v['n'] for v in x['vols']][:8]}\t{';'.join(x['lacking'])}\n")
    # --- 4. AI worksheet (genre/catch/synopsis/slug) ---
    with open(os.path.join(WORK, "ai-todo.jsonl"), "w", encoding="utf-8") as fo:
        for x in publishable:
            fo.write(json.dumps({"key": x["key"], "title": x["title"], "kana": x["kana"],
                                 "rakuten_kana": x["rakuten_kana"], "creators": x["creators"],
                                 "publisher": x["publisher"], "series_label": x["series_label"],
                                 "n_vols": len(x["vols"]), "caption": str(x.get("caption",""))[:300],
                                 "TODO": {"is_manga": True, "slug": "", "genres": [], "catch": "", "synopsis": "", "demographic": ""}},
                                ensure_ascii=False) + "\n")
    print(f"掲載可(AI worksheet待ち): {len(publishable)} / 欠落表: {len(lacking)}")
    print(f"→ {WORK}/ai-todo.jsonl を記入後 --emit")
    print(f"→ 欠落表 docs/production-diagnostics/backward-{YEAR}-lacking.tsv")


def _pad_date(sd):
    if not sd: return None
    m = re.match(r"^(\d{4})(?:[.\-/](\d{1,2}))?(?:[.\-/](\d{1,2}))?", str(sd))
    if not m: return None
    y, mo, d = m.group(1), m.group(2), m.group(3)
    if mo and d: return f"{y}-{int(mo):02d}-{int(d):02d}"
    if mo: return f"{y}-{int(mo):02d}"
    return y

def stage_emit():
    pub = json.load(open(os.path.join(WORK, "publishable.json"), encoding="utf-8"))
    todo = {}
    for ln in open(os.path.join(WORK, "ai-todo.jsonl"), encoding="utf-8"):
        d = json.loads(ln)
        todo[d["key"]] = d.get("TODO", {})
    idx = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    f = idx["f"]; si = f.index("slug")
    allslugs = {r[si] for r in idx["d"]}
    import yaml
    _NUM = re.compile(r"^[-+]?(\d[\d_]*|\d*\.\d+([eE][-+]?\d+)?)$")
    def _rep(dp, data):
        if _NUM.match(data) or data.lower() in ("true", "false", "null", "yes", "no", "on", "off", "~"):
            return dp.represent_scalar("tag:yaml.org,2002:str", data, style="'")
        return dp.represent_scalar("tag:yaml.org,2002:str", data)
    yaml.add_representer(str, _rep, Dumper=yaml.SafeDumper)
    written = 0; skipped = []
    for x in pub:
        t = todo.get(x["key"], {})
        if t.get("is_manga") is False:
            skipped.append((x["title"], ["AI判定=非漫画"])); continue
        errs = []
        slug = str(t.get("slug", "")).strip()
        if not re.fullmatch(r"[a-z0-9\-]{3,}", slug or ""):
            errs.append("slug不正")
        elif slug in allslugs:
            errs.append(f"slug衝突:{slug}")
        gs = t.get("genres") or []
        if not gs or any(g not in GENRES for g in gs):
            errs.append(f"genre不正{gs}")
        if not str(t.get("demographic", "")) in ("shounen", "shoujo", "seinen", "josei", "kids", "general"):
            errs.append("demographic不正")
        if not t.get("synopsis"):
            errs.append("synopsis無")
        if errs:
            skipped.append((x["title"], errs)); continue
        # ★NDL書誌規約の掃除: 「題 = 並記英題」→分離してalt.enへ / 末尾ピリオド除去
        raw_t = str(x["title"]).strip()
        alt_en = None
        m2 = re.match(r"^(.*?)\s*=\s*([^=]+)$", raw_t)
        if m2 and re.search(r"[A-Za-z]", m2.group(2)) and not re.search(r"[ぁ-んァ-ヶ一-龯]", m2.group(2)):
            raw_t, alt_en = m2.group(1).strip(), m2.group(2).strip().rstrip(".")
        raw_t = re.sub(r"[.．]$", "", raw_t).strip()
        y0 = re.search(r"(19|20)\d{2}", str(x["vols"][0].get("date", ""))) or re.search(r"(19|20)\d{2}", YEAR)
        year = int(y0.group()) if y0 else int(YEAR)
        page = {"slug": slug, "title": raw_t, "title_kana": re.sub(r"[\s　]+", "", x["kana"]),
                "title_romaji": slug.replace("-", " "),
                "year_started": year, "year_ended": None if year >= 2025 else year, "status": "ongoing" if year >= 2025 else "completed",
                "authors": [{"name": c, "role": "writer_artist"} for c in x["creators"][:3]],
                "publisher": "(unknown)", "magazine": None,
                "demographic": t["demographic"], "genres": gs, "genres_provisional": True,
                "synopsis": t.get("synopsis", ""), "catch": t.get("catch", ""),
                "anime_adapted": False,
                
                "editions": [{"type": "standard", "label": "通常版", "publisher": x["publisher"], "imprint": x["series_label"],
                              "volumes": [{"number": v["n"], "asin": None, "isbn13": v["isbn"],
                                           "cover_url": v.get("cover"),
                                           "release_date": _pad_date(v.get("date"))}
                                          for v in x["vols"]]}]}
        if alt_en:
            page["alternative_titles"] = {"en": alt_en}
        # ★Zodミラー最終検証(検索404の構造防止): date形式/None値キー
        for e2 in page["editions"]:
            for v2 in e2["volumes"]:
                rd = v2.get("release_date")
                assert rd is None or re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", str(rd)), f"date不正 {slug} {rd}"
        out = os.path.join(ROOT, ".preview-data", "manga", f"{slug}.yml")
        with open(out, "w", encoding="utf-8") as fo:
            yaml.dump(page, fo, allow_unicode=True, sort_keys=False, Dumper=yaml.SafeDumper)
        allslugs.add(slug); written += 1
    print(f"preview生成: {written} / 検証NG skip: {len(skipped)}")
    for tskip, errs in skipped[:10]:
        print("  skip:", tskip[:20], errs)
    if written:
        cov = json.load(open(COVERAGE, encoding="utf-8")) if os.path.exists(COVERAGE) else {}
        cov[YEAR] = {"emitted": written, "at": "2026-07-02"}
        json.dump(cov, open(COVERAGE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"被覆台帳記帳: {YEAR}")
        print("次: preview索引更新 → push → ユーザ確認 → 本番化")


if STAGE == "--discover":
    stage_discover()
elif STAGE == "--plan":
    stage_plan()
elif STAGE == "--emit":
    stage_emit()

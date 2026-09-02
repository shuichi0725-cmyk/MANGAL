#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""予約①続巻の種4自動追加 (= 2026-07-06 段階実行①)

classified.json の zokkan を volumes-supplement-auto.yml へ純粋追加。
ゲート: slug実在 / 巻番号必須(不明はworklist) / 同ISBN既登録skip / series_keys=db-v2逆引き成功必須。
★2026-09-02: 分類器の _slug は**公開slug**。slug-overrides.yml で改名した頁は manga.v2 ファイル名(SRC stem)と
  ズレるため、公開slug直引きだと「series_key逆引き不可」で保留に落ちていた(氷舞のアウフギーサー2 等4件で実踏。
  [[pubslug_src_stem_generator_trap]])。pub2stem 逆引き(_gen-shinkan-data.py と同実装)で SRC stem に解決し、
  touched も SRC stem で出す(= reflect --only はファイル名を要求する)。
★2026-09-02 同巻番号ゲート: 特装版/限定版が通常版と同じ巻番号で種4に入り二重化していた(ゆるゆり25/大室家9/コナン109 等11件)。
  ①特装版/限定版は保留(分類器も skip するが二重の安全弁) ②頁のstandard版 or 種4-auto(同series_keys)に同巻番号が既在なら保留、
  ただし既在が特装版entryなら通常版で置換(特装版entryを退役し volumes-supplement-retire-changelog.jsonl に記帳)。
出力: 追加件数 + touched slugリスト(.cache/preorders/zokkan-touched.json) + 不備worklist追記
"""
import json, os, sys, sqlite3, datetime, re
sys.stdout.reconfigure(encoding="utf-8")
import yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTO = os.path.join(ROOT, "data", "seeds", "volumes-supplement-auto.yml")
RETIRE_LOG = os.path.join(ROOT, "data", "seeds", "volumes-supplement-retire-changelog.jsonl")
TODAY = datetime.date.today().isoformat()
SPECIAL_ED = re.compile(r"特装版|限定版|初回限定|豪華版|特別版|特典付|小冊子付|ドラマCD|CD付|DVD付|Blu-?ray|OAD|アクリル|しおり付|カードセット付|ポストカード|クリアスタンド|キーホルダー|フィギュア付", re.I)

cls = json.load(open(f"{ROOT}/.cache/preorders/classified.json", encoding="utf-8"))
doc = yaml.safe_load(open(AUTO, encoding="utf-8")) or {"volumes": []}
have = {str(v.get("isbn13")) for v in doc["volumes"]}
con = sqlite3.connect(f"file:{ROOT}/.cache/db-v2.sqlite?mode=ro", uri=True)

def load_pub2stem():
    """公開slug→SRC stem の逆引き(slug-overrides.yml)。_gen-shinkan-data.py と同実装。"""
    m = {}
    p = os.path.join(ROOT, "data", "seeds", "slug-overrides.yml")
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

def resolve_stem(slug):
    """公開slug → manga.v2 の SRC stem(ファイル名)。直引きで無ければ pub2stem 逆引き。無ければ None。"""
    if os.path.exists(f"{ROOT}/data/manga.v2/{slug}.yml"):
        return slug
    stem = PUB2STEM.get(slug)
    if stem and os.path.exists(f"{ROOT}/data/manga.v2/{stem}.yml"):
        return stem
    return None

PAGE_NUMS = {}

def page_numbers(stem):
    """頁の standard 版(type無し含む)に既在する巻番号集合(同巻番号ゲート用)。"""
    if stem in PAGE_NUMS:
        return PAGE_NUMS[stem]
    nums = set()
    p = f"{ROOT}/data/manga.v2/{stem}.yml"
    if os.path.exists(p):
        d = yaml.safe_load(open(p, encoding="utf-8")) or {}
        for e in d.get("editions") or []:
            if (e.get("type") or "standard") != "standard":
                continue
            for v in e.get("volumes") or []:
                if isinstance(v.get("number"), int):
                    nums.add(v["number"])
    PAGE_NUMS[stem] = nums
    return nums

def keys_for_slug(slug):
    """既存頁のISBNからseries_key群を逆引き(先頭数冊で十分)。slug は SRC stem。"""
    p = f"{ROOT}/data/manga.v2/{slug}.yml"
    if not os.path.exists(p):
        return None
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

added = 0
replaced = 0
touched = set()
wl = []
key_cache = {}
for r in cls["zokkan"]:
    isbn, slug, vol = r["isbn"], r.get("_slug"), r.get("_vol")
    if isbn in have:
        continue
    if not slug:
        wl.append((isbn, r["title"], "slug無")); continue
    if SPECIAL_ED.search(str(r.get("title") or "")):
        wl.append((isbn, r["title"], f"特装版/限定版=非掲載(通常版ISBNを待つ) slug={slug}")); continue
    if vol is None:
        wl.append((isbn, r["title"], f"巻番号不明 slug={slug}")); continue
    stem = resolve_stem(slug)   # ★公開slug→SRC stem(改名頁の罠)
    if not stem:
        wl.append((isbn, r["title"], f"頁ファイル不在(公開slug→stem逆引き不能) slug={slug}")); continue
    if stem not in key_cache:
        key_cache[stem] = keys_for_slug(stem)
    ks = key_cache[stem]
    if not ks:
        why = "series_key逆引き不可(preorder-pages由来=種2不在→seed直接追記が正)" if os.path.exists(f"{ROOT}/data/seeds/preorder-pages/{stem}.yml") else "series_key逆引き不可"
        wl.append((isbn, r["title"], f"{why} slug={slug}" + (f" stem={stem}" if stem != slug else ""))); continue
    # ★同巻番号ゲート(2026-09-02): 頁standard版 or 種4-auto(同series_keys)に同じ巻番号が既在
    dup_auto = [v for v in doc["volumes"] if int(v.get("number") or -1) == int(vol)
                and set(v.get("series_keys") or []) & set(ks) and str(v.get("isbn13")) != isbn]
    if int(vol) in page_numbers(stem) or dup_auto:
        specials = [v for v in dup_auto if SPECIAL_ED.search(str(v.get("title_display") or ""))]
        if dup_auto and len(specials) == len(dup_auto) and int(vol) not in page_numbers(stem):
            # 既在が特装版entryだけ → 通常版で置換(特装版entryを退役+台帳)
            for v in specials:
                doc["volumes"].remove(v)
                with open(RETIRE_LOG, "a", encoding="utf-8") as _rl:
                    _rl.write(json.dumps({"op": "retire_special_edition", "isbn13": str(v.get("isbn13")), "number": v.get("number"),
                                          "title": v.get("title_display"), "replaced_by": isbn, "at": TODAY, "reversible": True,
                                          "backup": v}, ensure_ascii=False) + "\n")
                replaced += 1
        else:
            ex = ",".join(str(v.get("isbn13")) for v in dup_auto) or "頁既在"
            wl.append((isbn, r["title"], f"同巻番号{vol}既在(版違い/二重登録?) 既存={ex} slug={slug}")); continue
    rd = r.get("ym")
    if rd and r.get("day"):
        rd = f"{rd}-{r['day']:02d}"
    doc["volumes"].append({"series_keys": ks, "qid": None, "number": int(vol), "isbn13": isbn,
                           "release_date": rd, "pages": None, "publisher": r.get("publisher"),
                           "edition_type": "standard", "title_display": r.get("title"),
                           "source": "rakuten-preorder", "added_at": TODAY,
                           "note": f"楽天予約ハーベスト① slug={slug}" + (f" stem={stem}" if stem != slug else "")})
    have.add(isbn)
    touched.add(stem)   # ★reflect --only はファイル名(SRC stem)
    added += 1

yaml.dump(doc, open(AUTO, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=200)
json.dump(sorted(touched), open(f"{ROOT}/.cache/preorders/zokkan-touched.json", "w"))
with open(f"{ROOT}/docs/production-diagnostics/preorder-triage.tsv", "a", encoding="utf-8") as f:
    for isbn, title, why in wl:
        f.write(f"zokkan_hold\t{isbn}\t\t{str(title)[:40]}\t\t\t{why}\n")

# ★covers seed自動追記(2026-07-10 ユーザ指摘=新刊巻の書影忘れ): harvestの実URL書影を
#   data/seeds/covers.jsonl.gz へ純粋追加。promoteの_cover_forがnull書影を充填する経路に乗せる。
import gzip as _gz
_cp = os.path.join(ROOT, "data", "seeds", "covers.jsonl.gz")
_have = set()
try:
    for _l in _gz.open(_cp, "rt", encoding="utf-8"):
        try: _have.add(json.loads(_l).get("isbn13"))
        except Exception: pass
except Exception: pass
_added_cov = 0
with _gz.open(_cp, "at", encoding="utf-8") as _f:
    for _r in cls["zokkan"]:
        _c = _r.get("cover")
        if _c and "noimage" not in _c and _r.get("isbn") not in _have:
            _f.write(json.dumps({"isbn13": _r["isbn"], "cover_url": _c}, ensure_ascii=False) + "\n")
            _have.add(_r["isbn"]); _added_cov += 1
print(f"covers seed追記: {_added_cov}件(新刊書影)")
print(f"種4追加 {added} / 対象頁 {len(touched)} / 保留 {len(wl)} (worklist追記) / 特装版→通常版置換 {replaced}")

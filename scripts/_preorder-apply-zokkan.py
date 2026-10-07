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
★2026-10-06 予約頁の続巻=seed直接追記: 予約頁(preorder-pages)出身の頁は種2に series が無く series_key を逆引きできない
  (=種4が効かない)。従来は「seed直接追記が正」と保留に書くだけで手作業待ちだった(カクリキ2/猩猩姫3 が発売日を過ぎても出なかった)。
  → 通常版が1つ・同ISBN/同巻番号なし・巻が連続(予約頁max+1..+3)の時だけ、その seed の巻の並びに1冊差し込む
  ([[preorder_page_zokkan_direct_append]])。全体を書き直すと長文(rakuten_caption)の折り返しが変わるので行を差し込み、
  読み直して「その1冊が増えただけ」を検算してから書く。記帳=data/seeds/preorder-page-zokkan-changelog.jsonl / 退避=.cache/preorder-page-zokkan-bak-<日付>/
★2026-10-08 固定頁の続巻=巻の並びへ直接追記: edition-overrides に editions を持つ頁は promote が editions を丸ごと置き換えるので
  種4に入れても頁に出ない(無敗のふたり6・Kiss me crying 6・聖女に嘘は通じない7・チンチンデビル6・罪と罰のスピカ8・最強出戻り中年冒険者3
  = 9/14〜10/3 に種4へ入ったまま出ていなかった。月次#36 FROZEN)。→ 通常版1つ・同ISBN/同巻番号なし・巻連続(max+1..+3)・
  出版社一致・発売日が既刊より前でない時だけ、override の巻の並びへ1冊足す(記帳=edition-fix-changelog.jsonl op=override_zokkan_append /
  退避=.cache/edition-overrides-zokkan-bak-<日付>/)。種4に既に在る巻も、固定頁なら毎回ここを通る(再投入で拾い直す)。
  edition-canonical(キー=SRC stem)の頁は canonical が override より後に editions を組み直すので、override 併用 or open_tail 無しなら
  黙って種4に入れず保留簿へ(本体へ手で追記= CLAUDE.md 厳守6。ゴルゴ13 223 型)。open_tail 在り かつ override 無しは種4→末尾追随で出る。
出力: 追加件数 + touched slugリスト(.cache/preorders/zokkan-touched.json) + 不備worklist追記
"""
import sys as _sys_h
if any(_a in ("-h", "--help") for _a in _sys_h.argv[1:]):   # ★--help で本体を走らせない(2026-10-03 apply-zokkan を誤実行し touched を空で上書き)
    print(__doc__ or "(no doc)"); _sys_h.exit(0)
import json, os, sys, sqlite3, datetime, re, unicodedata
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

PP_LOG = os.path.join(ROOT, "data", "seeds", "preorder-page-zokkan-changelog.jsonl")


def is_preorder_produced(stem):
    """頁が予約頁 seed から作られるか = preorder-pages/<stem>.yml が在り、本流の元頁(data/manga・source-pages)が無い。
    promote の予約合流は「本流が同じ stem を書いた時」だけ seed を退く(自己retire)ので、元頁が無ければ seed が頁の正。"""
    return (os.path.exists(f"{ROOT}/data/seeds/preorder-pages/{stem}.yml")
            and not os.path.exists(f"{ROOT}/data/manga/{stem}.yml")
            and not os.path.exists(f"{ROOT}/data/seeds/source-pages/{stem}.yml"))


def release_date_of(r):
    rd = r.get("ym")
    if rd and r.get("day"):
        rd = f"{rd}-{r['day']:02d}"
    return rd


def append_to_preorder_page(stem, r, vol):
    """予約頁 seed の通常版の巻の並びに1冊差し込む。成功=None / 失敗=保留理由。"""
    import copy, shutil
    pp = f"{ROOT}/data/seeds/preorder-pages/{stem}.yml"
    txt = open(pp, encoding="utf-8").read()
    d0 = yaml.safe_load(txt) or {}
    eds = d0.get("editions") or []
    std = [i for i, e in enumerate(eds) if (e.get("type") or "standard") == "standard"]
    if len(std) != 1:
        return f"予約頁の通常版が{len(std)}個(足し先を決められない)"
    vols = eds[std[0]].get("volumes") or []
    if any(str(v.get("isbn13")) == str(r["isbn"]) for e in eds for v in e.get("volumes") or []):
        return "既在"   # 既に seed に在る=何もしない(呼び側は簿に書かない)
    nums = [v.get("number") for v in vols if isinstance(v.get("number"), int)]
    if int(vol) in nums:
        return f"同巻番号{vol}既在(予約頁)"
    mx = max(nums or [0])
    if int(vol) > mx + 3:   # 途中の欠けを埋める巻は通す(同じ回に3巻・4巻が逆順で来る型)。遠い飛び番だけ止める
        return f"巻が飛びすぎ(予約頁max{mx}→{vol}=全巻回収側)"
    cov = r.get("cover") if r.get("cover") and "noimage" not in str(r.get("cover")) else None
    newv = {"number": int(vol), "asin": None, "isbn13": str(r["isbn"]), "cover_url": cov,
            "release_date": release_date_of(r)}
    # 通常版の volumes ブロックの末尾を探す(editions は col0 の「- 」、版のキーは2字下げ、巻は「  - 」+4字下げ)
    lines = txt.split("\n")
    try:
        ei = lines.index("editions:")
    except ValueError:
        return "editions: 行が無い(差し込めない)"
    starts, j = [], ei + 1
    while j < len(lines) and (lines[j].startswith("- ") or lines[j].startswith("  ") or lines[j] == ""):
        if lines[j].startswith("- "):
            starts.append(j)
        j += 1
    span_end = starts[std[0] + 1] if std[0] + 1 < len(starts) else j
    vi = next((k for k in range(starts[std[0]], span_end) if lines[k].startswith("  volumes:")), None)
    if vi is None:
        return "volumes: 行が無い(差し込めない)"
    snippet = ["  " + ln for ln in yaml.dump([newv], allow_unicode=True, sort_keys=False, width=200).rstrip("\n").split("\n")]
    if lines[vi].strip() == "volumes: []":
        lines[vi:vi + 1] = ["  volumes:"] + snippet
    else:
        k = vi + 1
        while k < span_end and (lines[k].startswith("  - ") or lines[k].startswith("    ")):
            k += 1
        lines[k:k] = snippet
    new_txt = "\n".join(lines)
    want = copy.deepcopy(d0)
    want["editions"][std[0]].setdefault("volumes", []).append(newv)
    if yaml.safe_load(new_txt) != want:
        return "差し込み検算NG(読み直した内容が1冊追加と一致しない)"
    bak_dir = os.path.join(ROOT, ".cache", f"preorder-page-zokkan-bak-{TODAY}")
    os.makedirs(bak_dir, exist_ok=True)
    if not os.path.exists(os.path.join(bak_dir, f"{stem}.yml")):
        shutil.copy2(pp, os.path.join(bak_dir, f"{stem}.yml"))
    open(pp, "w", encoding="utf-8").write(new_txt)
    with open(PP_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"op": "preorder_page_zokkan_append", "slug": stem, "isbn13": str(r["isbn"]), "number": int(vol),
                            "before": None, "after": newv, "at": TODAY, "reversible": True,
                            "backup": os.path.relpath(os.path.join(bak_dir, f"{stem}.yml"), ROOT),
                            "source": "rakuten-preorder", "title": r.get("title")}, ensure_ascii=False) + "\n")
    return None


OVR_P = os.path.join(ROOT, "data", "seeds", "edition-overrides.json")
OVR_RAW = open(OVR_P, encoding="utf-8").read() if os.path.exists(OVR_P) else "{}"
OVR = json.loads(OVR_RAW)
OVR_ADDS = []   # (key, newv) = このrunで巻の並びに足した巻(最後に1回だけ書いて読み直し検算)
OVR_LOG = os.path.join(ROOT, "data", "seeds", "edition-fix-changelog.jsonl")
CANON_DIR = os.path.join(ROOT, "data", "seeds", "edition-canonical")
_pubs = yaml.safe_load(open(os.path.join(ROOT, "data", "publishers.yml"), encoding="utf-8")) or {}
_PUBN = {}
for _k, _v in _pubs.items():
    _PUBN[_k] = _k
    if isinstance(_v, dict):
        for _n in [_v.get("name")] + list(_v.get("aliases") or []):
            if _n:
                _PUBN[re.sub(r"\s+", "", unicodedata.normalize("NFKC", _n))] = _k


def _pub_key(name):
    """出版社名/キー → publishers.yml のキー(引けなければ正規化した生名)。"""
    n = re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(name or "")))
    return _PUBN.get(n, n)


def override_key(slug, stem):
    """★固定頁(edition-overrides の editions 指定)のキー。promote と同じく公開slug→SRC stem の順に引く。無ければ None。"""
    for k in (slug, stem):
        if k and (OVR.get(k) or {}).get("editions"):
            return k
    return None


_CANON = None


def canonical_frozen(stem, has_override):
    """★edition-canonical(キー=seed内の slug = SRC stem)で通常版を固定している頁か。canonical は override より**後**に
    editions を組み直すので、canonical を持つ頁は override に足しても効かない。
    種4が効くのは「open_tail 在り かつ override 無し」だけ(open_tail の末尾追随は override が無い時の種2+種4の通常版を見る。
    override が在ると override の通常版を見る= ゴルゴ13 は override 1-220 で止まり、221・222 は本体へ手で追記してきた)。"""
    global _CANON
    if _CANON is None:
        _CANON = {}
        import glob as _glob
        for p in _glob.glob(os.path.join(CANON_DIR, "*.yml")):
            try:
                s = yaml.safe_load(open(p, encoding="utf-8")) or {}
            except Exception:
                continue
            if s.get("slug"):
                _CANON[s["slug"]] = s
    s = _CANON.get(stem)
    if s is None:
        return False
    return has_override or not s.get("open_tail")


def append_to_override(key, r, vol):
    """★固定頁の通常版の巻の並びに1冊足す(2026-10-08)。成功=None / 失敗=保留理由。
    edition-overrides は promote で editions を丸ごと置き換えるので、種4に入れても頁に出ない
    (無敗のふたり6・Kiss me crying 6・聖女に嘘は通じない7 等6冊が 9/14〜10/3 に種4へ入ったまま出ていなかった=#36 FROZEN)。
    手作業の前例(聖女に嘘は通じない6 = 2026-09-03 override追記)を機械化。ゲートは予約頁の直接追記と同じ考え方:
    通常版が1つ / 同ISBN・同巻番号が無い / 巻が連続(max+1..+3) / 出版社が同じ(移籍・別版を混ぜない) / 発売日が既刊より前でない。"""
    eds = OVR[key]["editions"]
    std = [i for i, e in enumerate(eds) if (e.get("type") or "standard") == "standard"]
    if len(std) != 1:
        return f"固定頁の通常版が{len(std)}個(足し先を決められない)"
    if any(str(v.get("isbn13")) == str(r["isbn"]) for e in eds for v in e.get("volumes") or []):
        return "既在"
    vols = eds[std[0]].get("volumes") or []
    nums = [v.get("number") for v in vols if isinstance(v.get("number"), int)]
    if int(vol) in nums:
        return f"同巻番号{vol}既在(固定頁)"
    mx = max(nums or [0])
    if not (mx >= 1 and mx + 1 <= int(vol) <= mx + 3):
        return f"巻が連続しない(固定頁max{mx}→{vol})"
    ep, rp = eds[std[0]].get("publisher"), r.get("publisher")
    if ep and rp and _pub_key(ep) != _pub_key(rp):
        return f"出版社が違う(固定頁={ep} / 楽天={rp}=移籍・別版の疑い)"
    rd = release_date_of(r)
    dates = [str(v.get("release_date")) for v in vols if v.get("release_date")]
    if rd and dates and str(rd) < max(dates)[:len(str(rd))]:
        return f"発売日{rd}が既刊の最終日{max(dates)}より前"
    newv = {"asin": None, "cover_url": None, "isbn13": str(r["isbn"]), "number": int(vol), "release_date": rd}
    vols.append(newv)   # 書影は promote 最終pass が covers seed(下で harvest 書影を追記)から充填する
    eds[std[0]]["volumes"] = vols
    OVR_ADDS.append((key, std[0], newv, r.get("title")))
    return None


added = 0
added_pp = 0
added_ov = 0
replaced = 0
touched = set()
wl = []
key_cache = {}
for r in sorted(cls["zokkan"], key=lambda x: (str(x.get("_slug") or ""), x.get("_vol") if isinstance(x.get("_vol"), int) else 10**6)):
    isbn, slug, vol = r["isbn"], r.get("_slug"), r.get("_vol")
    _st0 = resolve_stem(slug) if slug else None
    if isbn in have and not (_st0 and (is_preorder_produced(_st0) or override_key(slug, _st0))):
        continue   # ★予約頁/固定頁は種4に在っても頁に出ない=seed側の有無で判断する(下の直接追記へ)
    if not slug:
        wl.append((isbn, r["title"], "slug無")); continue
    if SPECIAL_ED.search(str(r.get("title") or "")):
        wl.append((isbn, r["title"], f"特装版/限定版=非掲載(通常版ISBNを待つ) slug={slug}")); continue
    if vol is None:
        wl.append((isbn, r["title"], f"巻番号不明 slug={slug}")); continue
    stem = resolve_stem(slug)   # ★公開slug→SRC stem(改名頁の罠)
    if not stem:
        wl.append((isbn, r["title"], f"頁ファイル不在(公開slug→stem逆引き不能) slug={slug}")); continue
    if is_preorder_produced(stem):
        # ★予約頁の seed で作られる頁は、作品が後から種2に入って series_key が引けても種4を読まない
        #   (promote の予約合流は「同名の元頁が本流で書かれた時」だけ種2側に譲る)。2026-10-06 に種4へ入れた97冊が
        #   頁に出なかった実害 → series_key の有無に関わらず seed へ直接差し込む。
        why = append_to_preorder_page(stem, r, vol)
        if why is None:
            have.add(isbn); touched.add(stem); added_pp += 1
        elif why != "既在":
            wl.append((isbn, r["title"], f"予約頁への直接追記を保留: {why} slug={slug}"))
        continue
    _ok = override_key(slug, stem)
    if canonical_frozen(stem, bool(_ok)):
        # ★canonical 固定頁も種4を読まない(override 併用 or open_tail 無し)。本体への追記は人が確かめて行う(CLAUDE.md 厳守6)
        if int(vol) not in page_numbers(stem):
            wl.append((isbn, r["title"], f"canonical固定頁(override併用/open_tail無し)=種4が効かない→canonical本体へ手で追記 slug={slug} stem={stem}"))
        continue
    if _ok:
        # ★固定頁(edition-overrides)は種4を読まない= 巻の並びへ直接足す(2026-10-08)
        why = append_to_override(_ok, r, vol)
        if why is None:
            have.add(isbn); touched.add(stem); added_ov += 1
        elif why != "既在":
            wl.append((isbn, r["title"], f"固定頁(edition-overrides)への直接追記を保留: {why} slug={slug}"))
        continue
    if stem not in key_cache:
        key_cache[stem] = keys_for_slug(stem)
    ks = key_cache[stem]
    if not ks:
        wl.append((isbn, r["title"], f"series_key逆引き不可 slug={slug}" + (f" stem={stem}" if stem != slug else ""))); continue
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
    rd = release_date_of(r)
    doc["volumes"].append({"series_keys": ks, "qid": None, "number": int(vol), "isbn13": isbn,
                           "release_date": rd, "pages": None, "publisher": r.get("publisher"),
                           "edition_type": "standard", "title_display": r.get("title"),
                           "source": "rakuten-preorder", "added_at": TODAY,
                           "note": f"楽天予約ハーベスト① slug={slug}" + (f" stem={stem}" if stem != slug else "")})
    have.add(isbn)
    touched.add(stem)   # ★reflect --only はファイル名(SRC stem)
    added += 1

yaml.dump(doc, open(AUTO, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=200)
if OVR_ADDS:
    # ★固定頁への追記は最後に1回だけ書く。書式は既存と同じ(indent=1・非ASCIIそのまま・末尾改行)。
    #   読み直して「元の内容 + 足した巻だけ」と一致することを検算してから台帳に記帳する。
    import copy, shutil
    want = json.loads(OVR_RAW)
    for key, ei, newv, _t in OVR_ADDS:
        want[key]["editions"][ei].setdefault("volumes", []).append(copy.deepcopy(newv))
    if want != OVR:
        sys.exit("[abort] 固定頁追記の検算NG(メモリ上の内容が「元+追記」と一致しない)。edition-overrides.json は未変更。")
    bak_dir = os.path.join(ROOT, ".cache", f"edition-overrides-zokkan-bak-{TODAY}")
    os.makedirs(bak_dir, exist_ok=True)
    bak = os.path.join(bak_dir, "edition-overrides.json")
    if not os.path.exists(bak):
        open(bak, "w", encoding="utf-8").write(OVR_RAW)
    open(OVR_P, "w", encoding="utf-8").write(json.dumps(OVR, ensure_ascii=False, indent=1) + "\n")
    if json.load(open(OVR_P, encoding="utf-8")) != want:
        shutil.copy(bak, OVR_P)
        sys.exit("[abort] 固定頁追記の読み直し検算NG → edition-overrides.json を退避から戻した。")
    with open(OVR_LOG, "a", encoding="utf-8") as f:
        for key, ei, newv, t in OVR_ADDS:
            f.write(json.dumps({"op": "override_zokkan_append", "slug": key, "isbn13": newv["isbn13"], "number": newv["number"],
                                "before": None, "after": newv, "at": TODAY, "reversible": True,
                                "backup": os.path.relpath(bak, ROOT), "source": "rakuten-preorder", "title": t},
                               ensure_ascii=False) + "\n")
json.dump(sorted(touched), open(f"{ROOT}/.cache/preorders/zokkan-touched.json", "w"))
with open(f"{ROOT}/docs/production-diagnostics/preorder-triage.tsv", "a", encoding="utf-8") as f:
    for isbn, title, why in wl:
        f.write(f"zokkan_hold\t{isbn}\t\t{str(title)[:40]}\t\t\t\t{why}\n")  # ★8列に合わせる(2026-09-24: 理由が slug 列にずれていた)

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
print(f"種4追加 {added} / 予約頁へ直接追記 {added_pp} / 固定頁へ直接追記 {added_ov} / 対象頁 {len(touched)} / 保留 {len(wl)} (worklist追記) / 特装版→通常版置換 {replaced}")
for key, ei, newv, t in OVR_ADDS:
    print(f"  固定頁追記: {key} 巻{newv['number']} {newv['isbn13']} {newv['release_date']}  ({t})")

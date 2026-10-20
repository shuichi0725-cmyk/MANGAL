"""予約頁(data/seeds/preorder-pages)→ AniList 結線(2026-10-20 ユーザ GO「1、2 と、3 の4頁までやる」)。

予約頁は種2本流を通らない = series_key が無く、 enrich map(series_key → AniList)に引っかからない
([[preorder_page_bypasses_mainline_class]] の9件目)。 2,454頁中 AniList 付きは1頁だけだった。
★_build-anilist-enrich-map.py が中で link() を呼び、 enrich map へ `preorder:<stem>` キーで足す
  (promote の予約合流ブロックが引く。 作品QID / 和訳 todo / animeflag は enrich map の値を読むので自動で乗る)。

2経路:
  ISBN : 頁の巻 ISBN → 種2 series_key → 同じ enrich map の AniList(= 本流がその series に付けている AniList を借りる)
  題   : 頁題(+巻副題)強正規化 == AniList native/english/romaji/synonyms ∧ 作画側の著者一致 ∧ 本流未使用 ID ∧ 1:1
結ばない(保留 = holds.tsv):
  ・両経路が別 ID / 開始年が4年以上離れる(新装版・再刊・別作)
  ・ISBN 経路の series が別の公開頁の巻も持つ(俺はヒロインになれません。破! = 種2 が続編を本編 series に同居させる型)
  ・ISBN 経路の series 群が複数の AniList に割れる
  ・題経路で原作者だけ一致(インターネット巫女 = 別コミカライズを拾う型)/ 候補が複数 / 読切(ONE_SHOT)に2巻以上の頁
  ・同じ ID を複数の予約頁が取り合う
★anilist-link-overrides.yml の key `preorder:<stem>` で drop / relink できる(relink は builder 側で先に入る)。
出力(git 追跡): docs/production-diagnostics/preorder-anilist-links.tsv / preorder-anilist-holds.tsv
"""
import gzip
import json
import re
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import yaml

try:
    _Loader = yaml.CSafeLoader
except AttributeError:
    _Loader = yaml.SafeLoader

ROOT = Path(__file__).resolve().parent.parent
PP_DIR = ROOT / "data" / "seeds" / "preorder-pages"
DUMP = ROOT / ".cache" / "anilist-manga-dump-v3.jsonl.gz"
DB = ROOT / ".cache" / "db-v2.sqlite"
ISBN_IDX = ROOT / ".cache" / "isbn-page-index.json"
OUT_LINKS = ROOT / "docs" / "production-diagnostics" / "preorder-anilist-links.tsv"
OUT_HOLDS = ROOT / "docs" / "production-diagnostics" / "preorder-anilist-holds.tsv"
PREFIX = "preorder:"
YEAR_GAP = 4
HIRA = str.maketrans({chr(c): chr(c + 0x60) for c in range(0x3041, 0x3097)})
ROMAN = {"Ⅰ": "1", "Ⅱ": "2", "Ⅲ": "3", "Ⅳ": "4", "Ⅴ": "5",
         "Ⅵ": "6", "Ⅶ": "7", "Ⅷ": "8", "Ⅸ": "9", "Ⅹ": "10"}
NONAUTH = re.compile(r"translat|letter|assist|editor|design|proofread|adapt", re.I)
ART = re.compile(r"art", re.I)   # Art / Story & Art(作画側)


def tnorm(s):
    """題の強正規化(_anilist-recall-v2.py と同軸)。"""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    for k, v in ROMAN.items():
        s = s.replace(k, v)
    return re.sub(r"[^0-9a-zぁ-んァ-ヶ一-龯]", "", s.lower())


def anorm(s):
    if not s:
        return ""
    return re.sub(r"[\s　・･.,，、]+", "", unicodedata.normalize("NFKC", str(s)).translate(HIRA)).lower()


def lookable(n):
    return n and (len(n) >= 3 or (len(n) >= 2 and not n.isascii()))


def _isbn(v):
    return re.sub(r"\D", "", str(v or ""))


def _page_facts(d):
    isbns, subs, years = [], set(), []
    for ed in d.get("editions") or []:
        if not isinstance(ed, dict):
            continue
        pools = [ed.get("volumes") or []] + [vv.get("volumes") or [] for vv in (ed.get("versions") or [])]
        for pool in pools:
            for v in pool:
                if not isinstance(v, dict):
                    continue
                if v.get("isbn13"):
                    isbns.append(_isbn(v["isbn13"]))
                if v.get("subtitle"):
                    subs.add(str(v["subtitle"]))
                rd = str(v.get("release_date") or "")
                if rd[:4].isdigit():
                    years.append(int(rd[:4]))
    y = min(years) if years else d.get("year_started")
    try:
        y = int(y) if y else None
    except (TypeError, ValueError):
        y = None
    return list(dict.fromkeys(isbns)), subs, y


def link(sk_aid: dict, drop_keys: set, log=sys.stderr) -> dict:
    """{stem: aid} を返す(結ぶと決めた予約頁だけ)。 TSV 2本を書く。 sk_aid = builder の最終 series_key → aid。"""
    if not PP_DIR.is_dir():
        return {}
    # --- 予約頁
    pages = {}
    for f in sorted(PP_DIR.glob("*.yml")):
        try:
            d = yaml.load(f.read_text(encoding="utf-8"), Loader=_Loader) or {}
        except Exception:
            continue
        if isinstance(d, dict):
            pages[f.stem] = d
    # --- 種2: ISBN → series_key / series_key → ISBN
    isb2key, key2isb = defaultdict(set), defaultdict(set)
    con = sqlite3.connect(str(DB))
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    for i, k in con.execute("SELECT v.isbn13, s.series_key FROM volumes v JOIN editions e ON e.id=v.edition_id "
                            "JOIN series s ON s.id=e.series_id WHERE v.isbn13 IS NOT NULL"):
        i = _isbn(i)
        if len(i) == 13:
            isb2key[i].add(k)
            key2isb[k].add(i)
    con.close()
    # --- 公開頁の ISBN 索引(ISBN → 頁)= 「その series の巻が別の頁にも載っているか」
    page_of = {}
    if ISBN_IDX.exists():
        idx = json.loads(ISBN_IDX.read_text(encoding="utf-8"))
        if isinstance(idx.get("isbn"), dict):
            idx = idx["isbn"]
        page_of = {i: (v if isinstance(v, list) else [v]) for i, v in idx.items()}
    else:
        print("  ★予約頁AniList: .cache/isbn-page-index.json が無い = ISBN 経路は全部保留"
              "(python scripts/_exists.py --build で作る)", file=log)
    # --- AniList dump: 題索引 / 著者(全体・作画側)
    used = {a for a in sk_aid.values()}
    tindex = defaultdict(set)
    staff_all, staff_art, info = {}, {}, {}
    with gzip.open(DUMP, "rt", encoding="utf-8") as fh:
        for line in fh:
            e = json.loads(line)
            i = e["id"]
            t = e.get("title") or {}
            for s in (t.get("native"), t.get("english"), t.get("romaji")):
                n = tnorm(s)
                if len(n) >= 2:
                    tindex[n].add(i)
            for s in (e.get("synonyms") or []):
                n = tnorm(s)
                if len(n) >= 3:
                    tindex[n].add(i)
            sa, sr = set(), set()
            for ed in (e.get("staff") or {}).get("edges", []):
                role = ed.get("role", "") or ""
                if NONAUTH.search(role):
                    continue
                nm = (ed.get("node") or {}).get("name") or {}
                for n in (nm.get("native"), nm.get("full")):
                    a = anorm(n)
                    if len(a) >= 2:
                        sa.add(a)
                        if ART.search(role):
                            sr.add(a)
            staff_all[i], staff_art[i] = sa, sr
            info[i] = (t.get("native") or t.get("romaji") or "", (e.get("startDate") or {}).get("year"),
                       e.get("format") or "")

    isbn_res, title_res = {}, {}     # stem → (aid | None, 理由)
    facts = {}
    for stem, d in pages.items():
        if d.get("anilist_id"):
            continue
        isbns, subs, py = _page_facts(d)
        facts[stem] = (py, len(isbns))
        own = {stem, str(d.get("slug") or stem)}
        # ISBN 経路
        keys = set()
        for i in isbns:
            keys |= isb2key.get(i, set())
        if keys:
            aids = {sk_aid[k] for k in keys if k in sk_aid and not k.startswith(PREFIX)}
            if len(aids) > 1:
                isbn_res[stem] = (None, f"種2の series が複数の AniList に割れる {sorted(aids)}")
            elif aids:
                aid = next(iter(aids))
                other = set()
                if page_of:
                    for k in keys:
                        for i in key2isb.get(k, ()):
                            other |= set(page_of.get(i, ())) - own
                    isbn_res[stem] = ((None, f"その series の巻が別の頁にも在る({sorted(other)[0]} ほか{len(other)}頁)")
                                      if other else (aid, ""))
                else:
                    isbn_res[stem] = (None, "ISBN 索引なし")
        # 題経路
        tkeys = {tnorm(d.get("title"))}
        if d.get("subtitle"):
            tkeys.add(tnorm(str(d.get("title") or "") + str(d["subtitle"])))
        tkeys |= {tnorm(str(d.get("title") or "") + s) for s in subs}
        hits = set()
        for k in tkeys:
            if lookable(k):
                hits |= tindex.get(k, set())
        if hits:
            pa = {anorm(a.get("name")) for fld in ("authors", "original_authors")
                  for a in (d.get(fld) or []) if isinstance(a, dict)}
            pa = {a for a in pa if len(a) >= 2}
            cand = {i for i in hits if staff_all.get(i, set()) & pa}
            art = {i for i in cand if staff_art.get(i, set()) & pa
                   and not (info[i][2] == "ONE_SHOT" and len(isbns) >= 2)}
            free = art - used
            if len(free) == 1:
                title_res[stem] = (next(iter(free)), "")
            elif len(free) > 1:
                title_res[stem] = (None, f"題の候補が複数 {sorted(free)}")
            elif art:
                title_res[stem] = (None, f"題で当たる ID は本流の頁が使用中 {sorted(art)}")
            elif cand:
                title_res[stem] = (None, f"原作者だけ一致(別コミカライズの恐れ){sorted(cand)}")
    # 題経路の 1:1(同じ ID を複数の予約頁が取り合う → 全部保留)
    claim = Counter(a for a, _ in title_res.values() if a)
    for stem, (a, _) in list(title_res.items()):
        if a and claim[a] > 1:
            title_res[stem] = (None, f"同じ ID {a} を複数の予約頁が取り合う")

    links, link_rows, hold_rows = {}, [], []
    stats = Counter()
    for stem in sorted(set(isbn_res) | set(title_res)):
        d = pages[stem]
        key = PREFIX + stem
        ia, ir = isbn_res.get(stem, (None, ""))
        ta, tr = title_res.get(stem, (None, ""))
        py, _nv = facts[stem]
        if key in drop_keys:
            stats["override drop"] += 1
            hold_rows.append((stem, d.get("title"), "anilist-link-overrides で drop", ia or "", ta or "", py or "", ""))
            continue
        if key in sk_aid:            # relink override(builder が先に入れた)
            stats["override relink"] += 1
            continue
        if ia and ta and ia != ta:
            stats["保留: 経路で別 ID"] += 1
            hold_rows.append((stem, d.get("title"), "ISBN 経路と題経路で別 ID", ia, ta, py or "",
                              f"{info.get(ia, ('', ''))[1]}/{info.get(ta, ('', ''))[1]}"))
            continue
        aid = ia or ta
        if not aid:
            stats["保留: " + (ir or tr).split("(")[0].split(" {")[0].split(" [")[0]] += 1
            hold_rows.append((stem, d.get("title"), " / ".join(x for x in (ir, tr) if x), "", "", py or "", ""))
            continue
        ay = info.get(aid, ("", None))[1]
        if py and ay and abs(int(py) - int(ay)) >= YEAR_GAP:
            stats["保留: 開始年が4年以上離れる"] += 1
            hold_rows.append((stem, d.get("title"), f"開始年が {abs(int(py) - int(ay))} 年離れる", ia or "", ta or "",
                              py, ay))
            continue
        route = "ISBN+題" if (ia and ta) else ("ISBN" if ia else "題")
        stats["結ぶ: " + route] += 1
        links[stem] = aid
        note = " / ".join(x for x in (ir, tr) if x)
        link_rows.append((stem, d.get("title"), aid, info.get(aid, ("",))[0], route, py or "", ay or "", note))

    clean = lambda v: re.sub(r"[\t\n\r]", " ", str(v if v is not None else ""))
    OUT_LINKS.parent.mkdir(parents=True, exist_ok=True)
    with OUT_LINKS.open("w", encoding="utf-8", newline="\n") as f:
        f.write("stem\ttitle\tanilist_id\ta_native\troute\tpage_year\ta_year\tnote\n")
        for r in link_rows:
            f.write("\t".join(clean(v) for v in r) + "\n")
    with OUT_HOLDS.open("w", encoding="utf-8", newline="\n") as f:
        f.write("stem\ttitle\treason\tisbn_aid\ttitle_aid\tpage_year\ta_year\n")
        for r in hold_rows:
            f.write("\t".join(clean(v) for v in r) + "\n")
    print(f"  ★予約頁 AniList: 予約頁 {len(pages):,} / 結ぶ {len(links):,} / 保留 {len(hold_rows):,}", file=log)
    for k, v in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"      {k}: {v:,}", file=log)
    print(f"    → {OUT_LINKS.relative_to(ROOT)} / {OUT_HOLDS.relative_to(ROOT)}", file=log)
    return links

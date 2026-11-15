# -*- coding: utf-8 -*-
"""Wikipedia に在ってサイトに無い作品(厳選済み)を、頁seedにするまでの道具 (2026-11-15 新設)。

  python scripts/_wiki-nopage-build.py --plan            # 手元の照合 + NDLのヨミ取得(1.3秒/件・再開可) → worksheet と保留表
  python scripts/_wiki-nopage-build.py --plan --no-ndl   # NDL を叩かず、取得済みの分だけで組む
  python scripts/_wiki-nopage-build.py --emit            # slug 記入済みの worksheet → data/seeds/preorder-pages/*.yml

入力 = docs/production-diagnostics/wiki-nopage-ready.tsv(_gen-wiki-nopage-ready.py の合格)のうち
       「同じ著者の近い頁なし・2巻以上」。
★新規登録 protocol のとおり、機械で確かめられない項目は埋めない。 1つでも欠ければ保留表へ(載せない)。
  題     = Wikipedia の情報欄(楽天の題と完全一致で通過済み)
  ヨミ   = NDL(ISBN直引き)。 楽天のヨミと一致で確定 / NDL が主題だけ(副題なし)で楽天のヨミの先頭に一致 → 楽天のヨミを採る / それ以外は保留
  著者   = Wikipedia の欄名で役割を決める(作者=writer_artist / 原作=writer / 作画・漫画=artist)。 それ以外の欄しか無ければ保留
  年     = 1巻と最終巻の発売年(楽天)   状態 = 「全N巻」だけ completed(「既刊」は記事が古いことがあるので保留)
  区分   = Wikipedia のジャンル欄(少年漫画 等) → 無ければ楽天のジャンルID
  ジャンル = AniList(題が一致)の genres → 無ければ Wikipedia のジャンル欄の語を master の語へ写す。 どちらも無ければ保留
  二重頁の番人 = 楽天のヨミがサイトの既存頁のヨミと一致したら保留(ラテン表記ちがいの同じ作品)
  過去の裁定 = ISBN が data/seeds のどこかに既に書かれていたら保留(drop・種4・deny 等を1件ずつ見る)
キャッチ/あらすじは作らない(登録後の enrich の仕事)。
"""
from __future__ import annotations
import csv
import gzip
import importlib.util
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, ".cache", "wiki-nopage")
os.makedirs(WORK, exist_ok=True)
READY = os.path.join(ROOT, "docs", "production-diagnostics", "wiki-nopage-ready.tsv")
HOLD = os.path.join(ROOT, "docs", "production-diagnostics", "wiki-nopage-hold.tsv")
SHEET = os.path.join(WORK, "worksheet.jsonl")
NDL = os.path.join(WORK, "ndl.jsonl")


def _mod(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


G = _mod("wvg", "_audit-wiki-volume-gap.py")
norm = G.norm

MASTER = set("action adventure fantasy sci-fi mystery horror gag comedy romcom romance drama slice-of-life school sports "
             "baseball soccer historical samurai mecha yokai gourmet 4-koma essay isekai bl suspense music supernatural "
             "ecchi mind-game mahou-shoujo war".split())
ANILIST_G = {"Action": "action", "Adventure": "adventure", "Comedy": "comedy", "Drama": "drama", "Ecchi": "ecchi",
             "Fantasy": "fantasy", "Horror": "horror", "Mahou Shoujo": "mahou-shoujo", "Mecha": "mecha", "Music": "music",
             "Mystery": "mystery", "Romance": "romance", "Sci-Fi": "sci-fi", "Slice of Life": "slice-of-life",
             "Sports": "sports", "Supernatural": "supernatural", "Thriller": "suspense"}
WIKI_G = [("ラブコメ", ["romcom"]), ("ラブ・コメ", ["romcom"]), ("恋愛", ["romance"]), ("ラブストーリー", ["romance"]),
          ("アクション", ["action"]), ("バトル", ["action"]), ("格闘", ["action"]), ("冒険", ["adventure"]),
          ("アドベンチャー", ["adventure"]), ("異世界", ["isekai"]), ("ファンタジー", ["fantasy"]),
          ("サイエンス・フィクション", ["sci-fi"]), ("SF", ["sci-fi"]), ("ミステリ", ["mystery"]), ("推理", ["mystery"]),
          ("ホラー", ["horror"]), ("ギャグ", ["gag"]), ("コメディ", ["comedy"]), ("人間ドラマ", ["drama"]),
          ("日常", ["slice-of-life"]), ("学園", ["school"]), ("野球", ["sports", "baseball"]),
          ("サッカー", ["sports", "soccer"]), ("スポーツ", ["sports"]), ("時代劇", ["samurai"]), ("歴史", ["historical"]),
          ("ロボット", ["mecha"]), ("妖怪", ["yokai"]), ("料理", ["gourmet"]), ("グルメ", ["gourmet"]),
          ("4コマ", ["4-koma"]), ("四コマ", ["4-koma"]), ("エッセイ", ["essay"]), ("ボーイズラブ", ["bl"]),
          ("サスペンス", ["suspense"]), ("音楽", ["music"]), ("オカルト", ["supernatural"]), ("超能力", ["supernatural"]),
          ("魔法少女", ["mahou-shoujo"]), ("戦争", ["war"]), ("戦記", ["war"])]
WIKI_DEMO = [("少年漫画", "shounen"), ("少女漫画", "shoujo"), ("青年漫画", "seinen"), ("女性漫画", "josei"), ("児童漫画", "kodomo")]
ROLE = {"作者": "writer_artist", "原作": "writer", "作画": "artist", "漫画": "artist"}


_PAREN_ROLE = re.compile(r"[（(]([^（）()]*)[）)]")


def credited(field, raw):
    """情報欄の1欄 → [(名前, 役割 or None, 役割の出どころ)]。
    ★括弧の中の役割を先に読む(「久弥直樹(原案)」を 作者欄だからと writer_artist にしない = 役割を既定で埋めない)。"""
    out = []
    for part in re.split(r"\s*/\s*|、|,|，", G.clean(raw)):
        part = part.strip()
        if not part:
            continue
        notes = _PAREN_ROLE.findall(part)
        name = re.sub(r"^(原作|作画|漫画|原案|作|画)\s*[:：]\s*", "", _PAREN_ROLE.sub("", part)).strip()
        if not name or len(name) > 20:
            continue
        note = "・".join(notes)
        if note:
            if re.search(r"原案|キャラクター|企画|構成|監修|協力|脚本|デザイン|製作|制作|ネーム", note):
                role = None
            elif "原作" in note and re.search(r"作画|漫画", note):
                role = "writer_artist"
            elif "原作" in note:
                role = "writer"
            elif re.search(r"作画|漫画|画", note):
                role = "artist"
            else:
                role = None
            out.append((name, role, f"{field}({note})"))
        else:
            out.append((name, ROLE.get(field), field))
    return out


def clean_kana(s):
    """楽天の題ヨミ → 巻次(「（1）」「 1」)と空白を落とす。"""
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = re.sub(r"\s*[（(]?\s*\d{1,3}\s*[）)]?\s*$", "", s)
    return re.sub(r"[\s　]+", "", s)


def kana_key(s):
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)
    return re.sub(r"[^ァ-ヶー0-9A-Za-z]", "", s).upper().replace("ヲ", "オ")


def pad_date(s):
    m = re.match(r"(\d{4})年(\d{1,2})月(?:(\d{1,2})日)?", s or "")
    if not m:
        return None
    return f"{m.group(1)}-{int(m.group(2)):02d}" + (f"-{int(m.group(3)):02d}" if m.group(3) else "")


def pub_map():
    import yaml
    doc = yaml.safe_load(open(os.path.join(ROOT, "data", "publishers.yml"), encoding="utf-8"))

    def nkp(x):
        return re.sub(r"[\s・]|株式会社", "", unicodedata.normalize("NFKC", str(x or ""))).lower()
    m = {}
    for k, v in (doc or {}).items():
        if isinstance(v, dict):
            m[nkp(v.get("name", ""))] = k
            for a in v.get("aliases") or []:
                m[nkp(a)] = k
    return m, nkp


def targets():
    rows = list(csv.DictReader(open(READY, encoding="utf-8"), delimiter="\t"))
    return [r for r in rows if not r["同じ著者の近い頁"] and int(r["楽天の冊数"]) >= 2]


def fetch_ndl(isbns):
    """1巻の ISBN を NDL で直引き(_lookup.py に封じ込め・1.3秒/件・取得済みは飛ばす)。"""
    done = {}
    if os.path.exists(NDL):
        for l in open(NDL, encoding="utf-8"):
            d = json.loads(l)
            done[d["isbn"]] = d
    todo = [i for i in isbns if i not in done]
    if not todo:
        return done
    L = _mod("lookup", "_lookup.py")
    print(f"NDL 直引き {len(todo)} 件(約{len(todo) * 2 // 60 + 1}分)…", flush=True)
    fail = 0
    with open(NDL, "a", encoding="utf-8") as f:
        for n, ib in enumerate(todo, 1):
            try:
                recs = L.ndl_live_retry(f'isbn="{ib}"', maximum=3, backoff=(3, 10), raise_on_error=True)   # 失敗を「書誌なし」にしない
                fail = 0
            except SystemExit:
                print("  NDL が 429 = 中断(取得済みは保存。 --plan をもう一度で続きから)"); break
            except Exception as e:
                recs, fail = None, fail + 1
                print(f"  {ib} 失敗: {e}")
                if fail >= 3:
                    print("  連続3件失敗 = NDL が重い。 中断(休ませてから --plan をもう一度)"); break
            if recs is not None:
                d = {"isbn": ib, "rec": (recs[0] if recs else None)}
                f.write(json.dumps(d, ensure_ascii=False) + "\n"); f.flush()
                done[ib] = d
            if n % 20 == 0:
                print(f"  {n}/{len(todo)}", flush=True)
            time.sleep(1.3)
    return done


def plan(use_ndl=True):
    tg = targets()
    idx = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    F = {k: i for i, k in enumerate(idx["f"])}
    site_kana, site_author_kana = {}, {}
    for r in idx["d"]:
        aus = (r[F["authors"]] or []) + (r[F["original_authors"]] or [])
        k = kana_key(r[F["title_kana"]])
        if k:
            site_kana.setdefault(k, []).append((r[0], {norm(a.split("	")[0]) for a in aus}))
        for a in aus:                          # 既存頁の著者ヨミ(楽天にヨミが無い時の裏取り)
            nm, _, kn = a.partition("	")
            if kn:
                site_author_kana.setdefault(norm(nm), kn)
    import yaml as _yaml
    mags = {}
    for mk, mv in (_yaml.safe_load(open(os.path.join(ROOT, "data", "magazines.yml"), encoding="utf-8")) or {}).items():
        if isinstance(mv, dict) and mv.get("demographic"):
            mags[norm(mv.get("name"))] = (mk, mv["demographic"])
            for al in mv.get("aliases") or []:
                mags[norm(al)] = (mk, mv["demographic"])
    tmap = json.load(open(os.path.join(ROOT, ".cache", "isbn-title-map.json"), encoding="utf-8"))
    need = {i for r in tg for i in r["ISBN"].split(",")}
    items = {}
    pat = re.compile(r'^\{"isbn":\s*"(\d{13})"')
    with open(os.path.join(ROOT, ".cache", "rakuten-isbn-delta.jsonl"), encoding="utf-8") as f:
        for line in f:
            m = pat.match(line)
            if m and m.group(1) in need:
                items[m.group(1)] = json.loads(line).get("item") or {}
    # 過去の裁定: ISBN が seeds のどこかに書かれているか(1パス)
    seen_in = {}
    sd = os.path.join(ROOT, "data", "seeds")
    isbn_re = re.compile(r"97[89]\d{10}")
    for dp, _dn, fns in os.walk(sd):
        for fn in fns:
            if not fn.endswith((".yml", ".yaml", ".jsonl", ".json", ".tsv", ".txt")) or fn.startswith("isbn-snapshot"):
                continue
            p = os.path.join(dp, fn)
            if os.path.getsize(p) > 400_000_000:
                continue
            try:
                with open(p, encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if "97" in line:
                            for i in isbn_re.findall(line):
                                if i in need:
                                    seen_in.setdefault(i, set()).add(os.path.relpath(p, sd).replace(os.sep, "/"))
            except Exception:
                pass
    # ★裁定に当たるファイルだけを見る(発売日の表や NDL の発見表に ISBN が在るのは裁定ではない)
    RULING = re.compile(r"drop|deny|exclude|dedup|supplement|preorder|edition|adult|operations|merge|special|canonical|page")
    for i in list(seen_in):
        seen_in[i] = {f for f in seen_in[i] if RULING.search(f) and not f.startswith("release-date")}
    # 種2 にその ISBN が在るか
    con = sqlite3.connect(f"file:{os.path.join(ROOT, '.cache', 'db-v2.sqlite')}?mode=ro", uri=True)
    in_seed2 = {}
    need_l = sorted(need)
    for k in range(0, len(need_l), 500):
        chunk = need_l[k:k + 500]
        q = ("select v.isbn13, s.id, s.adult_score from volumes v join editions e on e.id=v.edition_id "
             f"join series s on s.id=e.series_id where v.isbn13 in ({','.join('?' * len(chunk))})")
        for isbn, sid, sc in con.execute(q, chunk):
            in_seed2[isbn] = (sid, sc or 0)
    # AniList(題 → genres)
    ani = {}
    wanted = {norm(r["題"]) for r in tg}
    with gzip.open(os.path.join(ROOT, ".cache", "anilist-manga-dump-v3.jsonl.gz"), "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            m = d.get("media") or d
            nat = norm((m.get("title") or {}).get("native"))
            if nat in wanted:
                ani[nat] = m
    # 記事本文(ジャンル欄・著者の欄名)
    arts = {}
    want_art = {r["記事"] for r in tg}
    with open(G.ARTS, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["title"] in want_art:
                arts[d["title"]] = d.get("text") or ""
    PUB, nkp = pub_map()
    ndl = fetch_ndl([r["ISBN"].split(",")[0] for r in tg]) if use_ndl else (
        {json.loads(l)["isbn"]: json.loads(l) for l in open(NDL, encoding="utf-8")} if os.path.exists(NDL) else {})

    old = {}
    if os.path.exists(SHEET):                      # 記入済みの slug を引き継ぐ
        for l in open(SHEET, encoding="utf-8"):
            d = json.loads(l)
            old[d["key"]] = d.get("slug", "")
    sheet, hold = [], []
    for r in tg:
        isbns = r["ISBN"].split(",")
        its = [items[i] for i in isbns]
        key, why = norm(r["題"]), []
        text = arts.get(r["記事"], "")
        head = G.templates(text, "Infobox animanga/Header")
        wgenre = G.clean(G.params(head[0]).get("ジャンル", "")) if head else ""
        box = None
        for body in G.templates(text, "Infobox animanga/Manga"):
            p = G.params(body)
            t = G.clean(p.get("タイトル", "")).split(" / ")[0].strip()
            if norm(t) == key or (not t and box is None):
                box = p
                if norm(t) == key:
                    break
        box = box or {}
        # 著者と役割
        r_names = [x.strip() for x in re.split(r"[/／]", its[0].get("author") or "") if x.strip()]
        r_kanas = [x.strip() for x in re.split(r"[/／]", its[0].get("authorKana") or "")]
        rk = {norm(n): (r_kanas[i] if i < len(r_kanas) else "") for i, n in enumerate(r_names)}
        authors, other_role = [], []
        for field in ("作者", "原作", "作画", "漫画", "原案", "キャラクター原案", "原作・原案など"):
            for nm, role, src in credited(field, box.get(field, "")):
                if not role:
                    other_role.append(f"{src}:{nm}"); continue
                kn = rk.get(norm(nm), "")
                if not kn:                         # 名前の完全一致だけ(部分一致・並び順での対応は取り違える)
                    kn = site_author_kana.get(norm(nm), "")
                authors.append({"name": nm, "kana": re.sub(r"[\s,]", "", kn), "role": role})
        if other_role:
            why.append("役割を決められない名前がある: " + ";".join(other_role)[:60])
        if not authors:
            why.append("役割の分かる著者欄が無い" + (f"({';'.join(other_role)[:40]})" if other_role else ""))
        elif any(not a["kana"] for a in authors):
            why.append("著者のヨミが楽天に無い: " + ",".join(a["name"] for a in authors if not a["kana"]))
        roles = {a["role"] for a in authors}
        if roles and roles not in ({"writer_artist"}, {"writer", "artist"}):
            # 作者(=writer_artist)と 作画/原作 が混ざる・原作だけ・作画だけ = 欄からは役割の組が確定しない
            why.append("役割の組が確定しない: " + ",".join(f"{a['name']}={a['role']}" for a in authors)[:60])
        # ヨミ
        rkana = kana_key(clean_kana(its[0].get("titleKana")))
        nrec = (ndl.get(isbns[0]) or {}).get("rec")
        nkana = re.sub(r"\d+(カン)?$", "", kana_key((nrec or {}).get("title_kana")))   # NDL のヨミ末尾の巻次(01カン)を落とす
        if isbns[0] not in ndl:
            why.append("NDL 未取得")
        elif not nrec:
            why.append("NDL に1巻の書誌なし(ヨミを確かめられない)")
        elif not nkana or not rkana:
            why.append("ヨミが NDL か楽天に無い")
        elif not (nkana == rkana or (len(nkana) >= 4 and rkana.startswith(nkana))):
            why.append(f"ヨミが NDL と楽天で違う({(nrec or {}).get('title_kana','')[:18]} / {its[0].get('titleKana','')[:18]})")
        same = [sl for sl, aus in site_kana.get(rkana, []) if aus & {norm(a["name"]) for a in authors}] if rkana else []
        if same:
            why.append(f"同じヨミ・同じ著者の頁が既に在る: {same[0]}")
        # 過去の裁定 / 種2
        hits = sorted({f for i in isbns for f in seen_in.get(i, ())})
        if hits:
            why.append("ISBN が seeds に既出: " + ",".join(hits)[:80])
        s2 = [in_seed2[i] for i in isbns if i in in_seed2]
        if any(sc > 0 for _, sc in s2):
            why.append("種2 で成人スコアあり")
        # 状態・区分・ジャンル・出版社
        if not G.vol_numbers(r["Wiki巻数欄"])[0][1]:
            why.append("「既刊」表記(完結か確かめられない)")
        demo = next((v for k2, v in WIKI_DEMO if k2 in wgenre), "")
        if not demo:
            gid = str(its[0].get("booksGenreId", ""))
            demo = {"001001001": "shounen", "001001002": "shoujo", "001001003": "seinen", "001001004": "josei"}.get(gid[:9], "")
        magkey = None
        for mname in re.split(r"\s*/\s*|→|、", G.clean(box.get("掲載誌", ""))):
            hit = mags.get(norm(re.sub(r"[（(].*", "", mname)))
            if hit:
                magkey = hit[0]
                demo = demo or hit[1]             # ジャンル欄にも楽天にも無ければ、掲載誌(雑誌マスタ)の区分
                break
        if not demo:
            why.append(f"区分(少年/少女/青年/女性)が決まらない(掲載誌: {G.clean(box.get('掲載誌', ''))[:20] or '空'})")
        genres, gsrc = [], ""
        am = ani.get(key)
        if am and not am.get("isAdult"):
            genres = [ANILIST_G[g] for g in am.get("genres") or [] if g in ANILIST_G]
            gsrc = f"anilist:{am.get('id')}"
        if not genres:
            for word, keys in WIKI_G:
                if word in wgenre:
                    genres += [k2 for k2 in keys if k2 not in genres]
            gsrc = "wikipedia" if genres else ""
        genres = [g for g in dict.fromkeys(genres) if g in MASTER][:4]
        if not genres:
            why.append(f"ジャンルの根拠なし(Wikiジャンル欄: {wgenre[:24] or '空'})")
        pk = PUB.get(nkp(its[0].get("publisherName")))
        if not pk:
            why.append(f"出版社が master に無い: {its[0].get('publisherName')}")
        vols = []
        for n, (i, it) in enumerate(zip(isbns, its), 1):
            rd = pad_date(it.get("salesDate"))
            if not rd:
                why.append("発売日の無い巻がある"); break
            vols.append({"number": n, "asin": None, "isbn13": i,
                         "cover_url": re.sub(r"_ex=\d+x\d+", "_ex=300x300", it.get("largeImageUrl") or ""), "release_date": rd})
        rec = {"key": key, "slug": old.get(key, ""), "title": r["題"], "title_kana": clean_kana(its[0].get("titleKana", "")),
               "ndl_kana": (nrec or {}).get("title_kana", ""), "ndl_title": (nrec or {}).get("title", ""),
               "authors": authors, "publisher": pk, "publisher_name": its[0].get("publisherName", ""),
               "imprint": re.sub(r"[\s　]*\d+$", "", its[0].get("seriesName") or "") or r["レーベル(Wiki)"],
               "demographic": demo, "magazine": magkey, "genres": genres, "genres_source": gsrc, "wiki_article": r["記事"],
               "wiki_volumes": r["Wiki巻数欄"], "anilist_id": (am or {}).get("id"), "in_seed2": len(s2), "vols": vols}
        if why:
            hold.append((r, why))
        else:
            sheet.append(rec)
    with open(SHEET, "w", encoding="utf-8", newline="\n") as f:
        for x in sheet:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    with open(HOLD, "w", encoding="utf-8", newline="\n") as f:
        f.write("題\t著者\t記事\tWiki巻数欄\t冊数\t保留の理由\n")
        for r, why in hold:
            f.write(f"{r['題']}\t{r['著者']}\t{r['記事']}\t{r['Wiki巻数欄']}\t{r['楽天の冊数']}\t{' / '.join(why)}\n")
    print(f"対象 {len(tg)} → 全項目そろった {len(sheet)}(冊 {sum(len(x['vols']) for x in sheet)}) / 保留 {len(hold)}")
    cnt = {}
    for _r, why in hold:
        for w in why:
            k = re.split(r"[:(（]", w)[0]
            cnt[k] = cnt.get(k, 0) + 1
    for k, v in sorted(cnt.items(), key=lambda kv: -kv[1]):
        print(f"  保留の理由 {k}: {v}")
    print(f"→ worksheet {SHEET}(slug を記入して --emit) / 保留表 {HOLD}")


def emit():
    import yaml
    idx = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    allslugs = {r[0] for r in idx["d"]}
    pp = os.path.join(ROOT, "data", "seeds", "preorder-pages")
    allslugs |= {fn[:-4] for fn in os.listdir(pp)}
    wrote, errs = [], []
    for l in open(SHEET, encoding="utf-8"):
        x = json.loads(l)
        slug = (x.get("slug") or "").strip()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or len(slug) < 2:
            errs.append((x["title"], f"slug不正: {slug!r}")); continue
        if slug in allslugs:
            errs.append((x["title"], f"slug衝突: {slug}")); continue
        if any(g not in MASTER for g in x["genres"]) or not x["genres"]:
            errs.append((x["title"], "genre不正")); continue
        ys = [int(v["release_date"][:4]) for v in x["vols"]]
        page = {"slug": slug, "title": x["title"], "title_kana": kana_key(x["title_kana"]) and re.sub(r"[\s　]+", "", x["title_kana"]),
                "title_romaji": slug.replace("-", " "),
                "authors": [{"name": a["name"], "kana": a["kana"], "role": a["role"]} for a in x["authors"]],
                "year_started": min(ys), "year_ended": max(ys), "status": "completed",
                "genres": x["genres"], "publisher": x["publisher"], "demographic": x["demographic"]}
        if x.get("magazine"):
            page["magazine"] = x["magazine"]
        if x["genres_source"] == "wikipedia":
            pass                                   # Wikipedia のジャンル欄 = trusted(provisional にしない)
        if x.get("anilist_id"):
            page["anilist_id"] = x["anilist_id"]
        page["_note_origin"] = (f"wiki-nopage 2026-11-15: Wikipedia『{x['wiki_article']}』情報欄({x['wiki_volumes']})×楽天(題完全一致・"
                                f"全{len(x['vols'])}冊・書影あり・漫画ジャンル)×NDL(ヨミ: {x['ndl_kana']})。 ジャンル根拠={x['genres_source']}。"
                                f" キャッチ/あらすじは未作成")
        page["editions"] = [{"type": "standard", "label": "通常版", "publisher": x["publisher"], "imprint": x["imprint"],
                             "volumes": x["vols"]}]
        for v in x["vols"]:
            assert re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", v["release_date"]), (slug, v)
        with open(os.path.join(pp, f"{slug}.yml"), "w", encoding="utf-8", newline="\n") as f:
            f.write(yaml.safe_dump(page, allow_unicode=True, sort_keys=False, width=1000))
        allslugs.add(slug)
        wrote.append(slug)
    open(os.path.join(WORK, "emitted-slugs.txt"), "w", encoding="utf-8").write("\n".join(wrote) + ("\n" if wrote else ""))
    print(f"頁seed {len(wrote)} 件 → data/seeds/preorder-pages/ / 一覧 {os.path.join(WORK, 'emitted-slugs.txt')}")
    for t, e in errs:
        print(f"  見送り {t}: {e}")


if __name__ == "__main__":
    if "--emit" in sys.argv:
        emit()
    else:
        plan(use_ndl="--no-ndl" not in sys.argv)

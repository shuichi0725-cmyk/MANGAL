#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全集 巻マニフェスト生成 (= 2026-07-19。zenshuu-collect の素材を突合し「巻番号→ISBN/題/日付/書影/本番頁」を確定)

入力: .cache/enrich-material/zenshuu/{ndl,rakuten}-{key}.jsonl + .cache/isbn-page-index.json
出力: .cache/enrich-material/zenshuu/manifest-{key}.jsonl (1行=1巻)
      docs/production-diagnostics/zenshuu-holes.tsv (欠け一覧=git永続)

軸の型:
  番号軸あり: tezuka(1-400=NDL series;N) / fujiko-land(vol.N=1-301) / kamuiden(部+巻→通番1-38) / tsuge(1-9) / hasegawa(第N巻=1-33)
  番号軸なし(作品×巻): fujiko-f / mizuki (ISBN集合の被覆で見る。通巻はwiki突合=将来)
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Z = os.path.join(ROOT, ".cache", "enrich-material", "zenshuu")
IDX_P = os.path.join(ROOT, ".cache", "isbn-page-index.json")


def to13(i):
    i = re.sub(r"[^0-9Xx]", "", str(i or ""))
    # ★9桁 = NDL側のISBN10末尾チェックデジット欠落(手塚62行等で実測)。
    #   ISBN13化は本体9桁+EAN検査数字の再計算なので決定的に復元できる。
    if len(i) in (9, 10) and i[:9].isdigit():
        b = "978" + i[:9]
        s = sum(int(c) * (1 if k % 2 == 0 else 3) for k, c in enumerate(b))
        return b + str((10 - s % 10) % 10)
    return i if len(i) == 13 else ""


def jload(p):
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in io.open(p, encoding="utf-8") if l.strip()]


def num_of(key, r, src):
    """ソース行から全集通番を推定。None=番号取れず"""
    ser = r.get("series") or ""
    ttl = r.get("title") or ""
    vol = str(r.get("vol") or "")
    if key == "tezuka":
        import unicodedata
        sern = unicodedata.normalize("NFKC", ser)
        m = (re.search(r"手塚治虫漫画全集[^;]*;\s*(\d+)", sern)
             or re.search(r"手塚治虫漫画全集\s*(\d{1,3})\s*$", sern)
             or (re.search(r"手塚治虫漫画全集[（(](\d+)[)）]", ttl) if src == "rk" else None))
        return int(m.group(1)) if m and int(m.group(1)) <= 400 else None
    if key == "fujiko-land":
        m = re.search(r"(?:vol\.?|;)\s*(\d{1,3})\s*$", ser, re.I)
        return int(m.group(1)) if m and "ランド" in ser else None
    if key == "kamuiden":
        s = vol + " " + ttl
        m = re.search(r"第[1一]部\D{0,4}?(\d+)", s)
        if m and int(m.group(1)) <= 15:
            return int(m.group(1))
        m = re.search(r"第[2二]部\D{0,4}?(\d+)", s)
        if m and int(m.group(1)) <= 12:
            return 15 + int(m.group(1))
        m = re.search(r"外伝\D{0,4}?(\d+)", s)
        if m and int(m.group(1)) <= 11:
            return 27 + int(m.group(1))
        return None
    if key == "tsuge":
        m = re.match(r"\s*(\d)\b", vol) or re.search(r"(\d)\s*[（(]", vol)
        return int(m.group(1)) if m and 1 <= int(m.group(1)) <= 9 else None
    if key == "hasegawa":
        m = re.search(r"長谷川町子全集\s*;\s*(?:第)?(\d+)巻?\s*$", ser)
        return int(m.group(1)) if m and int(m.group(1)) <= 33 else None
    if key == "tsuge-taizen":
        m = re.search(r"第([一二三四五六七八九十]+)巻", ttl)
        if m:
            n = _kn(m.group(1))
            return n if n and n <= 19 else None
        m = re.search(r"別巻([一二三])", ttl)
        if m:
            return 19 + _kn(m.group(1))
        return None
    return None  # fujiko-f / mizuki = 作品×巻軸


TOTALS = {"tezuka": 400, "fujiko-f": 115, "mizuki": 103, "fujiko-land": 301,
          "kamuiden": 38, "tsuge": 9, "hasegawa": 34, "tsuge-taizen": 22}
# hasegawa=本編33+別巻(思い出記念館)=34 / tsuge-taizen=講談社2020・本編19+別巻3=22(ユーザ指摘2026-07-19で追加)

_KANJI = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
def _kn(s):
    """漢数字(一〜十九)→int"""
    if not s: return None
    if s in _KANJI: return _KANJI[s]
    if s.startswith("十"): return 10 + _KANJI.get(s[1:], 0) if len(s) > 1 else 10
    if s.endswith("十"): return _KANJI.get(s[0], 0) * 10
    if "十" in s:
        a, b = s.split("十", 1)
        return _KANJI.get(a, 0) * 10 + _KANJI.get(b, 0)
    return None

# ★ユーザ裁定(2026-07-19)の特例2種:
#  1) 122 = KC版ISBNがNDL/楽天/wiki全滅 → 文庫全集版(楽天在庫あり・書影あり)で代用
#  2) 383-393のエッセイ/対談/小説/シナリオ集 = 非漫画巻だが全集構成として特例掲載。
#     9巻は書誌DB未登録(NDL/楽天/wiki全て不在=1996-97別巻)→ ISBN無し・題のみで登録
TEZUKA_SUBST = {122: {"isbn13": "9784063738162", "title": "タイガーブックス 2",
                      "date": "2011.3", "note": "KC版書誌が全DB不在→文庫全集版で代用(ユーザ裁定)"}}
TEZUKA_TITLE_ONLY = {383: "手塚治虫エッセイ集 第1巻", 384: "手塚治虫小説集", 386: "手塚治虫シナリオ集",
                     387: "手塚治虫エッセイ集 第2巻", 388: "手塚治虫対談集 第1巻", 389: "手塚治虫エッセイ集 第3巻",
                     390: "手塚治虫対談集 第2巻", 392: "手塚治虫エッセイ集 第4巻", 393: "手塚治虫対談集 第3巻"}
NONMANGA_PAT = re.compile(r"エッセイ集|対談集|小説集|シナリオ集|まんが専科|漫画の奥義|総目録")
# 混入除外(全集本体でないISBN帯/シリーズ)
EXCLUDE_SER = {"tezuka": re.compile(r"文庫全集|KCピース|ワイド"),
               "hasegawa": re.compile(r"セット")}


def load_covers():
    """covers seed(isbn13→url)のisbn集合 = 書影が既に確保済みか"""
    import gzip
    p = os.path.join(ROOT, "data", "seeds", "covers.jsonl.gz")
    s = set()
    if os.path.exists(p):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            for l in f:
                try:
                    s.add(json.loads(l)["isbn13"])
                except Exception:
                    pass
    return s


def tezuka_wiki_titles():
    """wiki表(| 262-263 | [[I.L]] …)から 巻番号→題。番号穴の題埋め用"""
    p = os.path.join(Z, "wiki-tezuka.txt")
    out = {}
    if not os.path.exists(p):
        return out
    t = io.open(p, encoding="utf-8").read()
    # 3形式対応: 素の数字セル / <span id="MTnnn">付き / 次行が[[リンク]]でも生テキストでも拾う
    pat = re.compile(
        r'\|\s*(?:rowspan="?\d+"?\s*\|)?\s*(?:<span[^>]*>)?\s*(\d{1,3})(?:-(\d{1,3}))?\s*(?:</span>)?\s*\n'
        r'\|(?:[^|\n]*\|)?\s*(?:\[\[)?([^\]\n|]+)')
    for m in pat.finditer(t):
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        title = re.sub(r"&nbsp;|<[^>]+>", " ", m.group(3)).strip()
        if title and 1 <= a <= 400 and a <= b <= min(a + 30, 400):
            for n in range(a, b + 1):
                out.setdefault(n, title)
    return out


def main():
    idx = json.load(io.open(IDX_P, encoding="utf-8")) if os.path.exists(IDX_P) else {}
    covers = load_covers()
    wiki_tez = tezuka_wiki_titles()
    holes = []
    print(f"{'全集':<12}{'定義':>5}{'ISBN確定':>7}{'番号確定':>7}{'番号穴':>5}{'日付欠':>5}{'書影欠':>5}{'本番未収':>6}")
    for key, total in TOTALS.items():
        import glob as _g
        ndl = []
        # 本体 + 追加スライス(★ドット区切り ndl-{key}.xxx.jsonl のみ。ハイフンだと別キー(tsuge-taizen)を誤吸収する)
        for p in [os.path.join(Z, f"ndl-{key}.jsonl")] + sorted(_g.glob(os.path.join(Z, f"ndl-{key}.*.jsonl"))):
            ndl.extend(jload(p))
        rk = jload(os.path.join(Z, f"rakuten-{key}.jsonl"))
        ex = EXCLUDE_SER.get(key)
        vols = {}  # num or isbn -> row
        by_isbn = {}
        bad_isbn = []
        for src, rows in (("ndl", ndl), ("rk", rk)):
            for r in rows:
                if ex and ex.search((r.get("series") or "") + (r.get("pub") or "")):
                    continue
                i = to13(r.get("isbn"))
                if not i:
                    if r.get("isbn"):  # NDL桁落ち等=壊れISBN(NDL by-title再照会で回収余地)
                        bad_isbn.append(r)
                    continue
                o = by_isbn.setdefault(i, {"isbn13": i, "num": None, "title": "", "date": "", "rk_cover": False})
                n = num_of(key, r, src)
                if n and not o["num"]:
                    o["num"] = n
                if src == "ndl":
                    if not o["title"]:
                        o["title"] = (r.get("title") or "").strip()
                    if not o["date"]:
                        o["date"] = (r.get("date") or "").strip()
                else:
                    o["rk_cover"] = True  # 楽天実在=CDN構築可
                    if not o["title"]:
                        o["title"] = (r.get("title") or "").strip()
                    if not o["date"]:
                        o["date"] = (r.get("salesDate") or "").strip()
        # 同番号に複数ISBN(新装/揺れ)は先勝ち。番号→ISBN map
        num_map = {}
        for i, o in sorted(by_isbn.items()):
            o["prod_slug"] = idx.get(i)
            if o["num"] and o["num"] not in num_map:
                num_map[o["num"]] = o
        # ★手塚: 番号穴をwiki題との正規化マッチで充当(NDL series番号無し行の救済)
        if key == "tezuka":
            def _nt(s):
                import unicodedata
                return re.sub(r"[\s・.,、。()（）\[\]]", "", unicodedata.normalize("NFKC", s)).lower()
            unnum = [o for o in by_isbn.values() if not o["num"]]
            for n in sorted(set(range(1, total + 1)) - set(num_map)):
                wt = wiki_tez.get(n)
                if not wt:
                    continue
                wtn = _nt(re.sub(r"_\(.*", "", wt))
                for o in unnum:
                    tn = _nt(re.sub(r"\d+\s*$", "", o["title"]))
                    if tn and wtn and (tn.startswith(wtn) or wtn.startswith(tn)):
                        o["num"] = n
                        num_map[n] = o
                        unnum.remove(o)
                        break
        # ★長谷川: 別巻(思い出記念館)=34巻目に割当
        if key == "hasegawa":
            for o in by_isbn.values():
                if not o["num"] and "思い出記念館" in o["title"] and 34 not in num_map:
                    o["num"] = 34
                    num_map[34] = o
        # ★手塚 特例適用(ユーザ裁定): 122=文庫版代用 / 383-393=題のみ登録+非漫画flag
        if key == "tezuka":
            for n, sub in TEZUKA_SUBST.items():
                if n not in num_map:
                    o = {"isbn13": sub["isbn13"], "num": n, "title": sub["title"], "date": sub["date"],
                         "rk_cover": True, "cover_ok": True, "prod_slug": idx.get(sub["isbn13"]),
                         "note": sub["note"]}
                    by_isbn[sub["isbn13"]] = o
                    num_map[n] = o
            for n, t in TEZUKA_TITLE_ONLY.items():
                if n not in num_map:
                    o = {"isbn13": None, "num": n, "title": t, "date": "", "rk_cover": False,
                         "cover_ok": False, "prod_slug": None,
                         "note": "書誌DB未登録(NDL/楽天/wiki不在)=題のみ・特例掲載(ユーザ裁定)"}
                    by_isbn[f"_titleonly_{n}"] = o
                    num_map[n] = o
            for o in by_isbn.values():
                if NONMANGA_PAT.search(o.get("title") or ""):
                    o["nonmanga"] = True
        numbered_axis = key not in ("fujiko-f", "mizuki", "fujiko-land")  # ★ランド=作品×巻軸へ変更(wiki/NDLに全巻通番リスト無し)
        missing_nums = sorted(set(range(1, total + 1)) - set(num_map)) if numbered_axis else []
        for o in by_isbn.values():
            o["cover_ok"] = o["rk_cover"] or (o["isbn13"] in covers)
        no_date = [o for o in by_isbn.values() if not o["date"] and not o.get("note")]
        no_cover = [o for o in by_isbn.values() if not o["cover_ok"] and not o.get("note")]
        no_prod = [o for o in by_isbn.values() if not o["prod_slug"]]
        with io.open(os.path.join(Z, f"manifest-{key}.jsonl"), "w", encoding="utf-8") as f:
            for i, o in sorted(by_isbn.items(), key=lambda kv: (kv[1]["num"] or 9999, kv[0])):
                f.write(json.dumps(o, ensure_ascii=False) + "\n")
        nm = "-" if not numbered_axis else str(len(missing_nums))
        print(f"{key:<12}{total:>5}{len(by_isbn):>7}{len(num_map) if numbered_axis else 0:>7}{nm:>5}{len(no_date):>5}{len(no_cover):>5}{len(no_prod):>6}")
        for n in missing_nums:
            wt = wiki_tez.get(n, "") if key == "tezuka" else ""
            holes.append(f"{key}\tnum_missing\t{n}\t\t{wt}")
        for o in no_date:
            holes.append(f"{key}\tno_date\t{o['num'] or ''}\t{o['isbn13']}\t{o['title'][:40]}")
        for o in no_cover:
            holes.append(f"{key}\tno_cover\t{o['num'] or ''}\t{o['isbn13']}\t{o['title'][:40]}")
        for r in bad_isbn:
            holes.append(f"{key}\tbad_isbn\t\t{r.get('isbn')}\t{(r.get('title') or '')[:40]}")
    hp = os.path.join(ROOT, "docs", "production-diagnostics", "zenshuu-holes.tsv")
    with io.open(hp, "w", encoding="utf-8") as f:
        f.write("key\thole\tnum\tisbn13\ttitle\n")
        f.write("\n".join(holes) + "\n")
    print(f"\n欠け一覧 → {hp} ({len(holes)}行)")


if __name__ == "__main__":
    main()

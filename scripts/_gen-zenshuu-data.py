#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全集コーナー view JSON 生成 (= 2026-07-19。A-1コーナー+C6中身ページの表示データ)

入力: .cache/enrich-material/zenshuu/manifest-{key}.jsonl (+ ishinomori: rakuten-ishinomori-full.jsonl
      + fukkan-lineups.json) + data/seeds/covers.jsonl.gz
出力: data/zenshuu-view.json (git追跡・コンポーネントがstatic import)

構造: { collections: [ {key,name,publisher,years,total,linked,complete,axis,covers[3],
        works:[{name, vols:[{n,t,i,d,c,s,nm}]}] | sets:[{name,isbn,date,cover,lineup}] } ] }
再実行=全再生成(冪等)。マニフェスト更新後にこれを再実行して commit。
"""
import gzip
import io
import json
import os
import re
import sys
import unicodedata

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Z = os.path.join(ROOT, ".cache", "enrich-material", "zenshuu")
OUT = os.path.join(ROOT, "data", "zenshuu-view.json")

META = {
    # key: (表示名, 出版社, 定義巻数, 軸)  年はデータから算出
    "mizuki": ("水木しげる漫画大全集", "講談社", 103, "num"),
    "tezuka": ("手塚治虫漫画全集", "講談社", 400, "num"),
    "kamuiden": ("カムイ伝全集", "小学館", 38, "num"),
    "tsuge-taizen": ("つげ義春大全", "講談社", 22, "num"),
    "tsuge": ("つげ義春全集", "筑摩書房", 9, "num"),
    "hasegawa": ("長谷川町子全集", "朝日新聞社", 34, "num"),
    "fujiko-f": ("藤子・F・不二雄大全集", "小学館", 115, "works"),
    "fujiko-land": ("藤子不二雄ランド", "中央公論社", 301, "works"),
    "ishinomori": ("石ノ森章太郎萬画大全集", "角川書店", 500, "sets"),
}


def load_covers():
    m = {}
    p = os.path.join(ROOT, "data", "seeds", "covers.jsonl.gz")
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for l in f:
            try:
                o = json.loads(l)
                m[o["isbn13"]] = o["cover_url"]
            except Exception:
                pass
    return m


_VOLTAIL = re.compile(
    r"[\s　.。･・]*(?:第?[0-9０-９]{1,3}巻?|[（(][0-9０-９]{1,3}[)）]|上|中|下|前編|後編|別巻)"
    r"[\s　]*(?:[（(][^)）]*[)）])?$")


def work_of(title):
    """巻表記を剥がして作品グループ名に。NDL複合題(A ; B)は前半を代表に"""
    t = unicodedata.normalize("NFKC", (title or "").strip())
    t = re.sub(r"\s*\|\s*.*$", "", t)
    t = t.split(" = ")[0].strip()          # ローマ字併記尾を落とす
    t = re.sub(r"\s*:\s*全\s*$", "", t)  # 「〜 : 全」
    if " ; " in t:
        t = t.split(" ; ")[0].strip()
    prev = None
    while prev != t:
        prev = t
        t = _VOLTAIL.sub("", t).strip()
    # 複合巻題「貸本漫画集 1 ロケットマン 他」型 = 数字より前をグループ名に(水木正典題 2026-07-19)
    m = re.match(r"^(.{2,20}?)[\s　]*[0-9０-９]{1,3}[\s　].+", t)
    if m:
        t = m.group(1).strip()
    return t or "その他"


def vol_sort_key(o):
    if o.get("num"):
        return (0, o["num"], "")
    return (1, 0, (o.get("date") or "9999") + (o.get("title") or ""))


def main():
    covers = load_covers()
    cols = []
    for key, (name, pub, total, axis) in META.items():
        if axis == "sets":
            sets = []
            fl = {}
            flp = os.path.join(Z, "fukkan-lineups.json")
            if os.path.exists(flp):
                fl = {int(k): v for k, v in json.load(io.open(flp, encoding="utf-8")).items()}
            rows = [json.loads(l) for l in io.open(os.path.join(Z, "rakuten-ishinomori-full.jsonl"), encoding="utf-8")]
            def ki_of(r):
                m = re.search(r"(\d+)期", r.get("title") or "")
                return int(m.group(1)) if m else 99
            for r in sorted(rows, key=ki_of):
                k = ki_of(r)
                lu = (fl.get(k) or {}).get("lineup", "")
                if lu in ("", "未定"):
                    lu = None
                sets.append({"n": k, "name": f"第{k}期", "isbn": r["isbn"],
                             "date": (r.get("salesDate") or "").replace("頃", ""),
                             "cover": r.get("cover"), "lineup": lu})
            cols.append({"key": key, "name": name, "publisher": pub, "total": total,
                         "years": "2006-2008", "axis": "sets", "linked": 0, "complete": False,
                         "guinness": True, "covers": [s["cover"] for s in sets[:3] if s.get("cover")],
                         "sets": sets})
            continue
        mf = [json.loads(l) for l in io.open(os.path.join(Z, f"manifest-{key}.jsonl"), encoding="utf-8")]
        if key == "tezuka":
            # ★全集400巻純化(2026-07-21 ユーザ指摘「手塚は400冊では?」):
            #   manifestには別版・関連本・NDL別レコードが混ざり478行あった。
            #   ①「全集(NNN(別巻M))」型のISBN付き別レコード → 同番号の番号行(ISBN無)へISBN/日付/slugをマージ
            #   ②番号なし行(講談社豪華版・復刊長編冒険漫画版・立東舎集成・中国語版・DX版401-405等) → drop
            #   = 表は講談社手塚治虫漫画全集の400行(本編382+別巻18)だけにする
            _bynum = {o.get("num"): o for o in mf if o.get("num")}
            _bekkan = re.compile(r"全集[（(](\d+)")
            for o in mf:
                if o.get("num"):
                    continue
                _m = _bekkan.search(o.get("title") or "")
                _tgt = _bynum.get(int(_m.group(1))) if _m else None
                if _tgt is not None and not _tgt.get("isbn13"):
                    _tgt["isbn13"] = o.get("isbn13")
                    if not _tgt.get("date"):
                        _tgt["date"] = o.get("date")
                    if not _tgt.get("prod_slug"):
                        _tgt["prod_slug"] = o.get("prod_slug")
            mf = [o for o in mf if o.get("num")]
        years = sorted(int(m.group(0)) for o in mf if (m := re.search(r"(19|20)\d{2}", str(o.get("date") or ""))))
        groups = {}
        order = []
        for o in sorted(mf, key=vol_sort_key):
            w = work_of(o.get("title") or "")
            if w.startswith(name[:6]):
                w = "その他・巻題確認中"  # NDL/楽天題がシリーズ名だけの行(見た目確認用の仮グループ)
            if w not in groups:
                groups[w] = []
                order.append(w)
            slug = (o.get("prod_slug") or [None])
            slug = slug[0] if isinstance(slug, list) else slug
            groups[w].append({
                "n": o.get("num"), "t": unicodedata.normalize("NFKC", (o.get("title") or "").strip())[:48],
                "i": o.get("isbn13"), "d": (o.get("date") or "")[:7],
                "c": covers.get(o.get("isbn13") or ""), "s": slug,
                **({"nm": True} if o.get("nonmanga") else {}),
            })
        works = [{"name": w, "vols": groups[w]} for w in order]
        linked = sum(1 for ws in works for v in ws["vols"] if v["s"])
        n_isbn = sum(len(ws["vols"]) for ws in works)
        complete = (key in ("mizuki", "kamuiden", "tsuge", "tsuge-taizen", "hasegawa"))
        # コーナー用: 別グループから書影3枚
        cvs = []
        for ws in works:
            for v in ws["vols"]:
                if v["c"]:
                    cvs.append(v["c"])
                    break
            if len(cvs) >= 3:
                break
        cols.append({"key": key, "name": name, "publisher": pub, "total": total,
                     "years": f"{years[0]}-{years[-1]}" if years else "",
                     "axis": axis, "linked": linked, "isbns": n_isbn,
                     "complete": complete, "covers": cvs, "works": works})
    # コーナー表示順 = 完備→大物
    orderkey = ["mizuki", "tezuka", "kamuiden", "tsuge-taizen", "hasegawa", "tsuge", "fujiko-f", "fujiko-land", "ishinomori"]
    cols.sort(key=lambda c: orderkey.index(c["key"]))
    json.dump({"collections": cols}, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    kb = os.path.getsize(OUT) // 1024
    print(f"→ {OUT} ({kb}KB) / {len(cols)}全集 / works計{sum(len(c.get('works') or []) for c in cols)}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""/shinkan(今月の新刊一覧頁)用データ生成 (2026-08-25 ユーザ採用=案E)。

data/calendar/release/{ym}.json([slug,vol,title]) に巻の書影/ISBN/著者/出版社/レーベルを足した
[slug, vol, title, cover|null, isbn13|null, authors, publisher, imprint] を
public/shinkan/{ym}.json へ書く(★2025-01固定床〜当月+3。1行リスト表示+Amazonリンク用 2026-08-25拡張。
2026-08-31 ユーザ指示で床を2026-06→2025-01へ遡行=年×月ナビ対応)。
- 書影はページyml(data/manga.v2)の該当巻cover_url。無ければnull=頁側が題字タイル表示。
- ★フィルタしない(全冊)。死リンク防止は頁側が「一覧索引に居る作品のみリンク化」で担保
  (preview=subset索引でも安全、本番=ほぼ全部リンク)。
- 週次蒸留のstep1(カレンダー再生成の直後)で再実行する。
usage: python scripts/_gen-shinkan-data.py
"""
import datetime
import io
import json
import os

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "calendar", "release")
OUT = os.path.join(ROOT, "public", "shinkan")


def months(center: datetime.date, lo: int, hi: int):
    for k in range(lo, hi + 1):
        m = center.month + k
        y = center.year + (m - 1) // 12
        mm = (m - 1) % 12 + 1
        yield f"{y}-{mm:02d}"


def load_pub2stem() -> dict:
    """公開slug→SRC stem の逆引き (= slug-overrides.yml。改名頁はカレンダー=公開slug、
    manga.v2ファイル名=SRC stem のズレがあり、公開slug直引きだと書影/ISBN/著者が全部落ちる。
    2026-08-31 実踏: 2026-06で93頁=書影欠の主因だった)。"""
    m: dict = {}
    p = os.path.join(ROOT, "data", "seeds", "slug-overrides.yml")
    if os.path.exists(p):
        d = yaml.safe_load(io.open(p, encoding="utf-8")) or {}
        ov = d.pop("overrides", {}) or {}
        for stem, pub in d.items():
            if isinstance(pub, str) and pub != stem:
                m[pub] = stem
        for stem, rec in ov.items():
            pub = (rec or {}).get("slug")
            if pub and pub != stem:
                m[pub] = stem
    return m


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    jst_now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)
    page_cache: dict = {}
    pub2stem = load_pub2stem()

    def page_info(slug: str, num):
        """→ (cover, isbn13, authors文字列, publisher表示名, imprint)。無い項目はNone/空。"""
        if slug not in page_cache:
            info = {"vols": {}, "authors": "", "pub_by_ed": {}}
            p = os.path.join(ROOT, "data", "manga.v2", slug + ".yml")
            if not os.path.exists(p) and slug in pub2stem:
                p = os.path.join(ROOT, "data", "manga.v2", pub2stem[slug] + ".yml")
            if os.path.exists(p):
                try:
                    y = yaml.safe_load(io.open(p, encoding="utf-8"))
                    names = [str(a.get("name")) for a in (y.get("authors") or []) if a.get("name")]
                    orig = [str(a.get("name")) for a in (y.get("original_authors") or []) if a.get("name")]
                    info["authors"] = "・".join(orig + names)[:60]
                    for ed in y.get("editions") or []:
                        pub = ed.get("publisher") or ""
                        imp = ed.get("imprint") or ""
                        for v in ed.get("volumes") or []:
                            n = v.get("number")
                            if n is not None and n not in info["vols"]:
                                info["vols"][n] = (v.get("cover_url"), v.get("isbn13"), pub, imp)
                except Exception:
                    pass
            page_cache[slug] = info
        info = page_cache[slug]
        rec = info["vols"].get(num)
        if not rec and info["vols"]:
            c0 = next(iter(info["vols"].values()))
            rec = (None, None, c0[2], c0[3])
        cov, isbn, pub, imp = rec if rec else (None, None, "", "")
        return cov, (str(isbn) if isbn else None), info["authors"], str(pub or ""), str(imp or "")

    # ★2025-01固定床(ユーザ指定=遡り開始月 2026-08-31)〜当月+3
    floor = datetime.date(2025, 1, 1)
    center = jst_now.date()
    lo = (floor.year - center.year) * 12 + (floor.month - center.month)
    for ym in months(center, lo, 3):
        src = os.path.join(SRC, ym + ".json")
        if not os.path.exists(src):
            continue
        d = json.load(io.open(src, encoding="utf-8"))
        out = {"days": {}, "unknown": []}
        n_cov = n_all = 0

        def row(it):
            nonlocal n_all, n_cov
            slug, num, title = it[0], it[1], it[2]
            cov, isbn, au, pub, imp = page_info(str(slug), num)
            n_all += 1
            n_cov += 1 if cov else 0
            return [slug, num, title, cov, isbn, au, pub, imp]

        for day, items in (d.get("days") or {}).items():
            out["days"][day] = [row(it) for it in items]
        for it in d.get("unknown") or []:
            out["unknown"].append(row(it))
        io.open(os.path.join(OUT, ym + ".json"), "w", encoding="utf-8", newline="\n").write(
            json.dumps(out, ensure_ascii=False, separators=(",", ":")))
        print(f"{ym}: {n_all}冊 (書影{n_cov}) → public/shinkan/{ym}.json")


if __name__ == "__main__":
    main()

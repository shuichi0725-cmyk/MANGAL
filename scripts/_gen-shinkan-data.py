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
- ★巻の引き方(2026-10-11 ユーザ裁定 C): ①カレンダーの ISBN → ②同じ巻番号のうち発売日が合う版 → ③最初の版。
  旧=巻番号だけで最初の版を採り、新装版・文庫版・全巻再刊の発売日に**別の版**の書影/ISBN(=Amazonリンク・
  構造化データ)/出版社/レーベルを出していた(熱愛プリンス 10/13 = カルチュア版1〜25巻に2020年ネクストF版)。
  旧規則と結果が違った冊数を毎回出す(= 取り違えの全数)。--audit で作品ごとの内訳も出す。
usage: python scripts/_gen-shinkan-data.py [--audit]
"""
import collections
import datetime
import io
import json
import os
import sys

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

    audit = "--audit" in sys.argv[1:]
    fixed = []  # (ym, slug, num, 旧規則のISBN, 採ったISBN)

    def page_info(slug: str, num, isbn=None, date: str = ""):
        """→ (cover, isbn13, authors文字列, publisher表示名, imprint)。無い項目はNone/空。
        isbn = カレンダーが持つその巻のISBN / date = 発売日(YYYY-MM-DD か YYYY-MM)。"""
        if slug not in page_cache:
            info = {"vols": {}, "by_isbn": {}, "authors": "", "pub_by_ed": {}}
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
                            rec = (v.get("cover_url"), v.get("isbn13"), pub, imp)
                            ib = v.get("isbn13")
                            if ib and str(ib) not in info["by_isbn"]:
                                info["by_isbn"][str(ib)] = rec
                            if n is not None:
                                info["vols"].setdefault(n, []).append((str(v.get("release_date") or ""), rec))
                except Exception:
                    pass
            page_cache[slug] = info
        info = page_cache[slug]
        cands = info["vols"].get(num) or []
        first = cands[0][1] if cands else None  # 旧規則 = 同じ巻番号の最初の版
        rec = info["by_isbn"].get(str(isbn)) if isbn else None
        if not rec and date:
            rec = next((r for rd, r in cands if rd[:10] == date), None) \
                or next((r for rd, r in cands if rd[:7] == date[:7]), None)
        if not rec:
            rec = first
        if rec and first and rec[1] != first[1]:
            fixed.append((date[:7], slug, num, first[1], rec[1]))
        if not rec and info["vols"]:
            c0 = next(iter(info["vols"].values()))[0][1]
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

        def row(it, date):
            nonlocal n_all, n_cov
            slug, num, title = it[0], it[1], it[2]
            ib = it[3] if len(it) > 3 else None  # 旧カレンダー(3要素)でも動く=発売日で引く
            cov, isbn, au, pub, imp = page_info(str(slug), num, ib, date)
            n_all += 1
            n_cov += 1 if cov else 0
            return [slug, num, title, cov, isbn, au, pub, imp]

        for day, items in (d.get("days") or {}).items():
            out["days"][day] = [row(it, f"{ym}-{day}") for it in items]
        for it in d.get("unknown") or []:
            out["unknown"].append(row(it, ym))
        io.open(os.path.join(OUT, ym + ".json"), "w", encoding="utf-8", newline="\n").write(
            json.dumps(out, ensure_ascii=False, separators=(",", ":")))
        print(f"{ym}: {n_all}冊 (書影{n_cov}) → public/shinkan/{ym}.json")

    # ★版の取り違えを直した数(= 旧規則「巻番号で最初の版」と違う巻を採った冊数)
    by = collections.Counter((ym, s) for ym, s, _n, _o, _w in fixed)
    print(f"版の取り違えを直した: {len(fixed)}冊 / {len({s for _y, s in by})}作品"
          + ("" if audit or not fixed else "(内訳 = --audit)"))
    if audit:
        for (ym, s), c in sorted(by.items()):
            ex = next((f for f in fixed if f[0] == ym and f[1] == s), None)
            print(f"  {ym} {s}: {c}冊 (例 {ex[2]}巻 {ex[3]} → {ex[4]})")


if __name__ == "__main__":
    main()

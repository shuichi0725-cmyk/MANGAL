# -*- coding: utf-8 -*-
"""/shinkan(今月の新刊一覧頁)用データ生成 (2026-08-25 ユーザ採用=案E)。

data/calendar/release/{ym}.json([slug,vol,title]) に **その巻の書影URL** を足した
[slug, vol, title, cover|null] を public/shinkan/{ym}.json へ書く(当月-1〜+3の5ヶ月)。
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


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    jst_now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    cover_cache: dict = {}

    def cover_for(slug: str, num) -> str | None:
        p = os.path.join(ROOT, "data", "manga.v2", slug + ".yml")
        if slug not in cover_cache:
            m = {}
            if os.path.exists(p):
                try:
                    y = yaml.safe_load(io.open(p, encoding="utf-8"))
                    for ed in y.get("editions") or []:
                        for v in ed.get("volumes") or []:
                            if v.get("cover_url") and v.get("number") is not None and v["number"] not in m:
                                m[v["number"]] = v["cover_url"]
                except Exception:
                    pass
            cover_cache[slug] = m
        m = cover_cache[slug]
        return m.get(num) or (next(iter(m.values())) if m and num is None else None)

    for ym in months(jst_now.date(), -1, 3):
        src = os.path.join(SRC, ym + ".json")
        if not os.path.exists(src):
            continue
        d = json.load(io.open(src, encoding="utf-8"))
        out = {"days": {}, "unknown": []}
        n_cov = n_all = 0
        for day, items in (d.get("days") or {}).items():
            rows = []
            for it in items:
                slug, num, title = it[0], it[1], it[2]
                c = cover_for(str(slug), num)
                rows.append([slug, num, title, c])
                n_all += 1
                n_cov += 1 if c else 0
            out["days"][day] = rows
        for it in d.get("unknown") or []:
            slug, num, title = it[0], it[1], it[2]
            out["unknown"].append([slug, num, title, cover_for(str(slug), num)])
            n_all += 1
        io.open(os.path.join(OUT, ym + ".json"), "w", encoding="utf-8", newline="\n").write(
            json.dumps(out, ensure_ascii=False, separators=(",", ":")))
        print(f"{ym}: {n_all}冊 (書影{n_cov}) → public/shinkan/{ym}.json")


if __name__ == "__main__":
    main()

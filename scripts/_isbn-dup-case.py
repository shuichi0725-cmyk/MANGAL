#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ISBNダブリ SPLIT per-case 調査ヘルパ。
使い方: python scripts/_isbn-dup-case.py <stem1,stem2,...>
各頁の series_key/sid と、共有ISBN全冊の 楽天題×発売日×どの頁に居るか を一覧表示(調査のみ)。"""
import os, re, sys, json, sqlite3

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TM = json.load(open(os.path.join(ROOT, ".cache", "isbn-title-map.json"), encoding="utf-8"))
RE_ISBN = re.compile(r"isbn13:\s*'?(\d{13})'?")
RE_TITLE = re.compile(r"^title:\s*(.+?)\s*$", re.M)
RE_SKEY = re.compile(r"^_skey:\s*(.+?)\s*$", re.M)

stems = sys.argv[1].split(",")
con = sqlite3.connect(os.path.join(ROOT, ".cache", "db-v2.sqlite"))

all_isbn = {}
for st in stems:
    mp = os.path.join(ROOT, "data", "manga.v2", st + ".yml")
    sp = os.path.join(ROOT, "data", "manga", st + ".yml")
    t = open(mp, encoding="utf-8").read() if os.path.exists(mp) else ""
    s = open(sp, encoding="utf-8").read() if os.path.exists(sp) else ""
    skey = (RE_SKEY.search(s).group(1) if RE_SKEY.search(s) else "?").strip("'\"")
    sid = None
    if skey != "?":
        r = con.execute("SELECT id FROM series WHERE series_key=?", (skey,)).fetchone()
        sid = r[0] if r else None
    title = (RE_TITLE.search(t).group(1) if RE_TITLE.search(t) else "?").strip("'\"")
    isbns = RE_ISBN.findall(t)
    print(f"== {st} | sid={sid} | skey={skey[:60]} | 頁題={title} | {len(isbns)}冊")
    for i in isbns:
        all_isbn.setdefault(i, []).append(st)

print("\n== ISBN → 楽天題 × 所属頁 ==")
for i in sorted(all_isbn):
    # 種2でこのISBNが本来どのsidに居るか
    rows = con.execute("""SELECT s.id, s.title FROM series s
        JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id
        WHERE v.isbn13=?""", (i,)).fetchall()
    home = ";".join(f"sid{r[0]}:{r[1][:14]}" for r in rows[:2])
    pages = ",".join(all_isbn[i])
    print(f"  {i} | 楽天={str(TM.get(i,'-'))[:34]:34} | 種2本籍={home[:40]:40} | 頁={pages}")

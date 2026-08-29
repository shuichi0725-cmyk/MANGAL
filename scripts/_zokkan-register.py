#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""続巻逆照合の登録器 (= idle-run 柱⑨の裁定側。★上位モデル専権・ユーザGO運用)

入力: .cache/recent-ongoing-volumes.jsonl (= _check-recent-ongoing-volumes.py の収集結果)
対象: trail(末尾続巻)のみ。gap(途中欠番)は登録しない=巻抜けは大半がunder-merge型で
      種4は真の取込もれのみ安全([[volgap_mostly_undermerge]]) → gap-report.tsv に落として per-case。

ゲート(2026-07-28の1,335巻初回登録で実証):
  ①既登録除外 = 本番ISBN索引(.cache/isbn-page-index.json ★実行前に _exists.py --build で最新化)
               + 種4既存ISBN(反映待ちの二重登録防止)
  ②巻番号 = int かつ > 当方max ③非9784除外 ④日付parse不能除外
  ⑤SRC実在(data/manga or source-pages。preorder頁=種4経路が効かない層は見送り)
  ⑥種2キー結線 = 頁の既存ISBN→db-v2逆引き(解決不可=canonical結線頁の疑い→見送り報告)

★著者/小説の判定は**収集側**(_check-recent-ongoing-volumes.py)が持つ(ここには楽天のauthorが来ない)。
  2026-08-29に「原作者名義のみ=原作小説の疑い」ゲートを収集側へ追加した。
  それ以前に登録された分は scripts/_audit-novel-in-manga-page.py で事後検出する。

出力: 種4(volumes-supplement.yml)純粋追加 + volume-gaps-changelog.jsonl + .cache/zokkan-stems.txt
反映: reflect --only を .cache/zokkan-stems.txt から~170個ずつチャンク(コマンドライン長制限)。
usage: python scripts/_zokkan-register.py [--apply]   (無印=dry-run)
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import time

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
SRC_JSONL = os.path.join(".cache", "recent-ongoing-volumes.jsonl")
TODAY = time.strftime("%Y-%m-%d")


def iso(date):
    m = re.match(r"(\d{4})年(\d{2})月(?:(\d{2})日)?", str(date))
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m.group(3) else f"{m.group(1)}-{m.group(2)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--src", default=SRC_JSONL)
    a = ap.parse_args()

    isbn_idx = json.load(open(os.path.join(".cache", "isbn-page-index.json"), encoding="utf-8"))
    supp_isbn = set(re.findall(r"isbn13: '?(\d{13})'?",
                               open(os.path.join("data", "seeds", "volumes-supplement.yml"), encoding="utf-8").read()))

    rows = [json.loads(l) for l in open(a.src, encoding="utf-8")]
    skip = {"既登録(索引)": 0, "既登録(種4)": 0, "非9784": 0, "日付不能": 0, "巻番号不正": 0}
    by_slug, gap_rows = {}, []
    seen_isbn = set()
    for r in rows:
        for g in r.get("gap") or []:
            gap_rows.append((r["slug"], r["title"], g))
        mv = r.get("our_max") or 0
        for t in r.get("trail") or []:
            isbn = str(t.get("isbn") or "")
            vol = t.get("vol")
            if not isbn.startswith("9784"):
                skip["非9784"] += 1; continue
            if isbn in isbn_idx:
                skip["既登録(索引)"] += 1; continue
            if isbn in supp_isbn or isbn in seen_isbn:
                skip["既登録(種4)"] += 1; continue
            if not isinstance(vol, int) or vol <= mv:
                skip["巻番号不正"] += 1; continue
            if not iso(t.get("date")):
                skip["日付不能"] += 1; continue
            seen_isbn.add(isbn)
            by_slug.setdefault(r["slug"], []).append(t)

    # SRC実在 + 種2キー結線
    con = sqlite3.connect(os.path.join(".cache", "db-v2.sqlite"))
    no_src, no_key, entries, stems = [], [], [], set()
    for slug in sorted(by_slug):
        if not (os.path.exists(os.path.join("data", "manga", slug + ".yml"))
                or os.path.exists(os.path.join("data", "seeds", "source-pages", slug + ".yml"))):
            no_src.append(slug); continue
        p = os.path.join("data", "manga.v2", slug + ".yml")
        if not os.path.exists(p):
            no_src.append(slug); continue
        d = yaml.safe_load(open(p, encoding="utf-8"))
        ibs = [str(v["isbn13"]) for e in d.get("editions") or [] for v in e.get("volumes") or [] if v.get("isbn13")]
        keys = []
        if ibs:
            qs = ",".join("?" * len(ibs))
            keys = [k for (k,) in con.execute(
                f"SELECT DISTINCT s.series_key FROM volumes v JOIN editions e ON e.id=v.edition_id "
                f"JOIN series s ON s.id=e.series_id WHERE v.isbn13 IN ({qs})", ibs)]
        if not keys:
            no_key.append(slug); continue
        pub = next((e.get("publisher") for e in d.get("editions") or []
                    if e.get("type") == "standard" and e.get("publisher")), None) \
            or next((e.get("publisher") for e in d.get("editions") or [] if e.get("publisher")), None)
        for t in sorted(by_slug[slug], key=lambda x: x["vol"]):
            e = ["- series_keys:"] + [f"  - {k}" for k in keys[:4]]
            e += ["  qid: null", f"  number: {t['vol']}", f"  isbn13: '{t['isbn']}'",
                  f"  release_date: '{iso(t['date'])}'"]
            if pub:
                e.append(f"  publisher: {pub}")
            e.append("  edition_type: standard")
            tdisp = re.sub(r"[\s　]+", " ", str(t.get("title") or "")).strip().replace('"', "'")
            if tdisp:
                e.append(f'  title_display: "{tdisp}"')
            e += ["  source: rakuten", f"  added_at: '{TODAY}'",
                  "  note: 続巻逆照合(idle-run柱⑨ _check-recent-ongoing-volumes)の検証済みtrail。既登録/巻番号/日付ゲート通過分"]
            entries.append("\n".join(e))
        stems.add(slug)

    n = len(entries)
    print(f"登録候補 {n}巻 / {len(stems)}頁  skip={skip}")
    print(f"見送り: SRC無し{len(no_src)}(preorder層) / 種2キー解決不可{len(no_key)}(canonical疑い)")
    if gap_rows:
        gp = os.path.join("docs", "production-diagnostics", "zokkan-gap-report.tsv")
        os.makedirs(os.path.dirname(gp), exist_ok=True)
        with open(gp, "w", encoding="utf-8", newline="") as f:
            f.write("slug\ttitle\tvol\tisbn\tdate\n")
            for s, ti, g in gap_rows:
                f.write(f"{s}\t{ti}\t{g.get('vol')}\t{g.get('isbn')}\t{g.get('date')}\n")
        print(f"gap(途中欠番・登録せずper-case行き): {len(gap_rows)}巻 → {gp}")
    if not a.apply:
        print("(dry-run: --apply で書込)")
        return
    if not entries:
        print("登録対象なし。")
        return
    with open(os.path.join("data", "seeds", "volumes-supplement.yml"), "a", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(entries) + "\n")
    with open(os.path.join("data", "seeds", "volume-gaps-changelog.jsonl"), "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"op": "zokkan-reverse-register", "count": n, "pages": len(stems),
                            "at": TODAY, "skips": skip}, ensure_ascii=False) + "\n")
    with open(os.path.join(".cache", "zokkan-stems.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(stems)))
    print(f"適用: 種4+{n} / 反映対象 {len(stems)} stem → .cache/zokkan-stems.txt")
    print("次: reflect --only を ~170個ずつチャンク(最後だけ --push)")


if __name__ == "__main__":
    main()

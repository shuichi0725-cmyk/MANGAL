#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抜粋本(既刊の再編)が★楽天の副題にしか現れない★型を検出する。

★なぜ要るか (= 2026-08-01 ユーザ発見「Papa told me が分裂している」から型化)
  promote の DROP_SUBTITLE_PATTERNS は **頁自身(種2由来)の subtitle** を見る。
  ところが実データでは、抜粋本の決定的証拠が **楽天の subTitle にしか無い** ことがある。
  実例: 『Papa told me（春/夏/秋/冬）』 = 種2の subtitle は空、楽天の subTitle が
  「シーズンセレクション」。既刊からの季節別選集(1996-11に4冊同時刊行)なのに、
  本編頁とは別に独立頁化し、さらに春だけ本編へ統合されて **4冊が3か所に割れた**。
  → 既存ルールは構造的にこの層を見られない。ここを埋めるのが本監査。

★これは「候補の列挙」であって自動 drop ではない
  副題の「〜セレクション/傑作集」は **レーベル名/叢書名** のこともある
  (例: 叶精作セレクション、クマのプー太郎セレクション、カプコン・セレクション)。
  その場合は頁の題が独立した実在作品なので **drop したら本物を消す**。
  [[konbini_reprint_sweep]] と同じ教訓 = imprint 一律 drop は不可。人が裁定する。

出力: docs/production-diagnostics/excerpt-subtitle.tsv
使い方:
  python scripts/_audit-excerpt-subtitle.py
  python scripts/_audit-excerpt-subtitle.py --word セレクション   # 語を絞る
"""
import argparse
import collections
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISBN_IDX = os.path.join(ROOT, ".cache", "isbn-page-index.json")
LIST_IDX = os.path.join(ROOT, "data", "manga-list-index.json")
SOURCES = [os.path.join(ROOT, ".cache", "rakuten-isbn-delta.jsonl"),
           os.path.join(ROOT, ".cache", "rakuten-isbn.jsonl")]
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "excerpt-subtitle.tsv")

# 抜粋本(既刊の再編)を示す語。promote の DROP_SUBTITLE_PATTERNS と同族だが、
# ここは「楽天副題」側を見るので素の「セレクション」も拾う(その代わり自動 drop しない)。
WORDS = ("セレクション", "傑作選", "傑作集", "名作選", "名作集", "総集編", "特別編集")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--word", action="append", help="対象語を絞る(既定=全部)")
    a = ap.parse_args()
    words = tuple(a.word) if a.word else WORDS

    if not os.path.exists(ISBN_IDX):
        print(f"★abort: {ISBN_IDX} が無い。先に python scripts/_exists.py --build")
        return 2
    idx = json.load(io.open(ISBN_IDX, encoding="utf-8"))
    print(f"ISBN索引 {len(idx)}件", flush=True)

    # 頁メタ(著者・巻数)= 裁定の材料
    meta = {}
    if os.path.exists(LIST_IDX):
        li = json.load(io.open(LIST_IDX, encoding="utf-8"))
        f = {n: i for i, n in enumerate(li["f"])}
        for r in li["d"]:
            au = [x.split("\t")[0] for x in (r[f["authors"]] or [])]
            meta[r[f["slug"]]] = (r[f["title"]], "・".join(au), r[f["total_volumes"]])

    hits, seen = {}, set()
    for fn in SOURCES:
        if not os.path.exists(fn):
            continue
        n = 0
        for line in io.open(fn, encoding="utf-8", errors="replace"):
            n += 1
            if not any(w in line for w in words):
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            it = o.get("item") or {}
            sub = it.get("subTitle") or ""
            if not any(w in sub for w in words):
                continue  # ★副題に在るものだけ(題に在る分は既存の promote ルールが見ている)
            isbn = (o.get("isbn") or "").replace("-", "")
            if isbn in seen:
                continue
            seen.add(isbn)
            pg = idx.get(isbn)
            if not pg:
                continue  # 本番に載っていない = 無害
            for slug in (pg if isinstance(pg, list) else [pg]):
                hits.setdefault(slug, []).append((isbn, it.get("title") or "", sub,
                                                  it.get("seriesName") or ""))
        print(f"  {os.path.basename(fn)}: {n}行走査 / 累計 頁{len(hits)}", flush=True)

    # 同一著者の他頁が在るか = 「再録元が在る」signal(drop候補が強まる)
    by_author = collections.defaultdict(set)
    for slug, (_t, au, _v) in meta.items():
        for a in au.split("・"):
            if a:
                by_author[a].add(slug)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = 0
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("slug\t頁題\t著者\t頁巻数\t対象巻数\tisbn\t楽天題\t楽天副題\tレーベル\t同著者他頁数\n")
        for slug in sorted(hits):
            t, au, vols = meta.get(slug, ("(索引に無し)", "", ""))
            others = max(0, len({s for a in au.split("・") if a for s in by_author[a]}) - 1)
            vs = sorted(hits[slug])
            for isbn, rt, sub, ser in vs:
                fh.write(f"{slug}\t{t}\t{au}\t{vols}\t{len(vs)}\t{isbn}\t{rt}\t{sub}\t{ser}\t{others}\n")
                rows += 1
    print(f"\n該当 頁{len(hits)}件 / 巻{rows}件 → {os.path.relpath(OUT, ROOT)}")
    print("★これは候補一覧。副題が『レーベル名』のケース(叶精作セレクション型)は drop 禁止 = 人が裁定する。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

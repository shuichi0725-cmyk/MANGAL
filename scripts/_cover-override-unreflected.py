#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""書影seed(cover-override.jsonl)のうち、本番 data/manga.v2 に未反映の頁を算出する。

背景 (= 週次蒸留 skill の手順1 に記載の穴):
  アイドル運転⑩(placeholder-cover-refresh)が seed に足した書影は、頁の再生成が挟まらない。
  step1 の cover-refresh は「自分が差し替えた分」しか promote しないため、
  seed には在るのに本番 yml が古い書影(文字だけの .gif 等)のままの頁が溜まる。

算出法 (= skill 記載の定義):
  cover-override.jsonl を ISBN で「最終行勝ち」に畳み、
  URL(? より前)が該当 slug の yml に無く、ISBN は在る行 = 未反映。

出力:
  --list        未反映 slug を1行1件で stdout (promote の --only-file にそのまま渡せる)
  --detail      ISBN 単位の内訳を TSV で出す
  --out <path>  slug 一覧をファイルへ書く
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "data" / "seeds" / "cover-override.jsonl"
V2 = ROOT / "data" / "manga.v2"
ISBN_INDEX = ROOT / ".cache" / "isbn-page-index.json"

VOL_START = re.compile(r"^\s*-\s+number:")
KV = re.compile(r"^\s*([A-Za-z_0-9]+):\s*(.*)$")


def base_url(u: str) -> str:
    """クエリ(?_ex=...)を落とした比較用URL。解像度サフィックスは描画側(coverSlim)が正規化するので比較に含めない。"""
    if not u:
        return ""
    return u.split("?", 1)[0].strip().strip("'\"")


def load_seed() -> dict[str, dict]:
    """ISBN13 -> 最終行 (最終行勝ち)"""
    folded: dict[str, dict] = {}
    if not SEED.exists():
        return folded
    with SEED.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            isbn = str(row.get("isbn13") or "").strip()
            url = str(row.get("cover_url") or "").strip()
            if not isbn or not url:
                continue
            folded[isbn] = row
    return folded


def parse_volumes(path: Path) -> dict[str, str]:
    """yml を軽量スキャンして isbn13 -> cover_url を返す (巻ブロック単位)。"""
    out: dict[str, str] = {}
    cur_isbn = ""
    cur_cover = ""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return out
    for line in text.splitlines():
        if VOL_START.match(line):
            if cur_isbn:
                out.setdefault(cur_isbn, cur_cover)
            cur_isbn = ""
            cur_cover = ""
            continue
        m = KV.match(line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        if k == "isbn13":
            cur_isbn = v.strip().strip("'\"")
        elif k == "cover_url":
            cur_cover = v.strip().strip("'\"")
    if cur_isbn:
        out.setdefault(cur_isbn, cur_cover)
    return out


def load_isbn_index() -> dict[str, str]:
    """ISBN -> stem (slug改名で seed の slug が死んでいる場合の救済)。"""
    if not ISBN_INDEX.exists():
        return {}
    try:
        raw = json.loads(ISBN_INDEX.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, str] = {}
    for k, v in (raw.items() if isinstance(raw, dict) else []):
        if isinstance(v, str):
            out[str(k)] = v
        elif isinstance(v, dict):
            s = v.get("slug") or v.get("stem") or v.get("file")
            if s:
                out[str(k)] = str(s).replace(".yml", "")
        elif isinstance(v, list) and v:
            out[str(k)] = str(v[0]).replace(".yml", "")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="未反映 slug を1行1件で出す")
    ap.add_argument("--detail", action="store_true", help="ISBN単位の内訳をTSVで出す")
    ap.add_argument("--out", help="slug一覧の書き出し先")
    args = ap.parse_args()

    folded = load_seed()
    if not folded:
        print("cover-override.jsonl が空か読めない", file=sys.stderr)
        return 1

    # slug ごとにまとめて yml を1回だけ読む
    by_slug: dict[str, list[tuple[str, dict]]] = {}
    no_slug: list[str] = []
    for isbn, row in folded.items():
        slug = str(row.get("slug") or "").strip()
        if not slug:
            no_slug.append(isbn)
            continue
        by_slug.setdefault(slug, []).append((isbn, row))

    idx = load_isbn_index()
    unreflected: dict[str, list[tuple[str, str, str]]] = {}
    missing_page = 0
    isbn_absent = 0
    ok = 0

    for slug, items in sorted(by_slug.items()):
        path = V2 / f"{slug}.yml"
        if not path.exists():
            # slug改名の救済: ISBN索引から実ファイルを引く
            alt = ""
            for isbn, _ in items:
                stem = idx.get(isbn)
                if stem and (V2 / f"{stem}.yml").exists():
                    alt = stem
                    break
            if not alt:
                missing_page += len(items)
                continue
            path = V2 / f"{alt}.yml"
            slug = alt
        vols = parse_volumes(path)
        for isbn, row in items:
            if isbn not in vols:
                isbn_absent += 1
                continue
            want = base_url(str(row.get("cover_url") or ""))
            have = base_url(vols.get(isbn) or "")
            if want and want != have:
                unreflected.setdefault(slug, []).append((isbn, have, want))
            else:
                ok += 1

    slugs = sorted(unreflected)
    rows = sum(len(v) for v in unreflected.values())

    if args.detail:
        print("slug\tisbn13\tnow\tseed")
        for s in slugs:
            for isbn, have, want in unreflected[s]:
                print(f"{s}\t{isbn}\t{have}\t{want}")
    elif args.list:
        for s in slugs:
            print(s)
    else:
        print(f"seed ISBN(畳み後)      : {len(folded):,}")
        print(f"一致(反映済)           : {ok:,}")
        print(f"★未反映 ISBN           : {rows:,}  → 頁 {len(slugs):,}")
        print(f"頁が見つからない ISBN  : {missing_page:,} (drop済/改名で索引にも無い)")
        print(f"頁に該当ISBNが無い     : {isbn_absent:,} (版整理で巻が移動した等)")
        print(f"slug欄が空のseed行     : {len(no_slug):,}")
        if slugs:
            print("\n先頭20頁: " + ", ".join(slugs[:20]))

    if args.out:
        Path(args.out).write_text("\n".join(slugs) + ("\n" if slugs else ""), encoding="utf-8")
        print(f"\n書き出し: {args.out} ({len(slugs)} 頁)", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())

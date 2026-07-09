#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日次蒸留 手順7のツール化(2026-07-10): ドラフト頁のcaptionからgenre付与をworksheet方式に。

従来はAIがチェックリスト頼みで手作業付与していた(飛ばし/master外混入のリスク)。
emit→AI記入→apply の3段で、検証(master32・純粋追加)をscript側に固定する。

使い方:
  python scripts/_preorder-genre-worksheet.py --emit   # genres空+caption有のドラフト頁を書き出し
  (AIが .cache/preorders/genre-worksheet.json の genres[] に master32キーを記入。確信なければ空のまま)
  python scripts/_preorder-genre-worksheet.py --apply  # 検証して頁ymlへ純粋追加(+genres_provisional)

ゲート(applyに内蔵):
  - master32(data/genres.yml)外のキーが1つでもあれば全体abort(新語/英語/表記揺れの混入防止)
  - 適用は genres が空の頁のみ(既に付いていればskip=純粋追加)
  - 付与した頁は genres_provisional: true を必ず立てる(AI由来の低信頼マーク)
  - caption無しの頁は emit 時に別途報告(先に _preorder-capture-captions.py で捕捉)
"""
import json, os, sys, glob, argparse

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.join(ROOT, ".cache", "preorders", "genre-worksheet.json")
GENRES_YML = os.path.join(ROOT, "data", "genres.yml")


def master_keys():
    import yaml
    d = yaml.safe_load(open(GENRES_YML, encoding="utf-8"))
    return set(d.keys())


def draft_pages(src):
    import yaml
    for p in sorted(glob.glob(os.path.join(src, "*.yml"))):
        try:
            d = yaml.safe_load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, dict) and "_preorder_draft" in d:
            yield p, d


def emit(src):
    rows, no_caption = [], []
    for p, d in draft_pages(src):
        if d.get("genres"):
            continue                       # 既に付与済み=対象外(純粋追加)
        cap = (d.get("_preorder_draft") or {}).get("rakuten_caption")
        if cap:
            rows.append({"file": os.path.relpath(p, ROOT), "slug": d.get("slug"),
                         "title": d.get("title"), "caption": cap, "genres": []})
        else:
            no_caption.append(d.get("slug"))
    os.makedirs(os.path.dirname(WS), exist_ok=True)
    json.dump(rows, open(WS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"→ worksheet {len(rows)} 件: {os.path.relpath(WS, ROOT)}")
    print(f"  master32キー: {' '.join(sorted(master_keys()))}")
    print("  記入規律: 1-4個・上のキーからのみ・確信なければ空のまま(空=未付与でよい。otherに逃がさない)")
    if no_caption:
        print(f"  ★caption無し {len(no_caption)} 件(genre付与不可→先に _preorder-capture-captions.py): {', '.join(no_caption[:10])}{' …' if len(no_caption) > 10 else ''}")


def apply():
    import yaml
    if not os.path.exists(WS):
        sys.exit("worksheetが無い。先に --emit。")
    rows = json.load(open(WS, encoding="utf-8"))
    master = master_keys()
    bad = [(r.get("slug"), g) for r in rows for g in (r.get("genres") or []) if g not in master]
    if bad:
        for slug, g in bad:
            print(f"  ✗ master32外: {slug} → '{g}'", file=sys.stderr)
        sys.exit(f"abort: master32外キー {len(bad)} 件(closed vocabulary厳守。genres.ymlのキーに直すか空に)")
    applied = skipped_nonempty = skipped_empty = missing = 0
    for r in rows:
        gs = r.get("genres") or []
        if not gs:
            skipped_empty += 1
            continue
        path = os.path.join(ROOT, r["file"])
        if not os.path.exists(path):
            missing += 1
            print(f"  ✗ 頁が無い: {r['file']}", file=sys.stderr)
            continue
        d = yaml.safe_load(open(path, encoding="utf-8"))
        if d.get("genres"):
            skipped_nonempty += 1
            continue                       # 上書き禁止=純粋追加
        d["genres"] = gs[:4]
        d["genres_provisional"] = True     # AI由来の低信頼マーク(必須)
        yaml.dump(d, open(path, "w", encoding="utf-8"),
                  allow_unicode=True, sort_keys=False, width=200)
        applied += 1
    print(f"→ applied={applied}, 記入なしskip={skipped_empty}, 既付与skip={skipped_nonempty}, 頁無し={missing}, overwrites=0")
    if applied:
        print("  ※preview索引の再構築を忘れずに(_build-list-index.py .preview-data/manga .preview-data)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--src", default=os.path.join(ROOT, ".preview-data", "manga"))
    a = ap.parse_args()
    if a.emit:
        emit(a.src)
    elif a.apply:
        apply()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()

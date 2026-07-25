#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日次蒸留 手順7: previewドラフトの vol1 あらすじ(caption)を捕捉(2026-07-09)。

genre/catch/synopsis の元。gen-preview/midfill は harvest caption を保存済みだが、
④回収作は vol1 のあらすじが無い/巻別のことがある → vol1 ISBN で楽天APIを叩き、
同じ応答から itemCaption(genre元)/booksGenreId を捕捉して `_preorder_draft` に保存。
★書影APIと同じく「1回のAPIで全フィールド取る」原則([[acquire_all_obtainable_info]])。

使い方: python scripts/_preorder-capture-captions.py   (rakuten_caption 未取得のdraftのみ叩く)
出力後: あらすじを読んで genre(master32・provisional) を人/AIが付与(この工程はAI判断)。
"""
import glob, os, sys, yaml, json

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from _lookup import rakuten_live_retry, _env

env = _env()
cache = {}
cap = tot = fetched = 0
for p in sorted(glob.glob(os.path.join(ROOT, ".preview-data", "manga", "*.yml"))):
    d = yaml.safe_load(open(p, encoding="utf-8"))
    pd = d.get("_preorder_draft")
    if not pd:
        continue
    tot += 1
    if pd.get("rakuten_caption"):        # 既に捕捉済(harvest等)は叩かない
        cap += 1
        continue
    # vol1 ISBN(シリーズ導入=genre/synopsis元)
    ib1 = None
    for e in d.get("editions", []):
        for v in e.get("volumes", []):
            if v.get("number") == 1:
                ib1 = v.get("isbn13")
    if not ib1:
        for e in d.get("editions", []):
            if e.get("volumes"):
                ib1 = e["volumes"][0].get("isbn13")
    if not ib1:
        continue
    if ib1 not in cache:
        items = rakuten_live_retry(env, isbn=ib1) or []  # ★一括=429をbackoff吸収
        it = items[0] if items else {}
        cache[ib1] = {"caption": str(it.get("itemCaption") or ""), "genreId": it.get("booksGenreId")}
        fetched += 1
    info = cache[ib1]
    if info["caption"]:
        pd["rakuten_caption"] = info["caption"]
        pd["rakuten_genre_id"] = info["genreId"]
        cap += 1
        yaml.dump(d, open(p, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=4096)

print(f"あらすじ捕捉: {cap}/{tot}頁 (API叩き{fetched}回) → 残 {tot - cap} は楽天にあらすじ未掲載(発売近くで付く)")
print("次: 各draftの rakuten_caption を読み、master32からgenre(provisional)を付与(AI判断)。")

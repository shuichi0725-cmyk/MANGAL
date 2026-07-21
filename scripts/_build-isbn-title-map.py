"""楽天harvestから ISBN→題名 マップ構築(過剰統合検出: 少数派巻の実題名照合用)。"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
m = {}
for fn in [f"{ROOT}/.cache/rakuten-isbn-delta.jsonl", f"{ROOT}/.cache/rakuten-isbn.jsonl"]:
    if not os.path.exists(fn):
        continue
    for line in open(fn, encoding="utf-8"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        isbn = str(o.get("isbn") or "")
        it = o.get("item") or {}
        t = it.get("title") or ""
        if len(isbn) == 13 and t:
            m[isbn] = t
print("ISBN→題名:", len(m), flush=True)
json.dump(m, open(f"{ROOT}/.cache/isbn-title-map.json", "w", encoding="utf-8"), ensure_ascii=False)
print("done", flush=True)

"""楽天harvest(.cache/rakuten-isbn*.jsonl)から ISBN→著者(author) マップを構築。
本番著者の一括見直し用(APIを叩かず harvest 種を使う)。"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
m = {}
n = 0
for fn in [f"{ROOT}/.cache/rakuten-isbn-delta.jsonl", f"{ROOT}/.cache/rakuten-isbn.jsonl"]:
    if not os.path.exists(fn):
        continue
    for line in open(fn, encoding="utf-8"):
        n += 1
        try:
            o = json.loads(line)
        except Exception:
            continue
        isbn = str(o.get("isbn") or "")
        it = o.get("item") or {}
        au = it.get("author") or ""
        if len(isbn) == 13 and au:
            m[isbn] = au
print(f"harvest行 {n} / ISBN→著者マップ {len(m)}", flush=True)
json.dump(m, open(f"{ROOT}/.cache/isbn-author-map.json", "w", encoding="utf-8"), ensure_ascii=False)
print("done", flush=True)

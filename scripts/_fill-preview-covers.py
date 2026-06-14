"""[トライアル] 楽天収穫(.cache/rakuten-isbn.jsonl)の書影URLを .preview-data の各巻 cover_url に流し込む。
本番データ(data/manga.v2)は触らない=テスト環境(mangal-preview)で書影表示を試すだけ。

- ISBN13一致で volume.cover_url を純粋追加(既に値がある所は上書きしない)
- largeImageUrl(200x200)優先、無ければ medium/small
- 楽天ISBNは10桁混在の可能性 → 13桁へ正規化して突合
"""
import os, glob, json, yaml

PREVIEW = ".preview-data/manga"
RAKUTEN = ".cache/rakuten-isbn.jsonl"

def to_isbn13(s):
    s = (s or "").replace("-", "").strip()
    if len(s) == 13:
        return s
    if len(s) == 10:
        core = "978" + s[:9]
        t = sum((1 if i % 2 == 0 else 3) * int(c) for i, c in enumerate(core))
        return core + str((10 - t % 10) % 10)
    return s

# 1) preview の全 ISBN を収集
want = set()
files = glob.glob(os.path.join(PREVIEW, "*.yml"))
for f in files:
    d = yaml.safe_load(open(f, encoding="utf-8")) or {}
    for ed in d.get("editions") or []:
        for v in ed.get("volumes") or []:
            isbn = to_isbn13(str(v.get("isbn13") or ""))
            if isbn:
                want.add(isbn)
print(f"preview ISBN: {len(want)} 個 / works {len(files)}")

# 2) 楽天 jsonl を1回走査し、欲しい ISBN の書影だけ拾う
cover = {}
with open(RAKUTEN, encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        it = rec.get("item") or {}
        isbn = to_isbn13(str(rec.get("isbn") or it.get("isbn") or ""))
        if isbn not in want or isbn in cover:
            continue
        url = it.get("largeImageUrl") or it.get("mediumImageUrl") or it.get("smallImageUrl")
        # ★楽天は書影が無いと noimage プレースホルダを返す → 表紙として扱わない
        if url and "noimage" not in url:
            cover[isbn] = url
print(f"書影マッチ: {len(cover)} ISBN")

# 3) preview yml に流し込み
works_with_cover = vols_filled = 0
for f in files:
    d = yaml.safe_load(open(f, encoding="utf-8")) or {}
    changed = False
    has_cover = False
    for ed in d.get("editions") or []:
        for v in ed.get("volumes") or []:
            # 既存の noimage プレースホルダ(前回実行の混入)を掃除
            cur = v.get("cover_url")
            if cur and "noimage" in cur:
                v["cover_url"] = None
                cur = None
                changed = True
            isbn = to_isbn13(str(v.get("isbn13") or ""))
            if isbn in cover:
                has_cover = True
                if not cur:
                    v["cover_url"] = cover[isbn]
                    vols_filled += 1
                    changed = True
    if has_cover:
        works_with_cover += 1
    if changed:
        with open(f, "w", encoding="utf-8") as w:
            yaml.safe_dump(d, w, allow_unicode=True, sort_keys=False, width=10000)

print(f"書影が付いた作品: {works_with_cover}/{len(files)} / 埋めた巻 cover_url: {vols_filled}")

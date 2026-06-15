"""[調査] 欠け巻のうち title+巻番号で楽天生データに在る上限を推定。本番反映なし。"""
import glob, yaml, json, re

def norm(t):
    t = t or ""
    t = re.sub(r"[〔\[(（【].*?[〕\])）】]", "", t)
    for w in ["新装版", "完全版", "愛蔵版", "文庫版", "ワイド版", "コミック版", "新装", "完全", "愛蔵", "BOX"]:
        t = t.replace(w, "")
    t = re.sub(r"\s+", "", t).lower()
    t = re.sub(r"[^\w぀-ヿ一-鿿]", "", t)
    return t

def vnum(t):
    m = re.findall(r"(\d{1,3})", t or "")
    return m[-1] if m else None

idx = {}
with open(".cache/rakuten-isbn.jsonl", encoding="utf-8") as fh:
    for line in fh:
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        it = r.get("item") or {}
        img = it.get("largeImageUrl") or ""
        if img and "noimage" not in img:
            idx[(norm(it.get("title", "")), vnum(it.get("title", "")))] = True
print("楽天index key:", len(idx))

files = glob.glob(".preview-data/manga/*.yml")
gap = match = 0
ex = []
for f in files:
    d = yaml.safe_load(open(f, encoding="utf-8")) or {}
    nt = norm(d.get("title", ""))
    for ed in d.get("editions") or []:
        for v in ed.get("volumes") or []:
            if v.get("cover_url"):
                continue
            gap += 1
            n = str(v.get("number") or "")
            if (nt, n) in idx:
                match += 1
                if len(ex) < 10:
                    ex.append((d.get("slug"), n))
print(f"欠け巻 {gap} / title+番号で楽天に在る(安全上限) {match}")
print("例:", ex)

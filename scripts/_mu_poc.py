"""MangaUpdates PoC: 未マッチ作を日本語titleで検索→年groundingでmatch、 hit率/精度測定。

★礼儀: User-Agent明示 + 1.2秒間隔 + 429指数backoff。 検索recordがリッチ
(description+genres+year)なので per-series呼び不要。 結果は .cache/mu-poc.json にcache。
"""
import sys, json, sqlite3, re, unicodedata, urllib.request, time
from collections import defaultdict
import pykakasi

sys.stdout.reconfigure(encoding="utf-8")
UA = "MANGAL-research/1.0 (https://mangal.shuichi0725.workers.dev; shuichi0725@gmail.com)"
_kks = pykakasi.kakasi()


def tnorm(s):
    return re.sub(r"[^0-9a-zぁ-んァ-ヶ一-龯]", "", unicodedata.normalize("NFKC", (s or "").lower()))


def rnorm(s):
    """romaji 強正規化: マクロン除去 → 英数のみ lower → 連続同字collapse(長音 ou/oo/uu/nn 吸収)。"""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))  # ō→o
    s = re.sub(r"[^0-9a-z]", "", s.lower())
    return re.sub(r"(.)\1+", r"\1", s)  # 連続同字を1つに(ryuu→ryu, ocha o→...)


def kana_romaji(kana):
    """title_kana(カナ)→ ヘボン式 romaji → rnorm。"""
    return rnorm("".join(x["hepburn"] for x in _kks.convert(kana or "")))


def mu(q, n=8):
    body = json.dumps({"search": q, "perpage": n}).encode("utf-8")
    req = urllib.request.Request("https://api.mangaupdates.com/v1/series/search", data=body,
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    for attempt in range(5):
        try:
            return json.loads(urllib.request.urlopen(req, timeout=40).read())
        except Exception as e:
            wait = 2 ** attempt + 1
            print(f"    retry {attempt+1} ({str(e)[:40]}) wait{wait}s", file=sys.stderr)
            time.sleep(wait)
    return {"results": []}


en = json.load(open(".cache/anilist-enrich-map.json", encoding="utf-8"))
matched = set(en.keys())
con = sqlite3.connect(".cache/db-v2.sqlite"); con.text_factory = lambda b: b.decode("utf-8", "replace")
maxvol = defaultdict(int)
for k, mx in con.execute("SELECT s.series_key,MAX(v.number) FROM series s JOIN editions e ON e.series_id=s.id "
                         "JOIN volumes v ON v.edition_id=e.id WHERE v.number BETWEEN 1 AND 200 GROUP BY s.series_key"):
    maxvol[k] = mx or 0
# ★年は巻の最小 release_date から導出(year_started はほぼ空のため)
syear = {}
for k, mn in con.execute("SELECT s.series_key,MIN(v.release_date) FROM series s JOIN editions e ON e.series_id=s.id "
                         "JOIN volumes v ON v.edition_id=e.id WHERE v.release_date IS NOT NULL GROUP BY s.series_key"):
    if mn and mn[:4].isdigit():
        syear[k] = int(mn[:4])
BAD = re.compile(r"全集|大全集|シリーズ|別冊|昔ばなし|笑える話|ハンドブック|アンソロ|総集|傑作|名作|作品集|画集|文庫|大百科|読本")
cand = []
for (k, t, tk) in con.execute("SELECT series_key,title,title_kana FROM series"):
    if k in matched or not t or len(t) < 3:
        continue
    if BAD.search(t):
        continue
    y = syear.get(k)
    if y and 1980 <= y <= 2010 and 3 <= maxvol.get(k, 0) <= 100:
        cand.append((t, y, maxvol[k], tk))
con.close()
# dedup by title, 年代散らす
seen = set(); tests = []
cand.sort(key=lambda x: x[1])
for t, y, v, tk in cand:
    nt = tnorm(t)
    if nt in seen:
        continue
    seen.add(nt); tests.append((t, y, v, tk))
# 150件を年代均等サンプル
if not tests:
    print("候補0件", file=sys.stderr); sys.exit(0)
step = max(1, len(tests) // 150)
sample = tests[::step][:150]
print(f"未マッチ候補(1980-2010 実漫画): {len(tests):,} → PoC {len(sample)}件", file=sys.stderr)

yhit = 0       # 年grounding hit(旧基準=ゆるい)
rhit = 0       # ★romaji gate hit(厳格=正確)
out = []
for i, (t, y, v, tk) in enumerate(sample):
    our_r = kana_romaji(tk) or rnorm(t)   # かな→ヘボン、 無ければ生title(英数題用)
    d = mu(t)
    results = d.get("results") or []
    ybest = None      # 年だけ一致(参考)
    rbest = None      # romaji一致(厳格)
    for r in results:
        rec = r["record"]
        try:
            yd = abs(int(rec.get("year")) - y)
        except (TypeError, ValueError):
            yd = 99
        if yd <= 1 and (ybest is None or yd < ybest[0]):
            ybest = (yd, rec)
        rr = rnorm(rec.get("title"))
        # romaji 強一致: 完全一致 OR 一方が他方を内包(長い副題差を許容、 最短6字)
        if our_r and rr and len(our_r) >= 5 and (our_r == rr or
                (len(our_r) >= 6 and len(rr) >= 6 and (our_r in rr or rr in our_r))):
            score = (0 if our_r == rr else 1, yd)
            if rbest is None or score < rbest[0]:
                rbest = (score, rec, our_r, rr)
    if ybest:
        yhit += 1
    if rbest:
        rhit += 1
        _, rec, our_r, rr = rbest
        ydok = ybest is not None
        out.append({"jp_title": t, "jp_year": y, "jp_vols": v, "our_romaji": our_r, "mu_rnorm": rr,
                    "year_ok": ydok, "mu_id": rec["series_id"], "mu_title": rec["title"],
                    "mu_year": rec.get("year"), "genres": [g["genre"] for g in (rec.get("genres") or [])],
                    "desc": (rec.get("description") or "")[:300]})
    if (i + 1) % 30 == 0:
        print(f"  {i+1}/{len(sample)}  年hit {yhit} / romaji hit {rhit}", file=sys.stderr)
    time.sleep(1.2)

json.dump(out, open(".cache/mu-poc.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
n = len(sample)
print(f"\n★PoC結果: {n}件")
print(f"  年grounding hit(ゆるい)  : {yhit} ({yhit*100//n}%) ← 誤マッチ多数")
print(f"  ★romaji gate hit(厳格)  : {rhit} ({rhit*100//n}%) ← これが正確")
yr = sum(1 for o in out if o["year_ok"])
print(f"  romaji hit中 年も一致     : {yr}/{rhit}(年裏取りも取れる割合)")
print("=== romaji一致サンプル(種2 ⇄ MangaUpdates)16 ===")
for o in out[:16]:
    yf = "✓年" if o["year_ok"] else "  "
    print(f"  {yf}「{o['jp_title'][:16]}」({o['jp_year']}) ⇄ MU「{o['mu_title'][:24]}」({o['mu_year']}) {o['genres'][:3]}")

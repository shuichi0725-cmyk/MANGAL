#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""楽天仮ヨミのNDL照合ワーカー (= A裁定「漏れない仕組み」の実体。日次蒸留の定常工程)

data/seeds/rakuten-kana-pending.jsonl の status=pending を古い順に NDL SRU(by-ISBN)で照合:
  - NDLにタイトルヨミあり → 楽天仮ヨミと比較(正規化: 長音/中点/スペース差は同一視)
      一致   → status=confirmed (verified_at付与)
      不一致 → status=mismatch + docs/production-diagnostics/kana-mismatch.tsv へ(slug直し要否の人間判断)
  - NDL未収載 → pending のまま残る(=漏れない。納本まで毎日試行される)
使い方: python scripts/_verify-kana-pending.py [--limit 200]
レート: 1.2s/req・429即中断。
"""
import json, os, re, sys, time, html, unicodedata, urllib.request, urllib.parse, datetime
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rate_gate  # ★NDLプロセス間グローバル・レートゲート(_lookup等と共有)
PEND = os.path.join(ROOT, "data", "seeds", "rakuten-kana-pending.jsonl")
MISS = os.path.join(ROOT, "docs", "production-diagnostics", "kana-mismatch.tsv")
LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 200
TODAY = datetime.date.today().isoformat()

def norm_kana(s):
    """比較用正規化: NFKC・ひら→カタ・スペース/中点/長音記号ゆらぎを吸収"""
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ん" else c for c in s)
    return re.sub(r"[\s　・=・、。!！?？\-ーf~〜]", "", s)

def ndl_title_kana(isbn):
    """NDL SRUでISBN照会→タイトルヨミ(dc:title内のdcndl:transcription)。無ければNone。"""
    q = f'isbn="{isbn}"'
    p = {"operation": "searchRetrieve", "query": q, "recordSchema": "dcndl", "maximumRecords": "3"}
    req = urllib.request.Request("https://ndlsearch.ndl.go.jp/api/sru?" + urllib.parse.urlencode(p))
    req.add_header("User-Agent", "Mozilla/5.0")
    _rate_gate.wait("ndl", 1.3)  # ★NDLグローバル間隔(_lookup.ndl_live等と共有=並走合算429を防ぐ)
    xml = html.unescape(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    if "Too Many Requests" in xml:
        print("★429→中断(進捗は保存済)"); sys.exit(2)
    m = re.search(r"<dc:title>.*?<dcndl:transcription>([^<]+)</dcndl:transcription>", xml, re.S)
    return m.group(1).strip() if m else None

if not os.path.exists(PEND):
    print("キュー無し"); sys.exit(0)
lines = [json.loads(l) for l in open(PEND, encoding="utf-8") if l.strip()]
pending_idx = [i for i, r in enumerate(lines) if r.get("status") == "pending"]
targets = pending_idx[:LIMIT]
print(f"キュー総数 {len(lines)} / pending {len(pending_idx)} / 今回照合 {len(targets)}")

confirmed = mismatched = still = 0
mm_rows = []
for i in targets:
    r = lines[i]
    try:
        ndl = ndl_title_kana(r["isbn"])
    except SystemExit:
        raise
    except Exception:
        ndl = None
    # NDL間隔は ndl_title_kana内の _rate_gate が担保(ここでの追加sleepは二重=削除)
    if not ndl:
        still += 1
        continue  # NDL未収載=pendingのまま(漏れない)
    na, nb = norm_kana(r.get("title_kana")), norm_kana(ndl)
    # ★NDLヨミは巻番号/上下巻を含む(ズレタ...ボクラ1 / セイデンジョウカン)→末尾の余分(数字/カン/ノ数字)を許容
    def _match(a, b):
        if a == b:
            return True
        for x, y in ((a, b), (b, a)):
            if y.startswith(x) and re.fullmatch(r"[0-9]{1,3}|カン|[0-9]{1,3}カン|ジョウ|ゲ|チュウ", y[len(x):]):
                return True
        return False
    if _match(na, nb):
        r["status"] = "confirmed"
        r["ndl_kana"] = ndl
        r["verified_at"] = TODAY
        confirmed += 1
    else:
        r["status"] = "mismatch"
        r["ndl_kana"] = ndl
        r["verified_at"] = TODAY
        mismatched += 1
        mm_rows.append((r.get("slug"), r.get("isbn"), r.get("title"), r.get("title_kana"), ndl))

# 全行書き戻し(atomic)
tmp = PEND + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    for r in lines:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
os.replace(tmp, PEND)
if mm_rows:
    new = not os.path.exists(MISS)
    with open(MISS, "a", encoding="utf-8") as f:
        if new:
            f.write("slug\tisbn\ttitle\trakuten_kana\tndl_kana\n")
        for row in mm_rows:
            f.write("\t".join(str(x) for x in row) + "\n")
print(f"確定 {confirmed} / 不一致 {mismatched}(→kana-mismatch.tsv) / NDL未収載 {still}(pending継続)")

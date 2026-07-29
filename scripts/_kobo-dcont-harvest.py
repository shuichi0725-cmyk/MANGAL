#!/usr/bin/env python3
"""電子のみ続巻柱(カラー版柱の相方): 紙が止まった後も電子だけ巻が進んでいる作品を検出する。

- 対象: 本番index(status=ongoing)をlatest_date降順に走査(resumable)。
- 各作: Kobo title検索 → ★残差題完全一致(巻トークン剥がし後がnorm一致)のみ採用
  (分冊/合本/カラー版/単話/スピンオフは残差不一致で自然排除)。
- Kobo最大巻 > 紙最大巻 なら候補として記録。
- ★出力は報告層のみ(.cache/kobo-dcont-candidates.jsonl + docs TSV)。自動でseed化しない
  (= Koboの巻番号は新装版採番で紙とズレることがある。採用は裁定後=だろう運転禁止)。
- resumable: .cache/kobo-dcont-done.json。429/失敗=中断→再実行で再開。

使い方: python scripts/_kobo-dcont-harvest.py [--limit 50]
"""
import sys, io, os, re, json, time, argparse, unicodedata, urllib.request, urllib.parse
from urllib.parse import urlparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
DONE = ROOT / ".cache" / "kobo-dcont-done.json"
CAND = ROOT / ".cache" / "kobo-dcont-candidates.jsonl"
TSV = ROOT / "docs" / "production-diagnostics" / "kobo-digital-continuation.tsv"

env = {}
for ln in open(ROOT / ".env.local", encoding="utf-8"):
    if "=" in ln:
        k, v = ln.split("=", 1)
        env[k.strip()] = v.strip()
RREF = env.get("RAKUTEN_REFERER", "https://github.com/")
_o = urlparse(RREF)
RORG = f"{_o.scheme}://{_o.netloc}"

NOISE = re.compile(r"分冊|単話|話売|合本|セット|カラー版|【期間限定|お試し|無料")
VOL_PAT = re.compile(r"[（(【]?\s*(\d{1,3})\s*[)）】]?\s*(?:巻)?\s*$")


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = re.sub(r"[\s　]+", "", s)
    return re.sub(r"[〜~ー\-–—・･。、．，,.:：;；!！?？'’\"”「」『』【】\[\]（）()/／＋+＆&☆★♪]", "", s).lower()


def kobo(params, retries=3):
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env.get("RAKUTEN_ACCESS_KEY", ""),
         "affiliateId": env.get("RAKUTEN_AFFILIATE_ID", ""), "format": "json", "formatVersion": "2",
         "hits": 30, "koboGenreId": "101904"}
    p.update(params)
    u = "https://openapi.rakuten.co.jp/services/api/Kobo/EbookSearch/20170426?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(u, headers={"Referer": RREF, "Origin": RORG, "User-Agent": "Mozilla/5.0"})
    for at in range(retries):
        try:
            time.sleep(1.3)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            if at == retries - 1:
                raise
            time.sleep((5, 30)[min(at, 1)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    a = ap.parse_args()
    sys.path.insert(0, str(ROOT / "scripts"))
    idx = json.load(open(ROOT / "data" / "manga-list-index.json", encoding="utf-8"))
    f = idx["f"]
    si, ti, st, mv, tv, ld = (f.index(x) for x in ("slug", "title", "status", "max_edition_volumes", "total_volumes", "latest_date"))
    done = json.load(open(DONE, encoding="utf-8")) if DONE.exists() else {}
    rows = [d for d in idx["d"] if d[st] == "ongoing" and d[si] not in done]
    rows.sort(key=lambda d: str(d[ld] or ""), reverse=True)
    rows = rows[: a.limit]
    print(f"対象 {len(rows)} 作 (done {len(done)})", flush=True)
    cf = CAND.open("a", encoding="utf-8", newline="\n")
    n_cand = 0
    for d in rows:
        slug, title = d[si], d[ti]
        paper_max = max(int(d[mv] or 0), int(d[tv] or 0))
        tn = norm(title)
        best = None
        try:
            r = kobo({"title": title})
        except Exception as e:
            print(f"★API失敗で中断(再実行で再開): {e}")
            break
        for it in (r.get("Items") or []):
            t = it.get("title") or ""
            if NOISE.search(t) or NOISE.search(it.get("seriesName") or ""):
                continue
            m = VOL_PAT.search(unicodedata.normalize("NFKC", t).strip())
            if not m:
                continue
            base = unicodedata.normalize("NFKC", t)[: m.start()].strip()
            if norm(base) != tn:
                continue  # 残差題完全一致のみ
            vol = int(m.group(1))
            if best is None or vol > best["vol"]:
                best = {"vol": vol, "title": t, "salesDate": it.get("salesDate"),
                        "url": it.get("affiliateUrl") or it.get("itemUrl"), "author": it.get("author")}
        done[slug] = {"paper": paper_max, "kobo": (best or {}).get("vol"), "at": time.strftime("%Y-%m-%d")}
        if best and paper_max and best["vol"] > paper_max:
            rec = {"slug": slug, "title": title, "paper_max": paper_max, "kobo_max": best["vol"],
                   "kobo_title": best["title"], "salesDate": best["salesDate"], "author": best["author"],
                   "url": best["url"], "at": time.strftime("%Y-%m-%d")}
            cf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            cf.flush()
            n_cand += 1
            print(f"  候補 {slug}: 紙{paper_max} < 電子{best['vol']} ({best['salesDate']})", flush=True)
    json.dump(done, DONE.open("w", encoding="utf-8"), ensure_ascii=False)
    # TSV再生成(全candidates)
    os.makedirs(TSV.parent, exist_ok=True)
    seen = {}
    if CAND.exists():
        for l in CAND.open(encoding="utf-8"):
            try:
                c = json.loads(l)
                seen[c["slug"]] = c
            except Exception:
                pass
    with TSV.open("w", encoding="utf-8", newline="\n") as fo:
        fo.write("slug\ttitle\tpaper_max\tkobo_max\tkobo_title\tsalesDate\tauthor\n")
        for c in sorted(seen.values(), key=lambda x: -(x["kobo_max"] - x["paper_max"])):
            fo.write(f"{c['slug']}\t{c['title']}\t{c['paper_max']}\t{c['kobo_max']}\t{c['kobo_title']}\t{c['salesDate']}\t{c['author']}\n")
    print(f"今回候補 {n_cand} / 累計 {len(seen)} → {TSV}")


if __name__ == "__main__":
    main()

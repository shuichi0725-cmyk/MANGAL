#!/usr/bin/env python3
"""NDL 発売日バックフィル収集 (= release_date 欠落巻を NDL 公式日付で埋める準備)。

背景: MADB(種2)は一部巻の release_date が欠落(None)。 これが dedup の日付tie-breakを歪め
(本物がNoneで別社混入に負ける菜#4/#6型)、 DATE_DISORDER も誘発する。 ★ISBN順での推測は危険
なので、 ★NDL SRU を by-ISBN 照会して ★権威的な発売年月(dcterms:date)を取得する。
NDL は古い絶版巻も収録(楽天は絶版を載せない)ため、 ここが本命の日付ソース。

出力: data/seeds/release-date-supplement.jsonl  (= {isbn13, date, source, at} の純粋追加 seed)
  ★種2 sqlite は不変。 promote が release_date=None の時だけこの seed で上書き(別途配線)。

特性: ★resumable(既取得ISBNはskip) / 礼儀レート / 失敗は null 記録で無限retry回避。
使い方: python scripts/_ndl-date-backfill.py            # 全6,097件
        python scripts/_ndl-date-backfill.py 500        # 先頭500件だけ(検証用)
"""
import sys, os, json, time, re, html, urllib.request, urllib.parse, sqlite3
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
OUT = ROOT / "data" / "seeds" / "release-date-supplement.jsonl"
KEEP = ("standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban")
SRU = "https://ndlsearch.ndl.go.jp/api/sru"
SLEEP = 0.2  # 礼儀レート(秒)


def norm_date(raw: str) -> str | None:
    """NDL dcterms:date ('1994.6' / '1994' / '1994.12' / '平成6' 等) → 'YYYY-MM' or 'YYYY'。"""
    if not raw:
        return None
    s = raw.strip()
    m = re.match(r"(\d{4})[.\-/年]\s*(\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.match(r"(\d{4})", s)
    if m:
        return m.group(1)
    return None


def fetch_ndl_date(isbn: str) -> str | None:
    url = (SRU + "?operation=searchRetrieve&recordSchema=dcndl&maximumRecords=1&query="
           + urllib.parse.quote(f"isbn={isbn}"))
    req = urllib.request.Request(url, headers={"User-Agent": "MANGAL-date-backfill/1.0"})
    xml = html.unescape(urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace"))
    m = re.search(r"<dcterms:date[^>]*>(.*?)</dcterms:date>", xml, re.S)
    if m:
        return norm_date(m.group(1))
    m = re.search(r"<dcterms:issued[^>]*>(.*?)</dcterms:issued>", xml, re.S)
    return norm_date(m.group(1)) if m else None


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    con = sqlite3.connect(DB)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    ph = ",".join("?" * len(KEEP))
    rows = con.execute(
        f"""SELECT DISTINCT v.isbn13 FROM volumes v JOIN editions e ON e.id=v.edition_id
            WHERE v.isbn13 IS NOT NULL AND v.isbn13 LIKE '9784%' AND e.type IN ({ph})
              AND (v.release_date IS NULL OR v.release_date='')""", KEEP).fetchall()
    targets = [r[0] for r in rows]

    # resume: 既取得(成功/null両方)はskip
    done = set()
    if OUT.exists():
        for line in OUT.open(encoding="utf-8"):
            try: done.add(json.loads(line)["isbn13"])
            except Exception: pass
    todo = [i for i in targets if i not in done]
    if limit:
        todo = todo[:limit]
    print(f"対象 {len(targets):,} / 既取得 {len(done):,} / 今回 {len(todo):,}")

    f = OUT.open("a", encoding="utf-8")
    ok = miss = err = 0
    for k, isbn in enumerate(todo, 1):
        try:
            d = fetch_ndl_date(isbn)
            rec = {"isbn13": isbn, "date": d, "source": "ndl"}
            if d: ok += 1
            else: miss += 1
        except Exception as e:
            rec = {"isbn13": isbn, "date": None, "source": "ndl", "error": str(e)[:60]}
            err += 1
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if k % 200 == 0:
            f.flush()
            print(f"  {k:,}/{len(todo):,}  (date有{ok:,}/無{miss:,}/err{err:,}) "
                  f"[{time.strftime('%H:%M:%S')}]")
        time.sleep(SLEEP)
    f.close()
    print(f"完了: 取得{ok:,} / NDL無し{miss:,} / err{err:,} → {OUT}")


if __name__ == "__main__":
    main()

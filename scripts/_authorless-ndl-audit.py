"""作画ゼロ(著者欠落)series の すり抜け非漫画を NDL完全title で炙る audit。
★「著者ゼロ=非漫画の赤信号」(かもしれない運転)。 MADB titleが marker欠落だと
既存の非漫画filterを すり抜ける(= 北斗の拳∅=アニメコミックス 型)。 NDLの完全title/NDC/責任表示で検出。

入力: .cache/preprod/authorless_suspects.json (= 作画ゼロ∧クリーンtitle∧ISBN有∧未drop)
出力: .cache/preprod/authorless_ndl.jsonl (= 1行1件 raw。 resumable=既取得ISBNはskip)。
分類は別step(_authorless-classify)で tunable に。 ここは raw取得のみ。
"""
import json
import sys
import os
import re
import html
import time
import urllib.request
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUS = os.path.join(ROOT, ".cache/preprod/authorless_suspects.json")
OUT = os.path.join(ROOT, ".cache/preprod/authorless_ndl.jsonl")
BASE = "https://ndlsearch.ndl.go.jp/api/sru"


def ndl(isbn):
    p = {"operation": "searchRetrieve", "version": "1.2", "recordSchema": "dcndl",
         "maximumRecords": "1", "query": f"isbn={isbn}"}
    url = BASE + "?" + urllib.parse.urlencode(p)
    for _ in range(2):
        try:
            xml = urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 MANGAL-audit"}),
                timeout=25).read().decode("utf-8", "replace")
            break
        except Exception:
            time.sleep(2)
    else:
        return None
    b = html.unescape(xml)
    titles = re.findall(r"<dcterms:title>(.*?)</dcterms:title>", b, re.S)
    ndc = re.findall(r"NDC[0-9]*\">([0-9.]+)<", b)
    cr = [re.sub(r"<[^>]+>", "", x).strip()
          for x in re.findall(r"<dc:creator[^>]*>(.*?)</dc:creator>", b, re.S)]
    nrec = re.search(r"<numberOfRecords>(\d+)", b)
    return {
        "title": titles[0] if titles else "",
        "ndc": ndc[:3],
        "creators": cr[:4],
        "found": int(nrec.group(1)) if nrec else 0,
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    suspects = json.load(open(SUS, encoding="utf-8"))
    done = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                done.add(json.loads(line)["isbn"])
            except Exception:
                pass
    todo = [s for s in suspects if s[3] not in done]
    print(f"全{len(suspects)} / 既取得{len(done)} / 残{len(todo)}", flush=True)
    with open(OUT, "a", encoding="utf-8") as f:
        for i, (sid, key, title, isbn) in enumerate(todo):
            r = ndl(isbn)
            rec = {"sid": sid, "key": key, "db_title": title, "isbn": isbn, "ndl": r}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if (i + 1) % 200 == 0:
                print(f"  {i+1}/{len(todo)} done", flush=True)
            time.sleep(1.0)
    print(f"完了: {len(todo)}件取得", flush=True)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""solo-truncated NO_EVIDENCE 断片の NDL 証拠収集(READ-ONLY・resumable)。

対象 = docs/production-diagnostics/solo-truncated.tsv の NO_EVIDENCE 行。
各件: ①isbn直引き(真の題/巻ラベル/シリーズ名) ②title+creator束縛で全巻列挙(ndc=726.1)。
出力 = .cache/solo-noevi-ndl.jsonl (1行1件・再実行は既取得skip)。
レート = 1.3s/req 厳守([[ndl_access_rate_method]])。429/エラーは記録して続行。
"""
import json, re, sys, time, urllib.parse, urllib.request, html
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
TSV = ROOT / "docs" / "production-diagnostics" / "solo-truncated.tsv"
OUT = ROOT / ".cache" / "solo-noevi-ndl.jsonl"


def sru(cql, max_rec=30):
    q = urllib.parse.urlencode({"operation": "searchRetrieve", "recordSchema": "dcndl",
                                "maximumRecords": str(max_rec), "query": cql})
    time.sleep(1.3)
    req = urllib.request.Request("https://ndlsearch.ndl.go.jp/api/sru?" + q,
                                 headers={"User-Agent": "mangal/1.0"})
    return urllib.request.urlopen(req, timeout=40).read().decode("utf-8")


def parse_bibs(x):
    x = html.unescape(x)
    out = []
    for m in re.finditer(r"<dcndl:BibResource[^>]*>(.*?)</dcndl:BibResource>", x, re.S):
        b = m.group(1)

        def g(t):
            return [re.sub(r"<[^>]+>", "", v).strip()
                    for v in re.findall(f"<{t}[^>]*>(.*?)</{t}>", b, re.S)]
        ids = g("dcterms:identifier")
        isbns = [re.sub(r"[^0-9X]", "", i) for i in ids
                 if re.fullmatch(r"[0-9\-]{9,17}X?", i.strip()) and len(re.sub(r"[^0-9X]", "", i)) in (10, 13)]
        out.append({"title": (g("dcterms:title") or [""])[0][:120],
                    "volume": (g("dcndl:volume") or [""])[0][:40],
                    "series": (g("dcndl:seriesTitle") or [""])[0].split("\n")[0][:60],
                    "issued": (g("dcterms:issued") or [""])[0][:12],
                    "creators": g("foaf:name")[:6],
                    "isbns": isbns[:3]})
    return out


def main():
    rows = [l.rstrip("\n").split("\t") for l in TSV.open(encoding="utf-8")
            if l.startswith("NO_EVIDENCE")]
    done = set()
    if OUT.exists():
        for ln in OUT.open(encoding="utf-8"):
            try:
                done.add(json.loads(ln)["slug"])
            except Exception:
                pass
    todo = [r for r in rows if r[1] not in done]
    print(f"対象 {len(rows)} / 済 {len(done)} / todo {len(todo)}", flush=True)
    with OUT.open("a", encoding="utf-8") as f:
        for n, (cl, slug, title, authors, vtag, isbn, dp, sib) in enumerate(todo, 1):
            rec = {"slug": slug, "title": title, "authors": authors, "vtag": vtag, "isbn": isbn}
            try:
                rec["by_isbn"] = parse_bibs(sru(f'isbn={isbn}'))
            except Exception as e:
                rec["by_isbn_err"] = str(e)[:80]
            au = re.split(r"[・,、/]", authors)[0].strip()
            t = re.sub(r"[〜~].*$", "", title).strip()
            if au and t:
                try:
                    rec["by_series"] = parse_bibs(
                        sru(f'title="{t}" AND creator="{au}" AND ndc=726.1'))
                except Exception as e:
                    rec["by_series_err"] = str(e)[:80]
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if n % 10 == 0:
                print(f"  {n}/{len(todo)}", flush=True)
    print("完了", flush=True)


if __name__ == "__main__":
    main()

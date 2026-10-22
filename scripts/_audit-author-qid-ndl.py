#!/usr/bin/env python3
"""著者QID監査(_audit-author-qid.py)の対象頁について、1巻ISBNのNDL書誌(著者+役割)を集める (2026-10-22)

- 入力: docs/production-diagnostics/author-qid-audit.tsv の slug
- 各頁の standard 版(無ければ先頭版)で番号最小の ISBN を NDL SRU に isbn= で引く。
- 出力: .cache/author-qid-ndl.jsonl(1頁1行・追記・slug で再開)。 NDL の 429 は ndl_live_retry の backoff で吸収し、
  吸収しきれなければ中断(何も書かない = 再実行で続きから)。 ★不在は「ndl_hit: false」として書く(想定内の応答)。
使い方: python scripts/_audit-author-qid-ndl.py [--limit N]
"""
import argparse, csv, json, os, sys

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import _lookup  # noqa: E402

TSV = os.path.join(ROOT, "docs", "production-diagnostics", "author-qid-audit.tsv")
OUT = os.path.join(ROOT, ".cache", "author-qid-ndl.jsonl")


def first_isbn(stem):
    fp = os.path.join(ROOT, "data", "manga.v2", stem + ".yml")
    if not os.path.exists(fp):
        return None
    d = yaml.safe_load(open(fp, encoding="utf-8")) or {}
    eds = d.get("editions") or []
    eds = sorted(eds, key=lambda e: 0 if e.get("type") == "standard" else 1)
    for e in eds:
        vs = [v for v in (e.get("volumes") or []) if v.get("isbn13")]
        if vs:
            vs.sort(key=lambda v: (v.get("number") is None, v.get("number") or 0))
            return str(vs[0]["isbn13"])
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    rows = list(csv.DictReader(open(TSV, encoding="utf-8"), delimiter="\t"))
    stem_of = {r["slug"]: r["stem"] for r in rows}   # ★slug≠ファイル名の頁がある(slug付け替え)
    slugs = [r["slug"] for r in rows]
    done = set()
    if os.path.exists(OUT):
        for ln in open(OUT, encoding="utf-8"):
            try:
                _r = json.loads(ln)
                if _r.get("isbn") or _r.get("ndl_hit"):  # ISBN を引けなかった行は取り直す
                    done.add(_r["slug"])
            except Exception:
                pass
    todo = [s for s in slugs if s not in done]
    if a.limit:
        todo = todo[: a.limit]
    print(f"対象 {len(slugs)} / 済 {len(done)} / 今回 {len(todo)}", flush=True)
    n = 0
    with open(OUT, "a", encoding="utf-8") as fo:
        for s in todo:
            isbn = first_isbn(stem_of[s])
            if not isbn:
                rec = {"slug": s, "isbn": None, "ndl_hit": False}
            else:
                try:
                    hits = _lookup.ndl_live_retry(f'isbn="{isbn}"', maximum=5)
                except Exception as e:
                    print(f"★NDL 中断({e})。 再実行で {s} から続く", flush=True)
                    sys.exit(2)
                hits = [h for h in hits if h.get("isbn") == isbn] or hits[:1]
                rec = {"slug": s, "isbn": isbn, "ndl_hit": bool(hits),
                       "creators": hits[0]["creators"] if hits else [],
                       "creators_raw": hits[0].get("creators_raw", []) if hits else [],
                       "ndl_title": hits[0]["title"] if hits else ""}
            fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fo.flush()
            n += 1
            if n % 50 == 0:
                print(f"  {n}/{len(todo)}", flush=True)
    print(f"完了 {n}件 → {os.path.relpath(OUT, ROOT)}", flush=True)


if __name__ == "__main__":
    main()

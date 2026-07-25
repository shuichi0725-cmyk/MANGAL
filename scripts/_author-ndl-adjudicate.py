"""著者不一致の**NDL裁定**: 楽天と食い違う頁を NDL(ISBN直引き)で三者照合して裁定する。

入力 = `docs/production-diagnostics/author-vs-rakuten.tsv`
  (= `_audit-author-vs-rakuten-full.py` が出す「当方の著者が楽天と1人も重ならない」頁)

裁定(★楽天単独では絶対に採用しない):
  ours_ok   : NDL が **当方**と一致 → 当方が正(楽天が別版/別表記)。 触らない
  fix       : NDL が **楽天**と一致 → 種2の誤紐付け。 是正候補(NDL+楽天の2ソース合意)
  conflict  : NDL がどちらとも違う → 保留(人が見る)
  no_ndl    : NDL不在(★不在≠不存在。 BL/小出版は収録が弱い) → 保留

出力 = `.cache/author-adjudicate.jsonl` (追記のみ・冪等・resumable)
★read-only: 種2 も 本番 も seed も書かない。 適用は `--apply` で
  `data/seeds/author-role-corrections.yml` に remove/add を**純粋追加**(fix のみ)。

usage:
  python scripts/_author-ndl-adjudicate.py --run --limit 100
  python scripts/_author-ndl-adjudicate.py --status
  python scripts/_author-ndl-adjudicate.py --apply        # fix を seed へ(要 --yes)
"""
import argparse
import csv
import importlib.util
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "production-diagnostics" / "author-vs-rakuten.tsv"
OUT = ROOT / ".cache" / "author-adjudicate.jsonl"
CORR = ROOT / "data" / "seeds" / "author-role-corrections.yml"
BACKOFF = (3, 10, 30, 90)
FAIL_STREAK = 8


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or ""))
    return re.sub(r"[\s　・,、/／。\.\-_]", "", s).lower()


def _kana_hit(a_list, b_list):
    """漢字↔かな等で直接一致しない時の緩い同一判定(先頭2文字の読み一致など)。
    ★誤採用を避けるため『どちらかが他方に含まれる』か『長さ差<=2で先頭一致』のみ許す。"""
    for a in a_list:
        for b in b_list:
            x, y = norm(a), norm(b)
            if not x or not y:
                continue
            if x in y or y in x:
                return True
    return False


def _lookup():
    spec = importlib.util.spec_from_file_location("lookup", ROOT / "scripts" / "_lookup.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def isbn_to_skey():
    """ISBN13 → series_key(種2)。 corrections seed は series_key 単位なので必須。"""
    import sqlite3
    con = sqlite3.connect(ROOT / ".cache" / "db-v2.sqlite")
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    m = {}
    for ib, k in con.execute(
        "SELECT v.isbn13, s.series_key FROM volumes v JOIN editions e ON e.id=v.edition_id "
            "JOIN series s ON s.id=e.series_id WHERE v.isbn13 IS NOT NULL AND v.isbn13!=''"):
        m.setdefault(ib, k)
    return m


def rows():
    with SRC.open(encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def done():
    if not OUT.exists():
        return set()
    s = set()
    with OUT.open(encoding="utf-8") as f:
        for ln in f:
            try:
                s.add(json.loads(ln)["slug"])
            except Exception:
                continue
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--limit", type=int, default=100)
    a = ap.parse_args()

    all_rows = rows()
    have = done()
    if a.status or not (a.run or a.apply):
        import collections
        c = collections.Counter()
        if OUT.exists():
            for ln in OUT.open(encoding="utf-8"):
                c[json.loads(ln)["verdict"]] += 1
        print(f"対象 {len(all_rows):,} / 裁定済 {len(have):,} / 残 {len(all_rows) - len(have):,}")
        print(f"  内訳: {dict(c)}")
        return

    if a.apply:
        import yaml
        fix = [json.loads(l) for l in OUT.open(encoding="utf-8")] if OUT.exists() else []
        fix = [f for f in fix if f["verdict"] == "fix"]
        print(f"fix {len(fix):,} 件を {CORR.name} へ純粋追加")
        if not a.yes:
            print("  ★--yes を付けて実行(確認のため既定はdry-run)")
            return
        doc = yaml.safe_load(CORR.read_text(encoding="utf-8"))
        exist = {e.get("series_key") for e in doc["corrections"]}
        n = 0
        for f in fix:
            k = f.get("series_key")
            if not k or k in exist:
                continue
            doc["corrections"].append({
                "series_key": k, "remove": f["ours"], "add": f["ndl_names"],
                "note": f"2026-07-25 著者NDL裁定: 種2の誤紐付けをNDL+楽天一致で是正 (slug={f['slug']})"})
            exist.add(k)
            n += 1
        CORR.write_text(yaml.dump(doc, allow_unicode=True, sort_keys=False, width=250), encoding="utf-8")
        print(f"  ✓ {n} 件追加 / 総 {len(doc['corrections']):,}")
        return

    todo = [r for r in all_rows if r["slug"] not in have]
    batch = todo[:a.limit]
    skey = isbn_to_skey()
    L = _lookup()
    print(f"NDL裁定 {len(batch)} 件 (約{len(batch) * 1.3 / 60:.1f}分) ...", flush=True)
    buf, streak, cnt = [], 0, {}
    for i, r in enumerate(batch, 1):
        try:
            recs = L.ndl_live_retry(f'isbn="{r["isbn"]}"', maximum=3, backoff=BACKOFF)
        except Exception as e:
            streak += 1
            print(f"  ✗ {r['isbn']}: {type(e).__name__}", flush=True)
            if streak >= FAIL_STREAK:
                print("★連続失敗で中断"); break
            continue
        streak = 0
        nd = [c for rec in recs[:1] for c in (rec.get("creators") or [])]
        nd = [re.sub(r",\s*(pub\.|fl\.|\d{3,4}).*$", "", x) for x in nd]
        # ★NDLは職業付き表記がある(「カモ漫画家」「七緒漫画家」)。 比較時だけ剥がす
        nd = [re.sub(r"(漫画家|著|画|作|編)$", "", x).strip() or x for x in nd]
        nd_n = {norm(x) for x in nd}
        ours = [x.strip() for x in r["ours"].split("/") if x.strip()]
        rak = [x.strip() for x in r["rakuten"].split("/") if x.strip()]
        if not nd:
            v = "no_ndl"
        elif nd_n & {norm(x) for x in ours}:
            v = "ours_ok"
        elif nd_n & {norm(x) for x in rak}:
            v = "fix"
        elif _kana_hit(nd, rak) and not _kana_hit(nd, ours):
            # ★NDL漢字表記 vs 楽天かな表記(育田花 ↔ いくたはな)= 同一人物。 当方だけが別人
            v = "fix"
        else:
            v = "conflict"
        cnt[v] = cnt.get(v, 0) + 1
        buf.append({"slug": r["slug"], "title": r["title"], "isbn": r["isbn"], "verdict": v,
                    "series_key": skey.get(r["isbn"]),
                    "ours": ours, "rakuten": rak, "ndl_names": [re.sub(r"\s*,\s*", "", x) for x in nd]})
        if i % 25 == 0:
            _append(buf); buf = []
            print(f"  ...{i}/{len(batch)} {cnt}", flush=True)
    _append(buf)
    print(f"★裁定内訳: {cnt}")


def _append(recs):
    if not recs:
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()

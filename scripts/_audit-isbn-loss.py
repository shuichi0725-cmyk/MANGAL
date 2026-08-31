#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本番から消えたISBNの監視 (= 2026-08-08 新設。ユーザ裁定「本当にある物を消したときに気付けない」)。

★狙い: 欠陥には**非対称性**がある。変なslug・変な題はユーザが見つけてくれるが、
  **存在しないもの**は誰にも見えない。だから「消えた」を機械で名指しする。

  python scripts/_audit-isbn-loss.py --snapshot   # 現在の本番ISBN集合を保存(週次の最後に実行)
  python scripts/_audit-isbn-loss.py              # 前回スナップショットとの差分を監査(preflightが呼ぶ)

判定:
  消えたISBN を「消えてよい理由の台帳」と突合し、**理由の無い消失だけ**を FAIL として出す。
  理由の台帳 = preorder-deny.jsonl / volume-exclude*.yml /
               art-book-exclude-isbn.yml / pending-r2-prune.jsonl(頁ごと廃止) /
               ★isbn-loss-acknowledged.jsonl(2026-08-31新設: 裁定済み削除の消し込み台帳。
                 {isbn13, reason, commit, at} = 根拠コミット必須。promote挙動には一切影響しない純簿記) /
               ★**別頁へ移設**(= 同じISBNが今も本番のどこかに在る)は消失でない。
  ※non-manga-drop.yml は series_key キーで slug/ISBN と直接突合できないため読まない
    (頁dropの消し込みは acknowledged 台帳に根拠コミットを書く)。
出力: docs/production-diagnostics/isbn-loss.tsv
"""
import os, sys, json, gzip, glob, argparse

sys.stdout.reconfigure(encoding="utf-8")
try:
    import yaml
    try:
        from yaml import CSafeLoader as L
    except ImportError:
        from yaml import SafeLoader as L
except ImportError:
    print("pyyaml が要る", file=sys.stderr); sys.exit(2)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MV2 = os.path.join(ROOT, "data", "manga.v2")
SNAP = os.path.join(ROOT, "data", "seeds", "isbn-snapshot.json.gz")   # ★git追跡(別PC/再clone後も効く)
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "isbn-loss.tsv")


def current():
    """本番全頁の isbn13 → slug(公開) を集める。"""
    m = {}
    for p in glob.glob(os.path.join(MV2, "*.yml")):
        try:
            d = yaml.load(open(p, encoding="utf-8"), Loader=L)
        except Exception:
            continue
        if not d:
            continue
        slug = d.get("slug") or os.path.basename(p)[:-4]
        for e in (d.get("editions") or []):
            for vs in [e.get("volumes") or []] + [vv.get("volumes") or [] for vv in (e.get("versions") or [])]:
                for v in vs:
                    if v.get("isbn13"):
                        m[str(v["isbn13"])] = slug
    return m


def _load_reasons():
    """「消えてよい」理由を持つ ISBN / series_key / slug を集める。"""
    isbns, notes = set(), {}

    def add(i, why):
        i = str(i).strip()
        if i:
            isbns.add(i); notes.setdefault(i, why)

    p = os.path.join(ROOT, "data", "seeds", "art-book-exclude-isbn.yml")
    if os.path.exists(p):
        for e in (yaml.load(open(p, encoding="utf-8"), Loader=L) or {}).get("exclude_isbn") or []:
            add(e.get("isbn13"), "art-book-exclude(画集)")
    for name in ("volume-exclude.yml", "volume-exclude-isbn.yml"):
        p = os.path.join(ROOT, "data", "seeds", name)
        if os.path.exists(p):
            doc = yaml.load(open(p, encoding="utf-8"), Loader=L) or {}
            # ★"excludes" = volume-exclude.yml の実トップキー(2026-08-18 バグ修正: これを読んでおらず
            #   exclude済みISBNが全部「理由なし」に化けていた)
            for k in ("excludes", "exclude", "exclude_isbn", "volumes"):
                for e in (doc.get(k) or []):
                    if isinstance(e, dict):
                        add(e.get("isbn13"), f"{name}(混入巻除去)")
                    else:
                        add(e, f"{name}(混入巻除去)")
    # ★消し込み台帳(2026-08-31): 裁定済み削除の純簿記。reason に根拠コミットを含める運用。
    p = os.path.join(ROOT, "data", "seeds", "isbn-loss-acknowledged.jsonl")
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8"):
            ln = ln.strip()
            if ln.startswith("{"):
                try:
                    d = json.loads(ln)
                    add(d.get("isbn13"), f"acknowledged({str(d.get('reason', ''))[:60]})")
                except Exception:
                    pass
    return isbns, notes


def _dropped_slugs():
    """頁ごと非掲載/廃止にした公開slug(= その頁のISBNが消えるのは正当)。"""
    s = {}
    p = os.path.join(ROOT, "data", "seeds", "pending-r2-prune.jsonl")
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8"):
            ln = ln.strip()
            if ln.startswith("{"):
                try:
                    d = json.loads(ln); s[d["slug"]] = "pending-r2-prune(" + str(d.get("reason", ""))[:40] + ")"
                except Exception:
                    pass
    p = os.path.join(ROOT, "data", "seeds", "preorder-deny.jsonl")
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8"):
            ln = ln.strip()
            if ln.startswith("{"):
                try:
                    d = json.loads(ln)
                    if d.get("slug"):
                        s[d["slug"]] = "preorder-deny(" + str(d.get("reason", ""))[:40] + ")"
                except Exception:
                    pass
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", action="store_true", help="現在のISBN集合を保存(週次の最後)")
    a = ap.parse_args()

    cur = current()
    if a.snapshot:
        os.makedirs(os.path.dirname(SNAP), exist_ok=True)
        with gzip.open(SNAP, "wt", encoding="utf-8") as f:
            json.dump(cur, f, ensure_ascii=False)
        print(f"スナップショット保存: {len(cur):,} ISBN → {os.path.relpath(SNAP, ROOT)}")
        return 0

    if not os.path.exists(SNAP):
        print("スナップショット未作成 = 初回。`--snapshot` で基準を作る(監査は次回から)")
        return 0
    with gzip.open(SNAP, "rt", encoding="utf-8") as f:
        prev = json.load(f)

    gone = {i: s for i, s in prev.items() if i not in cur}
    if not gone:
        print(f"ISBN消失監視: 消失0 (前回 {len(prev):,} → 現在 {len(cur):,})")
        return 0

    reason_isbn, notes = _load_reasons()
    drops = _dropped_slugs()
    rows, unexplained = [], 0
    for i, old_slug in sorted(gone.items()):
        if i in reason_isbn:
            why = notes[i]
        elif old_slug in drops:
            why = drops[old_slug]
        else:
            why = ""      # ★理由なし = 実在する巻を黙って消した疑い
            unexplained += 1
        rows.append((i, old_slug, why or "★理由なし"))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write("isbn13\t前回の頁\t理由\n")
        for r in rows:
            f.write("\t".join(r) + "\n")

    print(f"ISBN消失監視: 消失 {len(gone):,} 件 / うち★理由なし {unexplained:,} 件")
    print(f"→ {os.path.relpath(OUT, ROOT)}")
    if unexplained:
        print("★理由なしの消失 = **実在する巻を黙って消した疑い**。台帳(non-manga-drop/deny/exclude/prune)に")
        print("  根拠が無いのに本番から消えている。1件ずつ調べて、復活させるか台帳に理由を書くこと。")
        for i, s, w in [r for r in rows if r[2] == "★理由なし"][:20]:
            print(f"    {i}  (前回: {s})")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

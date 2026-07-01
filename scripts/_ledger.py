#!/usr/bin/env python3
"""統合台帳クエリ = 「このslug、過去に何をした?」を一発で引く。

台帳(operations.jsonl)は9千行超で目grepは形骸化する → cleanup着手前はこれで確認する。
CLAUDE.md 統合台帳 厳守ルール4の実行手段。

使い方:
  python scripts/_ledger.py <slug|部分一致>      # 操作履歴(at昇順) + holes状態
  python scripts/_ledger.py <slug> --raw         # raw行も表示
  python scripts/_ledger.py --stale              # 台帳より新しい未集約changelogを列挙
"""
import sys, json, gzip, os, glob
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN = os.path.join(ROOT, "data", "seeds", "intake-manifest")
OPS = os.path.join(MAN, "operations.jsonl")
HOLES = os.path.join(MAN, "holes-snapshot.jsonl.gz")

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--stale" in sys.argv:
        newer = [f for f in glob.glob(os.path.join(ROOT, "data", "seeds", "*changelog*.jsonl"))
                 if os.path.getmtime(f) > os.path.getmtime(OPS)]
        if newer:
            print(f"★未集約changelog {len(newer)}件 → python scripts/_manifest-consolidate-ops.py を回す:")
            for f in newer: print("  " + os.path.basename(f))
        else:
            print("台帳は最新(未集約changelog無し)")
        return
    if not args:
        print(__doc__); return
    q = args[0]
    show_raw = "--raw" in sys.argv

    # 操作履歴
    hits = []
    for ln in open(OPS, encoding="utf-8"):
        try: o = json.loads(ln)
        except Exception: continue
        s = str(o.get("slug") or "")
        rel = str(o.get("related") or "")
        if q in s or q in rel:
            hits.append(o)
    print(f"=== 操作履歴: '{q}' → {len(hits)}件 ===")
    from collections import Counter
    bysrc = Counter(o.get("op_source", "") for o in hits)
    print("  種別:", ", ".join(f"{k}×{n}" for k, n in bysrc.most_common()))
    # 各op_sourceの最新1件ずつ + 全体の直近5件
    seen = {}
    for o in hits: seen[o.get("op_source", "")] = o  # at昇順なので最後が最新
    print("  各種別の最新:")
    for k, o in seen.items():
        print(f"    {str(o.get('at',''))[:16]:17}{k:24}{o.get('slug','')}" + (f" (rel:{o['related']})" if o.get('related') else ""))
        if show_raw:
            print("       raw:", json.dumps(o.get("raw", {}), ensure_ascii=False)[:240])

    # holes状態
    if os.path.exists(HOLES):
        found = []
        with gzip.open(HOLES, "rt", encoding="utf-8") as f:
            for ln in f:
                try: h = json.loads(ln)
                except Exception: continue
                if q in str(h.get("slug", "")):
                    found.append(h)
        print(f"=== holes snapshot: {len(found)}件 (取得 {os.path.getmtime(HOLES) and __import__('datetime').datetime.fromtimestamp(os.path.getmtime(HOLES)).strftime('%Y-%m-%d')}) ===")
        for h in found[:10]:
            print(f"  {h.get('slug','')}: holes={h.get('holes', [])}")

if __name__ == "__main__":
    main()

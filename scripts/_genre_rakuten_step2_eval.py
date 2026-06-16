#!/usr/bin/env python3
"""
genre×楽天あらすじ step2 = held-out 検証 (= [[genre_from_rakuten_story_plan]])

LLM が caption だけで予測した結果(heldout-out)を、教師の trusted ラベル(heldout-truth)と
突合し、**ジャンル別 適合率/再現率/F1** を算出する。これが「学習の中身」の本体。

成果物:
  .cache/genre-rakuten/step2-metrics.json
  docs/genre-rakuten-learning.md の step2 セクションに表を流し込む(別途手で貼る or 確認用に print)
"""
import json, sys
from pathlib import Path
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".cache" / "genre-rakuten"
TRUTH = OUT / "heldout-truth.jsonl"
PREDS = OUT / "heldout-out"

import yaml
MASTER = list(yaml.safe_load((ROOT / "data" / "genres.yml").read_text(encoding="utf-8")).items())
MASTER_NAME = {k: v["name"] for k, v in MASTER}
UNLEARNABLE = {"gag", "romcom", "samurai", "4-koma"}
LEARNABLE = set(k for k, _ in MASTER if k not in UNLEARNABLE)


def main():
    truth = {}
    for line in TRUTH.open(encoding="utf-8"):
        r = json.loads(line)
        truth[r["slug"]] = set(g for g in r["label"] if g in LEARNABLE)

    preds = {}
    invalid_keys = defaultdict(int)
    nfiles = 0
    for fp in sorted(PREDS.glob("batch-*.json")):
        nfiles += 1
        try:
            arr = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ! 読めず {fp.name}: {e}", flush=True)
            continue
        for r in arr:
            gid = r.get("id")
            gs = r.get("genres") or []
            clean = set()
            for g in gs:
                if g in LEARNABLE:
                    clean.add(g)
                else:
                    invalid_keys[g] += 1
            if gid is not None:
                preds[gid] = clean

    common = [s for s in truth if s in preds]
    missing = [s for s in truth if s not in preds]
    print(f"truth: {len(truth):,} / preds: {len(preds):,} / 突合: {len(common):,} / 欠損: {len(missing):,}", flush=True)
    if invalid_keys:
        print(f"  無効キー(除外): {dict(sorted(invalid_keys.items(), key=lambda x:-x[1])[:10])}", flush=True)

    # per-genre
    tp = defaultdict(int); fp = defaultdict(int); fn = defaultdict(int)
    confus = defaultdict(lambda: defaultdict(int))  # truth genre → 誤って付けた/落とした
    for s in common:
        T = truth[s]; P = preds[s]
        for g in T & P: tp[g] += 1
        for g in P - T: fp[g] += 1
        for g in T - P: fn[g] += 1

    rows = []
    for g in sorted(LEARNABLE, key=lambda x: -(tp[x]+fn[x])):
        sup = tp[g] + fn[g]          # truth正例(support)
        pp = tp[g] + fp[g]           # 予測正例
        prec = tp[g] / pp if pp else 0.0
        rec = tp[g] / sup if sup else 0.0
        f1 = 2*prec*rec/(prec+rec) if (prec+rec) else 0.0
        rows.append({"genre": g, "name": MASTER_NAME[g], "support": sup,
                     "pred": pp, "tp": tp[g], "fp": fp[g], "fn": fn[g],
                     "precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3)})

    # micro/macro
    TP = sum(tp.values()); FP = sum(fp.values()); FN = sum(fn.values())
    micro_p = TP/(TP+FP) if (TP+FP) else 0
    micro_r = TP/(TP+FN) if (TP+FN) else 0
    micro_f = 2*micro_p*micro_r/(micro_p+micro_r) if (micro_p+micro_r) else 0
    macro_f = sum(r["f1"] for r in rows)/len(rows)

    metrics = {"common": len(common), "missing": len(missing),
               "micro": {"precision": round(micro_p,3), "recall": round(micro_r,3), "f1": round(micro_f,3)},
               "macro_f1": round(macro_f,3), "rows": rows,
               "missing_slugs": missing[:50]}
    (OUT / "step2-metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    # markdown 表
    print("\n| genre | 名称 | support | pred | P | R | F1 |", flush=True)
    print("|---|---|---:|---:|---:|---:|---:|", flush=True)
    for r in rows:
        print(f"| {r['genre']} | {r['name']} | {r['support']} | {r['pred']} | "
              f"{r['precision']:.2f} | {r['recall']:.2f} | {r['f1']:.2f} |", flush=True)
    print(f"\nmicro P/R/F1 = {micro_p:.3f}/{micro_r:.3f}/{micro_f:.3f}  macro-F1 = {macro_f:.3f}", flush=True)

    # 適用候補(高精度): precision>=0.80 & support>=20
    cand = [r for r in rows if r["precision"] >= 0.80 and r["support"] >= 20]
    print("\n-- 適用候補(P≥0.80 & support≥20)--", flush=True)
    for r in cand:
        print(f"  {r['genre']:14s} P={r['precision']:.2f} R={r['recall']:.2f} (sup {r['support']})", flush=True)
    print(f"\nmetrics → {OUT/'step2-metrics.json'}", flush=True)


if __name__ == "__main__":
    main()

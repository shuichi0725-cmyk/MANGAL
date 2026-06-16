#!/usr/bin/env python3
"""
タグ(要素)× 楽天あらすじ step2 = held-out 検証(タグ別 適合率/再現率)。
ジャンル版 _genre_rakuten_step2_eval.py のタグ版。

評価母数 = held-out 3,000 のうち trusted theme tag(vocab内)を ≥1 持つ work
(= truth が非自明なもの)。truth は不完全なので測定Pは下限値(FPサンプルで別途吟味)。
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
TRUTH = OUT / "heldout-tag-truth.jsonl"
PREDS = OUT / "heldout-tag-out"

import yaml
vocab = json.loads((OUT / "tag-vocab.json").read_text(encoding="utf-8"))
JA = {v["key"]: v["ja"] for v in vocab}
VOCAB = set(v["key"] for v in vocab)


def main():
    truth = {}
    for line in TRUTH.open(encoding="utf-8"):
        r = json.loads(line)
        truth[r["slug"]] = set(t for t in r["tags"] if t in VOCAB)

    preds = {}
    invalid = defaultdict(int)
    for fp in sorted(PREDS.glob("batch-*.json")):
        try:
            arr = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ! {fp.name}: {e}", flush=True); continue
        for r in arr:
            gid = r.get("id")
            clean = set()
            for t in (r.get("tags") or []):
                if t in VOCAB:
                    clean.add(t)
                else:
                    invalid[t] += 1
            if gid is not None:
                preds[gid] = clean

    # 評価母数 = truth に ≥1 タグ
    eval_slugs = [s for s in truth if truth[s] and s in preds]
    print(f"truth work: {len(truth):,} / preds: {len(preds):,} / 評価母数(truth≥1タグ): {len(eval_slugs):,}", flush=True)
    if invalid:
        print(f"  無効キー上位: {dict(sorted(invalid.items(), key=lambda x:-x[1])[:10])}", flush=True)

    tp = defaultdict(int); fp = defaultdict(int); fn = defaultdict(int)
    for s in eval_slugs:
        T = truth[s]; P = preds.get(s, set())
        for g in T & P: tp[g] += 1
        for g in P - T: fp[g] += 1
        for g in T - P: fn[g] += 1

    rows = []
    allkeys = set(list(tp)+list(fp)+list(fn))
    for g in sorted(allkeys, key=lambda x: -(tp[x]+fn[x])):
        sup = tp[g]+fn[g]; pp = tp[g]+fp[g]
        prec = tp[g]/pp if pp else 0.0
        rec = tp[g]/sup if sup else 0.0
        f1 = 2*prec*rec/(prec+rec) if (prec+rec) else 0.0
        rows.append({"tag": g, "ja": JA.get(g,g), "support": sup, "pred": pp,
                     "tp": tp[g], "fp": fp[g], "fn": fn[g],
                     "precision": round(prec,3), "recall": round(rec,3), "f1": round(f1,3)})

    TP=sum(tp.values()); FP=sum(fp.values()); FN=sum(fn.values())
    micro_p=TP/(TP+FP) if (TP+FP) else 0; micro_r=TP/(TP+FN) if (TP+FN) else 0
    micro_f=2*micro_p*micro_r/(micro_p+micro_r) if (micro_p+micro_r) else 0

    (OUT/"tag-step2-metrics.json").write_text(json.dumps(
        {"eval_n": len(eval_slugs),
         "micro": {"precision": round(micro_p,3),"recall": round(micro_r,3),"f1": round(micro_f,3)},
         "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n| tag | 日本語 | support | pred | P | R | F1 |", flush=True)
    print("|---|---|---:|---:|---:|---:|---:|", flush=True)
    for r in rows:
        print(f"| {r['tag']} | {r['ja']} | {r['support']} | {r['pred']} | "
              f"{r['precision']:.2f} | {r['recall']:.2f} | {r['f1']:.2f} |", flush=True)
    print(f"\nmicro P/R/F1 = {micro_p:.3f}/{micro_r:.3f}/{micro_f:.3f}", flush=True)

    cand = [r for r in rows if r["precision"] >= 0.70 and r["support"] >= 10]
    print(f"\n-- 適用候補(P≥0.70 & support≥10)= {len(cand)}タグ --", flush=True)
    for r in sorted(cand, key=lambda x:-x["f1"]):
        print(f"  {r['tag']:24s}{r['ja']:10s} P={r['precision']:.2f} R={r['recall']:.2f} (sup {r['support']})", flush=True)
    print(f"\nmetrics → {OUT/'tag-step2-metrics.json'}", flush=True)


if __name__ == "__main__":
    main()

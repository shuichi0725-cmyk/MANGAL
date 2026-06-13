"""catch-out/batch-*.json を data/seeds/catch-ja.json に統合(純粋追加)。
既存キーは保護(上書きしない)。 長さ/空を検証。 統合後に件数とサンプルを報告。"""
import os, glob, json

SEED = "data/seeds/catch-ja.json"
existing = json.load(open(SEED, encoding="utf-8")) if os.path.exists(SEED) else {}
before = len(existing)

added = skipped_dup = skipped_bad = 0
samples = []
for bf in sorted(glob.glob(".cache/catch-out/batch-*.json")):
    try:
        d = json.load(open(bf, encoding="utf-8"))
    except Exception as e:
        print(f"  PARSE-FAIL {bf}: {e}")
        continue
    for slug, copy in d.items():
        copy = (copy or "").strip()
        if not copy or len(copy) < 20 or len(copy) > 90:
            skipped_bad += 1
            continue
        if slug in existing:
            skipped_dup += 1
            continue
        existing[slug] = copy
        added += 1
        if len(samples) < 8:
            samples.append((slug, copy))

# slugソートで安定出力
out = {k: existing[k] for k in sorted(existing.keys())}
with open(SEED, "w", encoding="utf-8") as w:
    json.dump(out, w, ensure_ascii=False, indent=2)
    w.write("\n")

print(f"既存={before} / 追加={added} / 重複skip={skipped_dup} / 不良skip={skipped_bad} / 合計={len(out)}")
print("--- サンプル ---")
for s, c in samples:
    print(f"[{len(c)}字] {s}: {c}")

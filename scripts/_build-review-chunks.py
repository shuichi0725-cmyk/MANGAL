"""
en filled 40,990 entries を 80 chunk (= 各 ~512 entries) に分割。
agent が読みやすい single-line format (= 1 entry / 1 line) で書き出し。

output: .cache/review/chunk-001.txt ~ chunk-080.txt
"""
import yaml
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED3 = ROOT / "data" / "seeds" / "series-supplement-v2.yml"
OUTDIR = ROOT / ".cache" / "review" / "chunks"

with SEED3.open("r", encoding="utf-8") as f:
    doc = yaml.safe_load(f)

# en filled entries 抽出
entries = []
for i, e in enumerate(doc["series"]):
    en = (e.get("alternative_titles") or {}).get("en")
    if not en:
        continue
    key = e["key"]
    parts = key.split("|")
    name_parts = [p[5:] for p in parts if p.startswith("name:")]
    title = name_parts[-1] if name_parts else ""
    creator = name_parts[0] if len(name_parts) >= 2 else None
    sub_parts = [p[4:] for p in parts if p.startswith("sub:")]
    sub = sub_parts[0] if sub_parts else None
    entries.append({
        "idx": i,
        "title": title,
        "creator": creator,
        "sub": sub,
        "en": en,
        "key": key,
    })

print(f"Total en-filled entries: {len(entries)}")

# シャッフル (= seed 固定で再現可能)
random.seed(20260522)
random.shuffle(entries)

# 80 chunks に分割
N_CHUNKS = 80
chunk_size = (len(entries) + N_CHUNKS - 1) // N_CHUNKS
print(f"Chunks: {N_CHUNKS} files, ~{chunk_size} entries each")

OUTDIR.mkdir(parents=True, exist_ok=True)
# 既存 chunk を 一旦削除
for old in OUTDIR.glob("chunk-*.txt"):
    old.unlink()

for ci in range(N_CHUNKS):
    start = ci * chunk_size
    end = min(start + chunk_size, len(entries))
    chunk = entries[start:end]
    if not chunk:
        break
    fpath = OUTDIR / f"chunk-{ci+1:03d}.txt"
    with fpath.open("w", encoding="utf-8") as f:
        for e in chunk:
            # 1 entry = 1 line; use ` | ` as separator
            parts = [f'idx={e["idx"]}', f'title={e["title"]}']
            if e["creator"]:
                parts.append(f'creator={e["creator"]}')
            if e["sub"]:
                parts.append(f'sub={e["sub"]}')
            parts.append(f'en={e["en"]}')
            f.write(" | ".join(parts) + "\n")

# manifest 出力
manifest_path = OUTDIR / "manifest.txt"
with manifest_path.open("w") as f:
    f.write(f"total entries: {len(entries)}\n")
    f.write(f"chunks: {N_CHUNKS}\n")
    f.write(f"chunk size: ~{chunk_size}\n")
    for ci in range(N_CHUNKS):
        f.write(f"chunk-{ci+1:03d}.txt: {min(chunk_size, len(entries)-ci*chunk_size)} entries\n")
print(f"Wrote chunks to {OUTDIR}")
print(f"First chunk preview:")
with (OUTDIR / "chunk-001.txt").open() as f:
    for i, line in enumerate(f):
        if i >= 3: break
        print(f"  {line.rstrip()[:120]}")

"""C-2a candidates を 100件/batch に分割して input-NNN.json として保存。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / ".cache" / "c2a" / "input.json"
OUT_DIR = ROOT / ".cache" / "c2a"

data = json.loads(SRC.read_text(encoding="utf-8"))
batch_size = 100
n = (len(data) + batch_size - 1) // batch_size

for i in range(n):
    chunk = data[i * batch_size:(i + 1) * batch_size]
    path = OUT_DIR / f"input-{i+1:03d}.json"
    path.write_text(json.dumps(chunk, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {path.name}: {len(chunk)} entries")

print(f"total: {len(data)}, batches: {n}")
